#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string
import cPickle as pickle
#import pickle
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import random
import time
import zlib
import threading

import structures
#from structures import global_dict

locks = {}

allowed_clients = ["1.7.4.2"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
    def post(self):
        
        #global global_dict
        global_dict = {}
        starttime = time.time()
        post_body = self.request.body
        #if self.request.headers.get("Content-Encoding","ascii") == "gzip":
        #import logging
        #print self.request.headers.keys()
        #logging.info(str(len(post_body)))
        #logging.info(str(self.request.headers))
        #return    
        #try:
        #    post_body = gzip.decompress(post_body)
        #except:
        #    logging.info("no gzip for client!")
        
        sections = post_body.split('&')
        results = {}
        for pair in sections:
            ab = pair.split('=')
            results[ab[0]] = ab[1]
        
        client = results["client"]
        
        version = results["version"]
        if version in allowed_versions and client in allowed_clients:
            rumble = results["game"]
            
            if rumble not in locks:
                locks[rumble] = threading.Lock()
           #if "global" not in locks:
               #locks["global"] = threading.Lock()
                
            with locks[rumble]:
            #if True:
                game = memcache.get(rumble)            
                if game is None:
                    game = global_dict.get(rumble,None)    
                    if game is None:
                        game = structures.Rumble.get_by_key_name(rumble)
                        global_dict[game] = rumble
                else:
                    global_dict[game] = rumble
                    
                if game is None:
                    game = structures.Rumble(key_name = rumble,
                    Name = rumble, Rounds = int(results["rounds"]),
                    Field = results["field"], Melee = bool(results["melee"] == "YES"),
                    Teams = bool(results["teams"] == "YES"), TotalUploads = 0,
                    MeleeSize = 10, ParticipantsScores = zlib.compress(json.dumps([])))
                    self.response.out.write("CREATED NEW GAME TYPE " + rumble + "\n")
                    global_dict[game] = rumble
                else:
                    field = game.Field == results["field"]
                    rounds = (game.Rounds == int(results["rounds"]))
                    teams = game.Teams == bool(results["teams"] == "YES")
                    melee = game.Melee == bool(results["melee"] == "YES")
                    allowed = field and rounds and teams and melee
                    if not allowed:
                        self.response.out.write("OK. ERROR. Incorrect " + rumble + " config: ")
                        errorReasons = []
                        if not field:
                            errorReasons.append("field size ")
                        if not rounds:
                            errorReasons.append("number of rounds ")
                        if not teams:
                            errorReasons.append("teams ")
                        if not melee:
                            errorReasons.append("melee ")
                        self.response.out.write(string.join(errorReasons,", "))
                        
                        return
                
                try:
                    scores = pickle.loads(zlib.decompress(game.ParticipantsScores))
                except:
                    try:
                        scoresdicts = json.loads(zlib.decompress(game.ParticipantsScores))
                        scoreslist = [structures.LiteBot() for _ in scoresdicts]
                        for s,d in zip(scoreslist,scoresdicts):
                            s.__dict__.update(d)
                        scores = {s.Name:s for s in scoreslist}
                    except:
                        scores = {}
                    
                newBot = False
                bota = results["fname"]
                botb = results["sname"]
                
                bd = [[bota, rumble], [botb, rumble]]
                
                botHashes = [string.join(a,"|").encode('ascii') for a in bd]
                for b in botHashes:
                    intern(b)
                    
                syncname = rumble + "|" + structures.sync
                getHashes = botHashes + [syncname]
                
                botdict = memcache.get_multi(getHashes)
                global_dict.update(botdict)
                
                bots = [global_dict.get(h,None) for h in botHashes]
                
                pairingsarray = [[],[]]
                for i in [0, 1]:
                    if bots[i] is None or bots[i].PairingsList is None:
                        modelbot = structures.BotEntry.get_by_key_name(botHashes[i])
                        if modelbot is not None:
                            bots[i] = structures.CachedBotEntry(modelbot)
                            
                    if bots[i] is None:
                        modelbot = structures.BotEntry(key_name = botHashes[i],
                                Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0.0,
                                Survival = 0.0, PL = 0, Rumble = rumble, Active = False,
                                PairingsList = zlib.compress(pickle.dumps([]),1))
                        bots[i] = structures.CachedBotEntry(modelbot)
                        newBot = True
                    if isinstance(bots[i],structures.BotEntry):
                        bots[i] = structures.CachedBotEntry(bots[i])
                    
                    try:
                        pairingsarray[i] = pickle.loads(zlib.decompress(bots[i].PairingsList))
                    except:
                        pairsDicts = json.loads(zlib.decompress(bots[i].PairingsList))

                        pairingsarray[i] = [structures.ScoreSet() for _ in pairsDicts]
                        for s,d in zip(pairingsarray[i],pairsDicts):
                            s.__dict__.update(d)
                    #except:
                    #    pairingsarray[i] = pickle.loads(zlib.decompress(bots[i].PairingsList))
                        
                    if isinstance(bots[i],structures.BotEntry):
                        bots[i] = structures.CachedBotEntry(bots[i])
                         
                    bots[i].Name = bots[i].Name.encode('ascii')
                    intern(bots[i].Name)
                    
                    for p in pairingsarray[i]:
                        p.Name = p.Name.encode('ascii')
                        intern(p.Name)
                            
                    if not bots[i].Active or bots[i].Name not in scores: #game.ParticipantsScores:
                        #game.Participants.append(bd[i][0])
                        #game.Participants = list(set(game.Participants))
                        bots[i].Active = True
                        scores[bots[i].Name] = structures.LiteBot(bots[i])
                        newBot = True
                        self.response.out.write("Added " + bd[i][0] + " to " + rumble + "\n")
                
                        
                retrievetime = time.time() - starttime
                
                scorea = float(results["fscore"])
                scoreb = float(results["sscore"])
                
                
                if scorea + scoreb > 0:
                    APSa = 100*scorea/(scorea+scoreb)
                else:
                    APSa = 50#register a 0/0 as 50%
                APSb = 100 - APSa
                
                survivala = float(results["fsurvival"])
                survivalb = float(results["ssurvival"])
                
                survivala = 100.0*survivala/game.Rounds
                survivalb = 100.0*survivalb/game.Rounds
                
                    
                
                apair = None
                for p in pairingsarray[0]:
                    if p.Name == botb:
                        apair = p
                if apair is None:
                    apair = structures.ScoreSet(name = botb)
                    pairingsarray[0].append(apair)

                bpair = None
                for p in pairingsarray[1]:
                    if p.Name == bota:
                        bpair = p
                if bpair is None:
                    bpair = structures.ScoreSet(name = bota)
                    pairingsarray[1].append(bpair)
                    
                #participantsSet = set(game.Participants)
                
                    
                for b, pairings in zip(bots, pairingsarray):
                    i = 0
                    while i < len(pairings):
                        if pairings[i].Name not in scores:
                            pairings.pop(i)
                    
                        i += 1
                    b.Pairings = i
                
                botaPairs = bots[0].Pairings
                botbPairs = bots[1].Pairings
                
                aBattles = apair.Battles
                bBattles = bpair.Battles
                

                apair.APS *= float(aBattles)/(aBattles + 1)
                apair.APS += APSa/(aBattles+1)
                
                bpair.APS *= float(bBattles)/(bBattles + 1)
                bpair.APS += APSb/(bBattles+1)
                
                apair.Survival *= float(aBattles)/(aBattles + 1)
                apair.Survival += survivala/(aBattles+1)
                
                bpair.Survival *= float(bBattles)/(bBattles + 1)
                bpair.Survival += survivalb/(bBattles+1)
                
                apair.Battles += 1
                bpair.Battles += 1
                
                apair.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                bpair.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                

                for b, pairings in zip(bots, pairingsarray):
                    
                    #b.PairingsList = zlib.compress(json.dumps([p.__dict__ for p in pairings]),4)
                    b.PairingsList = zlib.compress(pickle.dumps(pairings,pickle.HIGHEST_PROTOCOL),1)
                    
                    aps = 0.0
                    survival = 0.0
                    pl = 0
                    battles = 0
                    if len(pairings) > 0:
                        for p in pairings:
                            aps += p.APS
                            survival += p.Survival
                            if p.APS > 50:
                                pl += 1
                            else:
                                pl -= 1
                            battles += p.Battles
                                
                        aps /= len(pairings)
                        survival /= len(pairings)
                        b.APS = aps
                        b.Survival = survival
                        b.PL = pl
                        b.Battles = battles
        
                    b.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                game.TotalUploads += 1
                
                self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
                
                game.AvgBattles = game.AvgBattles * 0.99 + 0.005 * (bots[0].Battles + bots[1].Battles)
                
                scorestime = time.time() - retrievetime - starttime
                

                

                
                sync = global_dict.get(syncname,None)
                if sync is None:
                    sync = {}
                else:
                    try:
                        sync = json.loads(zlib.decompress(sync))
                    except:
                        sync = {}
                
                for b in bots:
                    key = b.key_name
                    sync[key] = sync.get(key,0) + 1

                uploadsize = None
                if game.Melee:
                    uploadsize = game.MeleeSize -1
                else:
                    uploadsize = 30
                
                updates = min(len(sync),sorted(sync.values())[-min(len(sync),game.MeleeSize*10)])
                    
                wrote = False
                syncsize = -1
                if (game.Melee and updates >= uploadsize and len(sync) >= game.MeleeSize) or (not game.Melee and sum(sync.values()) > uploadsize):
                    syncset = sync.keys()
                    if game.Melee:
                        syncset = filter(lambda b: sync[b] >= game.MeleeSize-1,syncset)
                   # else:
                      #  syncset = filter(lambda b: sync[b] >= 1,syncset)
                        
                    if(len(syncset) > 30):
                        syncset = syncset[0:30]
                    if len(syncset) >= 1:
                        syncbotsDict = memcache.get_multi(syncset)
                        global_dict.update(syncbotsDict)
                            
                        syncbots = []
                        for sb in syncset:
                            b = global_dict.get(sb,None)
                            
                            if b is None or b.PairingsList is None:
                                sync.pop(sb,1)
                                global_dict.pop(sb,1)
                            else:
                                syncbots.append(b)
                                
                        if len(syncbots) >= 2:
                            sizelim = 800000
                            try:
                                while len(syncbots) > 0:
                                    size = 0
                                    num = 30
                                    thisput = []
                                    while len(syncbots) > 0 and num > 0:
                                        b = syncbots[-1]
                                        l = len(pickle.dumps(b,-1))
                                        if l+size > sizelim:
                                            break
                                        size += l
                                        syncbots.pop(-1)
                                        putb = structures.BotEntry(key_name = b.key_name)
                                        putb.init_from_cache(b)
                                        thisput.append(putb)
                                        num -= 1
                                    #try:
                                    db.put_async(thisput)
                                    for b in thisput:
                                        sync.pop(b.key().name(),1)
                                        global_dict.pop(b.key().name(),1)
                                    #except:
                                    #    self.response.out.write("\nERROR WRITING DATA!! QUOTA REACHED?")
                            except:
                                self.response.out.write("\nERROR WRITING DATA!! QUOTA REACHED?")
                            
                for b in bots:
                    if b.Name in scores:
                        lb = scores[b.Name]
                        b.ANPP = lb.ANPP
                        b.VoteScore = lb.VoteScore
                        scores.pop(b.Name,1)
                    scores[b.Name] = structures.LiteBot(b)
                
                game.ParticipantsScores = zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),1)
                #game.ParticipantsScores = zlib.compress(json.dumps([scores[s].__dict__ for s in scores]),4)
                game.Participants = []
                
                
                if game.BatchScoresAccurate:
                    game.BatchScoresAccurate = False
                    if not newBot:
                        game.put()
                if newBot:
                    game.put()
                    #db.put(bots)
                    memcache.delete("home")
                    
                botdict = {rumble:game,rumble + "|" + structures.sync:zlib.compress(json.dumps(sync),1)}
                for b in bots:
                    if b.key_name in sync:
                        botdict[b.key_name] = b
                
                global_dict.update(botdict)    
                memcache.set_multi(botdict)

            
            puttime = time.time() - scorestime - retrievetime - starttime
            
            if game.PriorityBattles and ((not game.Melee) or (game.Melee and random.random() < 0.0222)): # or min(bots, key = lambda b: b.Battles) < game.AvgBattles):
                #do a gradient descent to the lowest battled pairings:
                #1: take the bot of this pair which has less pairings/battles
                #2: find an empty pairing or take a low pairing
                #3: ????
                #4: PROFIT!!!
                
                priobot = None
                priopairs = None
                
                # this just does a gradient descent... let's do a direct search since we alread have the data
                if bots[0].Pairings < bots[1].Pairings:
                    priobot = bots[0]
                    priopairs = pairingsarray[0]
                elif bots[0].Pairings > bots[1].Pairings:
                    priobot = bots[1]
                    priopairs = pairingsarray[1]
                #elif min([b.Pairings for b in scores.values()]) < len(scores) - 1:
                #    possBots = filter(lambda b: b.Pairings < bots[0].Pairings,scores)
                    
                elif bots[0].Battles <= bots[1].Battles:
                    priobot = bots[0]
                    priopairs = pairingsarray[0]
                else:
                    priobot = bots[1]
                    priopairs = pairingsarray[1]
                
               # prioPack = [s for s in scores if s.Pairings < len(scores)-1 ]  
               # if len(prioPack) > 0:
                    
                
                
                
                priobot2 = None
                if priobot.Pairings < len(scores) - 1:
                    #create the first battle of a new pairing
                    
                    #cache pairings into dictionary to speed lookups against entire rumble
                    pairsdict = {}
                    for b in priopairs:
                        pairsdict[b.Name] = b
                    
                    #select all unpaired bots
                    possPairs = []
                    for p in scores:
                        if p not in pairsdict and p != priobot.Name:
                            possPairs.append(p)
                            
                    if len(possPairs) > 0:
                        #choose a random new pairing to prevent overlap
                        priobot2 = random.choice(possPairs)
                            
                                
                else:
                    #sort for lowest battled pairing
                    #priopairs = sorted(priopairs, key = lambda score: score.Battles)
                    minbat = min([p.Battles for p in priopairs])
                    possPairs = filter(lambda p: p.Battles <= minbat + 1 and p.Name != priobot.Name,priopairs)
                    while priobot2 is None:
                        
                        priobot2 = random.choice(possPairs).Name
                        #choose low battles, but still random - prevents lots of duplicates
                        
                        
                if priobot is not None and priobot2 is not None:    
                    priobots = [priobot.Name,priobot2]
                    priobots = [b.replace(' ','_') for b in priobots]
                    self.response.out.write("\n[" + string.join(priobots,",") + "]")
            
            
            priotime = time.time() - puttime - scorestime - retrievetime - starttime
            
            self.response.out.write("\nOK. " + bota + " vs " + botb + " received")
            
            elapsed = time.time() - starttime
            self.response.out.write(" in " + str(int(round(elapsed*1000))) + "ms")
            #self.response.out.write(" retrieve:" + str(int(round(retrievetime*1000))) + "ms")
            #self.response.out.write(" scores:" + str(int(round(scorestime*1000))) + "ms")
            #self.response.out.write(" priority battles:" + str(int(round(priotime*1000))) + "ms")
            #self.response.out.write(" put:" + str(int(round(puttime*1000))) + "ms")
            #self.response.out.write(", wrote " + str(syncsize) + " bots")
            #self.response.out.write(", " + str(len(sync)) + " bots waiting to write.")
            #self.response.out.write(", newBot: " + str(newBot))
            
        else:
            self.response.out.write("OK. CLIENT NOT SUPPORTED. Use one of: " + str(allowed_clients) + ", not " + client)
        



application = webapp.WSGIApplication([
    ('/UploadedResults', UploadedResults)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
