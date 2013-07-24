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
from google.appengine.api import taskqueue

def list_split(alist, split_size):
    return [alist[i:i+split_size] for i in range(0, len(alist), split_size)]

def dict_split(d, chunk_size=1):
    return    [
            dict(item for item in d.items()[i:i+chunk_size]) 
            for i in range(0, len(d.items()), chunk_size)
            ]
            

class QueueBatchRankings(webapp.RequestHandler):
    def get(self):  
        taskqueue.add(url='/BatchRankings',
                      target="batchratings",
                      payload=self.request.query_string)

class QueueDailyBatchRankings(webapp.RequestHandler):
    def get(self):  
        taskqueue.add(url='/BatchRankings',
                      target="batchratings",
                      payload="minwrite=true",
                      countdown=0)
        for i in [4,8,12,16,20]:
            taskqueue.add(url='/BatchRankings',
                          target="batchratings",
                          payload="",countdown=i*3600)
                      

class BatchRankings(webapp.RequestHandler):

           
    def post(self):
        try:
            #global global_dict
            #global_dict = {}
            starttime = time.time()
            cutoff_date = datetime.datetime.now() + datetime.timedelta(-365)
            cutoff_date_string = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
    
            parts = self.request.body.split("&")
            requests = {}
            
            if parts is not None and parts[0] != "":
                for pair in parts:
                    ab = pair.split('=')
                    requests[ab[0]] = ab[1]
            
            force = bool(requests.get("force",False))
            write = bool(requests.get("write",False))
            minwrite = bool(requests.get("minwrite",False))
            
            q = structures.Rumble.all()
            
            for r in q.run():
                   #clear garbage before loading lots of data!
                memr = memcache.get(r.Name)
                if memr is not None:
                    r = memr
                if r.BatchScoresAccurate and not force:
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
                totalAlivePairs = 0
                for i,b in enumerate(bots):    
                    try:
                        pairings = pickle.loads(zlib.decompress(b.PairingsList))
                    except:
                        pairsDicts = marshal.loads(zlib.decompress(b.PairingsList))
    
                        pairings = [structures.ScoreSet() for _ in pairsDicts]
                        for s,d in zip(pairings,pairsDicts):
                            s.__dict__.update(d)                
                    removes = []
                    alivePairings = 0
                    for q,p in enumerate(pairings):
                        j = botIndexes.get(p.Name,-1)
                        if j != -1:
                            APSs[j,i] = numpy.float64(p.APS)
                            p.Alive = True
                            alivePairings += 1
                        else:
                            removes.append(q)
                    b.Pairings = alivePairings
                    totalAlivePairs += alivePairings
                    removes.reverse()
                    removed = False
                    for q in removes:
                        p = pairings[q]
                        if p.LastUpload < cutoff_date_string:
                            removed = True
                            pairings.pop(q)
                        else:
                            if p.Alive:
                                removed = True
                            p.Alive = False
                    if removed:
                        b.PairingsList = zlib.compress(pickle.dumps(pairings,-1),1)
                    
                            
                APSs += numpy.float64(100) - APSs.transpose()
                APSs *= numpy.float64(0.5)
                
                numpy.fill_diagonal(APSs, numpy.nan)
                
                gc.collect()
                logging.info(str(len(bots)) + " bots loaded, total of " + str(totalAlivePairs) + " alive pairings")
                logging.info("mem usage after unzipping pairings: " + str(runtime.memory_usage().current()) + "MB")        
                
                #Vote
                mins = numpy.nanmax(APSs,1)
                for i,minimum in enumerate(mins):
                    minIndexes = numpy.argwhere(APSs[i,...] == minimum)
                    ties = len(minIndexes)
                    if ties > 0:
                        increment = 1./ties
                        for minIndex in minIndexes:
                            bots[minIndex].VoteScore += increment
    
                #inv_len = 1.0/botlen
                for b in bots:
                    if b.Pairings > 0:
                        b.VoteScore = 100.0*b.VoteScore/float(b.Pairings)
                    else:
                        b.VoteScore = 0
                    
                #KNN PBI
                half_k = int(math.ceil(math.sqrt(botlen)/2))
                KNN_PBI = -numpy.ones((botlen,botlen))
                for i in xrange(len(bots)):
                    low_bound = max([0,i-half_k])
                    high_bound = min([botlen-1,i+half_k])
                    low_high_bound = min([i+1,high_bound])
                    before = APSs[:,low_bound:i]
                    after = APSs[:,low_high_bound:high_bound]
                    compare = numpy.hstack((before,after))
                    mm = numpy.mean(numpy.ma.masked_array(compare,numpy.isnan(compare)),axis=1)
                    KNN_PBI[:,i] = APSs[:,i] - mm.filled(numpy.nan)
    
    #                a[i] = 0
     #               logging.info("mean error of transpose: " + str(numpy.mean(numpy.square(a))))
                
                #KNN_PBI[KNN_PBI == numpy.nan] = -1
    
                
                logging.info("mem usage after KNNPBI: " + str(runtime.memory_usage().current()) + "MB")         
                # Avg Normalised Pairing Percentage
                
                mins = numpy.nanmin(APSs,1)            
                maxs = numpy.nanmax(APSs,1)
                inv_ranges = numpy.float64(1.0)/(maxs - mins)
                NPPs = -numpy.ones((botlen,botlen))
                for i in range(botlen):
                    if numpy.isfinite(inv_ranges[i]):
                        NPPs[i,:] = numpy.float64(100)*(APSs[i,:] - mins[i]) * inv_ranges[i]
                    else:
                        NPPs[i,:] = numpy.float64(100)
                
                #NPPs[NPPs] = -1
                
                logging.info("mem usage after ANPP: " + str(runtime.memory_usage().current()) + "MB")   
                
                changedBots = []#bots with new pairings since last run
                
                # save to cache
                botsdict = {}
                
                for i,b in enumerate(bots):    
    #                try:
                    pairings = pickle.loads(zlib.decompress(b.PairingsList))
    #                except:
    #                    pairsDicts = marshal.loads(zlib.decompress(b.PairingsList))
    #
    #                    pairings = [structures.ScoreSet() for _ in pairsDicts]
    #                    for s,d in zip(pairings,pairsDicts):
    #                        s.__dict__.update(d)                
                    nppCount = 0
                    totalNPP = 0.0
                    
                    apsCount = 0
                    totalAPS = 0.0
                    
                    aliveCount = 0
                    
                    changed = False
                    for p in pairings:
                        j = botIndexes.get(p.Name,-1)
                        if j != -1:
                            p.Alive = True
                            changePotential = (p.KNNPBI == 0.0 and p.NPP == -1 )

                                
                            aliveCount += 1
                            p.KNNPBI = float(KNN_PBI[j,i])
                            p.NPP = float(NPPs[j,i])
    
                            if not numpy.isnan(APSs[j,i]):
                                p.APS = float(APSs[j,i])
                                totalAPS += p.APS
                                apsCount += 1
                                
                            if numpy.isnan(p.KNNPBI):
                                p.KNNPBI = 0
                            
                            if numpy.isnan(p.NPP):
                                p.NPP = -1
                            else:
                                totalNPP += p.NPP
                                nppCount += 1
                                
                            if changePotential and p.KNNPBI != 0.0 and p.NPP != -1 :
                                changed = True
                        else:
                            p.Alive = False
                            p.KNNPBI = 0
                            p.NPP = -1
                        
                    
                    if nppCount > 0:
                        b.ANPP = float(totalNPP/nppCount)
                    else:
                        b.ANPP = -1.0
                    if apsCount > 0:
                        b.APS = float(totalAPS/apsCount)
                    else:
                        b.APS = -1.0
                        
                
    
                    b.PairingsList = zlib.compress(pickle.dumps(pairings,-1),1)
                    b.Pairings = aliveCount
                    if b.Pairings > 0:
                        botsdict[b.key_name] = b
                    if changed:
                        changedBots.append(b)
                    
                logging.info("mem usage after zipping: " + str(runtime.memory_usage().current()) + "MB")     
    
                #gc.collect()
                #logging.info("mem usage after gc: " + str(runtime.memory_usage().current()) + "MB")     
                
                if len(botsdict) > 0:
                    splitlist = dict_split(botsdict,32)
                    for d in splitlist:
                        memcache.set_multi(d)
                    
                    logging.info("wrote " + str(len(botsdict)) + " bots to memcache")
                    #global_dict.update(botsdict)
                
                
                botsdict.clear()
                botsdict = None
                
                scores = {b.Name: structures.LiteBot(b) for b in bots}
                
               # bots = None
                gc.collect()
                
                r.ParticipantsScores = db.Blob(zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),3))
                #logging.info("mem usage after scores zipping: " + str(runtime.memory_usage().current()) + "MB")     
                #r.ParticipantsScores = zlib.compress(marshal.dumps([scores[s].__dict__ for s in scores]),4)
                scores = None
                
                if write:
                    writebots = [None]*len(bots)
                    for i,b in enumerate(bots):
                        putb = structures.BotEntry(key_name = b.key_name)
                        putb.init_from_cache(b)
                        writebots[i] = putb
                    write_lists = list_split(writebots,50)
                    for subset in write_lists:                    
                        db.put(subset)
                    logging.info("wrote " + str(len(writebots)) + " bots to database")
                    
                if minwrite:
                    writebots = [None]*len(changedBots)
                    for i,b in enumerate(changedBots):
                        putb = structures.BotEntry(key_name = b.key_name)
                        putb.init_from_cache(b)
                        writebots[i] = putb
                    write_lists = list_split(writebots,50)
                    for subset in write_lists:                    
                        db.put(subset)
                    logging.info("wrote " + str(len(writebots)) + " changed bots to database")
                changedBots = None
                if write or minwrite:
                    r.BatchScoresAccurate = True
                memcache.set(r.Name,r)
                
                r.put()
                #gc.collect()
                r = None
                logging.info("mem usage after write: " + str(runtime.memory_usage().current()) + "MB")     
                
                    
                
            elapsed = time.time() - starttime    
            self.response.out.write("Success in " + str(round(1000*elapsed)) + "ms")
        except:
            logging.exception('')

application = webapp.WSGIApplication([
    ('/BatchRankings', BatchRankings),
    ('/QueueBatchRankings', QueueBatchRankings),
    ('/QueueDailyBatchRankings', QueueDailyBatchRankings)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
