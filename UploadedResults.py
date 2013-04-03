#!/usr/bin/env python
#import cgi
import datetime
import wsgiref.handlers
#try:
#    import json
#except:
#    import simplejson as json
import string
import cPickle as pickle
#import pickle
from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
#from operator import attrgetter
import random
import time
import zlib
import threading

import structures
import logging
from structures import global_dict
import numpy
import marshal

global_sync = {}
#sync_lock = threading.Lock()
#write_lock = threading.Lock()
last_write = {}
locks = {}

allowed_clients = ["1.7.4.2", "1.8.1.0 Alpha 7", "1.8.1.0"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
    def post(self):
        global global_dict
        global global_sync
        global locks
        global last_write
        #global sync_lock
        
        starttime = time.time()
        post_body = self.request.body
        
        sections = post_body.split('&')
        results = {}
        for pair in sections:
            ab = pair.split('=')
            if ab is not None and len(ab) == 2:
                results[ab[0]] = ab[1]
        
        client = results.get("client","ERROR")
        user = results.get("user","ERROR")
        put_result = None
        version = results.get("version","ERROR")
        if version in allowed_versions and client in allowed_clients:
            rumble = results.get("game","ERROR")
            
            #logging.debug("game: " + rumble + ", user: " + user)

            syncname = str(bool(results["melee"] == "YES")) + "|" + structures.sync
            writelockname = "write" + syncname
            if syncname not in locks:
                locks[syncname] = threading.Lock()
            sync_lock = locks[syncname]
            if writelockname not in locks:
                locks[writelockname] = threading.Lock()
            write_lock = locks[writelockname]
            
            if syncname not in last_write:
                last_write[syncname] = time.time()
            last_write_time = last_write[syncname]
            
            
            global_sync[syncname] = global_sync.get(syncname,{})
            botsync = global_sync[syncname]
            
            if True:
                
                
                bota = results["fname"]
                botb = results["sname"]
                #logging.debug("Bots : " + bota + " vs. " + botb)
                
                bd = [[bota, rumble], [botb, rumble]]
                
                botHashes = [string.join(a,"|").encode('ascii') for a in bd]
                
                memget = [rumble]
                memget.extend(botHashes) #botHashes.append(rumble)
                memdict = memcache.get_multi(memget)                
                
                game = memdict.get(rumble,None)
                game_future = None
                if game is None:
                    #game = structures.Rumble.get_by_key_name(rumble)
                    game_future = db.get_async(db.Key.from_path('Rumble',rumble))
                    
                newBot = False
                
                bots = [memdict.get(h,None) for h in botHashes]
                
                pairingsarray = [[],[]]
                botFutures = [None,None]
                for i in [0, 1]:
                    if bots[i] is None or bots[i].PairingsList is None:
                        botFutures[i] = db.get_async(db.Key.from_path('BotEntry',botHashes[i]))

                for i in [0,1]:
                    if botFutures[i] is not None:                        
                        modelbot = botFutures[i].get_result()
                        if modelbot is not None:
                            bots[i] = structures.CachedBotEntry(modelbot)
                            #logging.debug("retrieved from database")
                            
                for i in [0,1]:
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
                        bots[i].PairingsList = None
                    except:
                        pairsDicts = marshal.loads(zlib.decompress(bots[i].PairingsList))

                        pairingsarray[i] = [structures.ScoreSet() for _ in pairsDicts]
                        for s,d in zip(pairingsarray[i],pairsDicts):
                            s.__dict__.update(d)
                        bots[i].PairingsList = None


                    
                                             
                    #bots[i].Name = bots[i].Name.encode('ascii')
                    #intern(bots[i].Name)
                    
                   # for p in pairingsarray[i]:
                    #    p.Name = p.Name.encode('ascii')
                     #   intern(p.Name)
                    
                            

                if game_future is not None:
                    game = game_future.get_result()

                if game is None:
                    game = structures.Rumble(key_name = rumble,
                    Name = rumble, Rounds = int(results["rounds"]),
                    Field = results["field"], Melee = bool(results["melee"] == "YES"),
                    Teams = bool(results["teams"] == "YES"), TotalUploads = 0,
                    MeleeSize = 10, ParticipantsScores = db.Blob(zlib.compress(pickle.dumps([]))))
                    self.response.out.write("CREATED NEW GAME TYPE " + rumble + "\n")
                    
                    logging.info("Created new game type: " + rumble)
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
                scores = None
                
                try:
                    scores = pickle.loads(zlib.decompress(game.ParticipantsScores))
                    game.ParticipantsScores = None
                    if len(scores) == 0:
                        scores = {}
                except:
                    scoresdicts = marshal.loads(zlib.decompress(game.ParticipantsScores))
                    scoreslist = [structures.LiteBot(loadDict = d) for d in scoresdicts]
                    #for s,d in zip(scoreslist,scoresdicts):
                    #    s.__dict__.update(d)
                    scores = {s.Name:s for s in scoreslist}
                    if len(scores) == 0:
                        scores = {}
                
                    #logging.debug("uncompressed scores: " + str(len(s)) + "   compressed: " + str(a))

                        
                        
                for i in [0,1]:
                    
                    if not bots[i].Active or bots[i].Name not in scores: 
                        bots[i].Active = True
                        scores[bots[i].Name] = structures.LiteBot(bots[i])
                        newBot = True
                        self.response.out.write("Added " + bd[i][0] + " to " + rumble + "\n")
                        logging.info("added new bot!")
                
                        
                #retrievetime = time.time() - starttime
                
                scorea = float(results["fscore"])
                scoreb = float(results["sscore"])
                
                
                if scorea + scoreb > 0:
                    APSa = 100*scorea/(scorea+scoreb)
                else:
                    APSa = 50#register a 0/0 as 50%
                #APSb = 100 - APSa
                
                survivala = float(results["fsurvival"])
                survivalb = float(results["ssurvival"])
                
                survivala = 100.0*survivala/game.Rounds
                survivalb = 100.0*survivalb/game.Rounds
                
                for b, pairings in zip(bots, pairingsarray):
                    
                    #b.PairingsList = zlib.compress(marshal.dumps([s.__dict__ for s in pairings]),1)
                    
                    if len(pairings) > 0:
                        removes = []
                        for p in pairings:
                            try:
                                p.APS = float(p.APS)
                                p.Survival = float(p.Survival)
                                p.Battles = int(p.Battles)
                            except:
                                removes.append(pairings.index(p))
                                continue
                            
                        removes.sort(reverse=True)
                        for i in removes:
                            pairings.pop(i)
                
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
                        if pairings[i].Name == b.Name:
                            pairings.pop(i)
                            continue
                        if not hasattr(pairings[i],"Alive"):
                            pairings[i].Alive = True
                        
                        if pairings[i].Alive and pairings[i].Name not in scores:
                            pairings[i].Alive = False
                    
                        i += 1
                    b.Pairings = i
                
                #botaPairs = bots[0].Pairings
                #botbPairs = bots[1].Pairings
                                
                aBattles = apair.Battles
                
                
                #bBattles = bpair.Battles
                
                inv_ab = 1.0/(aBattles + 1.0)    

                apair.APS *= float(aBattles)*inv_ab
                apair.APS += APSa*inv_ab
                
                #bpair.APS *= float(bBattles)/(bBattles + 1)
                #bpair.APS += APSb/(bBattles+1)
                bpair.APS = 100 - apair.APS
                            
                apair.Survival *= float(aBattles)*inv_ab
                apair.Survival += survivala*inv_ab
                
                bpair.Survival *= float(aBattles)*inv_ab
                bpair.Survival += survivalb*inv_ab
                
                apair.Battles += 1
                bpair.Battles = apair.Battles
                
                apair.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                bpair.LastUpload = apair.LastUpload
                

                for b, pairings in zip(bots, pairingsarray):
                    aps = 0.0
                    survival = 0.0
                    pl = 0
                    battles = 0
                    if len(pairings) > 0:
                        
                        for p in pairings:
                            if p.Alive:
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
                        
                    b.PairingsList = zlib.compress(pickle.dumps(pairings,pickle.HIGHEST_PROTOCOL),1)
                    b.LastUpload = apair.LastUpload
                
                game.TotalUploads += 1
                
                self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
                
                game.AvgBattles = game.AvgBattles * 0.99 + 0.005 * (bots[0].Battles + bots[1].Battles)

                

                

                #synclen = 0
                with sync_lock:
                    for b in bots:
                        key = b.key_name
                        botsync[key] = botsync.get(key,0) + 1
                    #synclen = len(botsync)

                minSize = min(60,len(scores)/2)
                
                botsDict = {}
                for b in bots:
                    botsDict[b.key_name] = b
                            
                if len(botsync) > minSize and not write_lock.locked():# and time.time() > last_write_time + 20:
                    
                    with write_lock:
                        syncset = None
                        with sync_lock:
                            #last_write[syncname] = time.time()
                            syncset = botsync.keys()
                            #medianVal = numpy.median(botsync.values())
                            #if medianVal > 1:
                            #syncset = filter(lambda b: botsync[b] >= 2,syncset)
                        if len(syncset) >= 10:
                            syncbotsDict = memcache.get_multi(syncset)
                            botsDict.update(syncbotsDict)
                            with sync_lock:
                                syncbots = []
                                for sb in syncset:
                                    b = botsDict.get(sb,None)
                                    
                                    if b is None or b.PairingsList is None:
                                        botsync.pop(sb,1)
                                        botsDict.pop(sb,1)
                                    else:
                                        syncbots.append(b)
                                        botsync.pop(sb,1)
                                        
                        
                            try:
                                thisput = []
                                while len(syncbots) > 0:
                                    b = syncbots.pop(-1)
                                    putb = structures.BotEntry(key_name = b.key_name)
                                    putb.init_from_cache(b)
                                    thisput.append(putb)
        
                                put_result = db.put_async(thisput)
                                
                                logging.info("wrote " + str(len(thisput)) + " results to database")
                                for b in thisput:
                                    s = b.key().name()
                                    botsync.pop(s,1)
                                    botsDict.pop(s,1)
                                
                            except Exception, e:
                                logging.error('Failed to write data: '+ str(e))
                                self.response.out.write('Failed to write data: '+ str(e.__class__))
                            
                for b in bots:
                    if b.Name in scores:
                        lb = scores[b.Name]
                        b.ANPP = lb.ANPP
                        b.VoteScore = lb.VoteScore
                        scores.pop(b.Name,1)
                    scores[b.Name] = structures.LiteBot(b)
                
                game.ParticipantsScores = db.Blob(zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),1))
                game.Participants = []
                
                
                if game.BatchScoresAccurate:
                    game.BatchScoresAccurate = False
                    if not newBot:
                        game.put()
                if newBot:
                    game.put()
                    #db.put(bots)
                    memcache.delete("home")
                    
                infodict = {rumble:game}  #,syncname:zlib.compress(json.dumps(sync),1)}
                botsDict.update(infodict)
                                    
                global_dict.update(infodict)    
                for b in bots:
                    botsDict[b.key_name] = b
                memcache.set_multi(botsDict)

            
           # puttime = time.time() - scorestime - retrievetime - starttime
            scoreVals = scores.values()
            maxPairs = len(scoreVals) - 1           
            if game.PriorityBattles and ((not game.Melee) or (game.Melee and (random.random() < 0.0222 or min([bots[0].Pairings,bots[1].Pairings]) < maxPairs))): # or min(bots, key = lambda b: b.Battles) < game.AvgBattles):
                #do a gradient descent to the lowest battled pairings:
                #1: take the bot of this pair which has less pairings/battles
                #2: find an empty pairing or take a low pairing
                #3: ????
                #4: PROFIT!!!
                
                priobot = None
                priopairs = None
                
                # this just does a gradient descent... let's do a direct search since we alread have the data

                priobot2 = None                                
                if bots[0].Pairings < maxPairs:
                    priobot = bots[0]
                    priopairs = pairingsarray[0]
                elif bots[1].Pairings < maxPairs:
                    priobot = bots[1]
                    priopairs = pairingsarray[1]
                elif min([b.Pairings for b in scores.values()]) < maxPairs:
                    possBots = filter(lambda b: b.Pairings < maxPairs,scoreVals)
                    priobot = random.choice(possBots)
                    priobot2 = random.choice(scoreVals).Name
                    while priobot2 == priobot.Name:
                        priobot2 = random.choice(scoreVals).Name
                elif bots[0].Battles <= bots[1].Battles:
                    priobot = bots[0]
                    priopairs = pairingsarray[0]
                else:
                    priobot = bots[1]
                    priopairs = pairingsarray[1]
                
               # prioPack = [s for s in scores if s.Pairings < len(scores)-1 ]  
               # if len(prioPack) > 0:
                    
                
                
                
                if priobot2 is None and priopairs is not None:
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
                        if len( possPairs) > 0:
                            
                            priobot2 = random.choice(possPairs).Name
                            #choose low battles, but still random - prevents lots of duplicates
                        
                        
                if priobot is not None and priobot2 is not None:    
                    priobots = [priobot.Name,priobot2]
                    priobots = [b.replace(' ','_') for b in priobots]
                    self.response.out.write("\n[" + string.join(priobots,",") + "]")
            
            
           # priotime = time.time() - puttime - scorestime - retrievetime - starttime
            
            self.response.out.write("\nOK. " + bota + " vs " + botb + " received")
            
            elapsed = time.time() - starttime
            self.response.out.write(" in " + str(int(round(elapsed*1000))) + "ms")
            #time.sleep(0.5)
            #self.response.out.write(" retrieve:" + str(int(round(retrievetime*1000))) + "ms")
            #self.response.out.write(" scores:" + str(int(round(scorestime*1000))) + "ms")
            #self.response.out.write(" priority battles:" + str(int(round(priotime*1000))) + "ms")
            #self.response.out.write(" put:" + str(int(round(puttime*1000))) + "ms")
            #self.response.out.write(", wrote " + str(syncsize) + " bots")
            #self.response.out.write(", " + str(len(sync)) + " bots waiting to write.")
            #self.response.out.write(", newBot: " + str(newBot))
            
        else:
            self.response.out.write("OK. CLIENT NOT SUPPORTED. Use one of: " + str(allowed_clients) + ", not " + client)
        
        if put_result is not None:
            put_result.get_result()



application = webapp.WSGIApplication([
    ('/UploadedResults', UploadedResults)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
