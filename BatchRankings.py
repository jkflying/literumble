#!/usr/bin/env python
#import cgi
import datetime
import wsgiref.handlers
import time
#try:
#    import json
#except:
#    import simplejson as json
import string
import marshal

import zlib
import cPickle as pickle
import math

from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures
from google.appengine.api import runtime
import logging
#from structures import global_dict
import numpy
import gc

def list_split(alist, split_size):
    return [alist[i:i+split_size] for i in range(0, len(alist), split_size)]

def dict_split(d, chunk_size=1):
    return    [
            dict(item for item in d.items()[i:i+chunk_size]) 
            for i in range(0, len(d.items()), chunk_size)
            ]

class BatchRankings(webapp.RequestHandler):

           
    def get(self):
        #global global_dict
        #global_dict = {}
        starttime = time.time()
        cutoff_date = datetime.datetime.now() + datetime.timedelta(-30)
        cutoff_date_string = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

        q = structures.Rumble.all()
        
        for r in q.run():
               #clear garbage before loading lots of data!
            memr = memcache.get(r.Name)
            if memr is not None:
                r = memr
            if r.BatchScoresAccurate:
                continue


            gc.collect()            
            gc.collect(2)               
            
            logging.info("mem usage at start of " + r.Name + ": " + str(runtime.memory_usage().current()) + "MB")
            try:
                scores = pickle.loads(zlib.decompress(r.ParticipantsScores))
            except:
                scoresdicts = marshal.loads(zlib.decompress(r.ParticipantsScores))
                scoreslist = [structures.LiteBot() for _ in scoresdicts]
                for s,d in zip(scoreslist,scoresdicts):
                    s.__dict__.update(d)
                scores = {s.Name:s for s in scoreslist}
            
            if len(scores) == 0:
                continue
                    
            r.ParticipantsScores = None
            gc.collect()

            particHash = [p + "|" + r.Name for p in scores]
            
            particSplit = list_split(particHash,32)
            ppDict = {}
            for l in particSplit:
                ppDict.update(memcache.get_multi(l))
            
            
            particSplit = None
            
            bots = [ppDict.get(h,None) for h in particHash]
            
            botsdict = {}


            missingHashes = []
            missingIndexes = []
            for i in xrange(len(bots)):
                if bots[i] is None:
                    missingHashes.append(particHash[i])
                    missingIndexes.append(i)
                
                elif isinstance(bots[i],structures.BotEntry):
                    bots[i] = structures.CachedBotEntry(bots[i])
                    
            if len(missingHashes) > 0:
                bmis = structures.BotEntry.get_by_key_name(missingHashes)

                #lost = False
                lostList = []

                for i in xrange(len(missingHashes)):
                    if bmis[i] is not None:
                        cb = structures.CachedBotEntry(bmis[i])
                        bots[missingIndexes[i]] = cb
                        botsdict[missingHashes[i]] = cb
                        
                    else:
                        bots[missingIndexes[i]] = None
                        lostList.append(missingHashes[i])
                        #lost = True

            
            particHash = None
            missingHashes = None
            missingIndexes = None
            logging.info("mem usage after loading bots: " + str(runtime.memory_usage().current()) + "MB")     

            bots = filter(lambda b: b is not None, bots)
            
            get_key = attrgetter("APS")
            bots.sort( key=lambda b: get_key(b), reverse=True)
            
            gc.collect()   
   
            botIndexes = {}
            for i,b in enumerate(bots):
                b.Name = b.Name.encode('ascii')
                intern(b.Name)
                botIndexes[b.Name] = i
                b.VoteScore = 0.
            
            botlen = len(bots)
            APSs = numpy.empty([botlen,botlen])  
            APSs.fill(numpy.nan)
            
            for i,b in enumerate(bots):    
                try:
                    pairings = pickle.loads(zlib.decompress(b.PairingsList))
                except:
                    pairsDicts = marshal.loads(zlib.decompress(b.PairingsList))

                    pairings = [structures.ScoreSet() for _ in pairsDicts]
                    for s,d in zip(pairings,pairsDicts):
                        s.__dict__.update(d)                
                removes = []
                for q,p in enumerate(pairings):
                    j = botIndexes.get(p.Name,-1)
                    if not j == -1:
                        try:
                            APSs[j][i] = p.APS
                        except:
                            removes.append(q)
                removes.reverse()
                for q in removes:
                    p = pairings[q]
                    if p.LastUpload < cutoff_date_string:
                        pairings.pop(q)
                    else:
                        p.Alive = False
                
                b.Pairings = len(pairings)
                        
            APSs += 100 - APSs.transpose()
            APSs *= 0.5
            
            numpy.fill_diagonal(APSs, numpy.nan)
            
            gc.collect()
            
            logging.info("mem usage after unzipping pairings: " + str(runtime.memory_usage().current()) + "MB")        
            
            #Vote
            minIndexes = numpy.nanargmax(APSs,1)
            for minIndex in minIndexes:
                bots[minIndex].VoteScore += 1

            #inv_len = 1.0/botlen
            for b in [bots[i] for i in set(minIndexes)]:
                b.VoteScore = 100.0*b.VoteScore/float(b.Pairings)
                
            #KNN PBI
            half_k = int(math.ceil(math.sqrt(botlen)/2))
            KNN_PBI = -numpy.ones((botlen,botlen))
            for i,b in enumerate(bots):
                low_bound = max([0,i-half_k])
                high_bound = min([botlen-1,i+half_k])
                before = APSs[:][low_bound:i]
                after = APSs[:][(i+1):high_bound]
                compare = numpy.vstack((before,after))
                mm = numpy.mean(numpy.ma.masked_array(compare,numpy.isnan(compare)),axis=0)
                KNN_PBI[:][i] = APSs[:][i] - mm.filled(numpy.nan)
            
            #KNN_PBI[KNN_PBI == numpy.nan] = -1

            
            logging.info("mem usage after KNNPBI: " + str(runtime.memory_usage().current()) + "MB")         
            # Avg Normalised Pairing Percentage
            
            mins = numpy.nanmin(APSs,1)            
            maxs = numpy.nanmax(APSs,1)
            inv_ranges = 1.0/(maxs - mins)
            NPPs = -numpy.ones((botlen,botlen))
            for i in range(botlen):
                NPPs[:][i] = 100*(APSs[i][:] - mins[i]) * inv_ranges[i]
            
            #NPPs[NPPs] = -1
            
            logging.info("mem usage after ANPP: " + str(runtime.memory_usage().current()) + "MB")   
            
            
            
            # save to cache
            botsdict = {}
            
            for i,b in enumerate(bots):    
                try:
                    pairings = pickle.loads(zlib.decompress(b.PairingsList))
                except:
                    pairsDicts = marshal.loads(zlib.decompress(b.PairingsList))

                    pairings = [structures.ScoreSet() for _ in pairsDicts]
                    for s,d in zip(pairings,pairsDicts):
                        s.__dict__.update(d)                
                count = 0
                totalNPP = 0.0
                
                apsCount = 0
                totalAPS = 0.0
                for p in pairings:
                    if not getattr(p,'Alive',True):
                        continue
                    
                    j = botIndexes.get(p.Name,-1)
                    if j == -1:
                        p.KNNPBI = 0
                        p.NPP = -1
                    else:
                        
                        p.KNNPBI = float(KNN_PBI[j][i])
                        p.NPP = float(NPPs[j][i])
                        if not numpy.isnan(APSs[j][i]):
                            p.APS = float(APSs[j][i])
                            totalAPS += p.APS
                            apsCount += 1
                        
                        if not numpy.isnan(p.NPP):
                            totalNPP += p.NPP
                            count += 1
                
                if count > 0:
                    b.ANPP = float(totalNPP/count)
                else:
                    b.ANPP = -1.0
                if apsCount > 0:
                    b.APS = float(totalAPS/apsCount)
                    
            

                b.PairingsList = zlib.compress(pickle.dumps(pairings,pickle.HIGHEST_PROTOCOL),4)

                if b.Pairings > 0:
                    botsdict[b.key_name] = b
                
            logging.info("mem usage after zipping: " + str(runtime.memory_usage().current()) + "MB")     

            #gc.collect()
            #logging.info("mem usage after gc: " + str(runtime.memory_usage().current()) + "MB")     
            
            if len(botsdict) > 0:
                splitlist = dict_split(botsdict,32)
                for d in splitlist:
                    memcache.set_multi(d)
                #global_dict.update(botsdict)
            
            
            botsdict.clear()
            botsdict = None
            
            scores = {b.Name: structures.LiteBot(b) for b in bots}
            
            bots = None
            gc.collect()
            
            r.ParticipantsScores = db.Blob(zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),3))
            #logging.info("mem usage after scores zipping: " + str(runtime.memory_usage().current()) + "MB")     
            #r.ParticipantsScores = zlib.compress(marshal.dumps([scores[s].__dict__ for s in scores]),4)
            scores = None
            
            r.BatchScoresAccurate = True
            memcache.set(r.Name,r)
            r.put()
            #gc.collect()
            r = None
            logging.info("mem usage after write: " + str(runtime.memory_usage().current()) + "MB")     
            
                
            
        elapsed = time.time() - starttime    
        self.response.out.write("Success in " + str(round(1000*elapsed)) + "ms")


application = webapp.WSGIApplication([
    ('/BatchRankings', BatchRankings)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
