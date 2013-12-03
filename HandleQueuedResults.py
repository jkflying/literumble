#!/usr/bin/env python
#import cgi
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
#from google.appengine.api import users
from google.appengine.api import taskqueue
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
import Queue
#from Queue import EMPTY

global_sync = {}
#sync_lock = threading.Lock()
#write_lock = threading.Lock()
last_write = {}
locks = {}



def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)

class HandleQueuedResults(webapp.RequestHandler):
    def post(self):
        global global_dict
        #global_dict = {}
        global global_sync
        global locks
        global last_write
        #global sync_lock
        
#        starttime = time.time()
        results = json.loads(self.request.body)
        
        rumble = results.get("game","ERROR")
        
        #logging.debug("game: " + rumble + ", user: " + user)

        syncname = str(bool(results.get("melee") == "YES")) + "|" + structures.sync
        writelockname = "write" + syncname
        if syncname not in locks:
            locks[syncname] = threading.Lock()
        sync_lock = locks[syncname]
        if writelockname not in locks:
            locks[writelockname] = threading.Lock()
        write_lock = locks[writelockname]
        
        #if syncname not in last_write:
        #    last_write[syncname] = time.time()
        #last_write_time = last_write[syncname]
        
        
        global_sync[syncname] = global_sync.get(syncname,{})
        botsync = global_sync[syncname]
        
        if True:
            
            
            bota = results.get("fname")
            botb = results.get("sname")
            #bota = rreplace(bota,"_"," ",1)
            #botb = rreplace(botb,"_"," ",1)
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
                    try:
                        pairsDicts = marshal.loads(zlib.decompress(bots[i].PairingsList))
    
                        pairingsarray[i] = [structures.ScoreSet() for _ in pairsDicts]
                        for s,d in zip(pairingsarray[i],pairsDicts):
                            s.__dict__.update(d)
                        bots[i].PairingsList = None
                    except:
                        pairingsarray[i] = []

                
                        

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
                    errstr = "OK. ERROR. Incorrect " + rumble + " config: "
                    errorReasons = []
                    if not field:
                        errorReasons.append("field size ")
                    if not rounds:
                        errorReasons.append("number of rounds ")
                    if not teams:
                        errorReasons.append("teams ")
                    if not melee:
                        errorReasons.append("melee ")
                    logging.error(errstr + string.join(errorReasons,", ") + "  User: " + results["user"])
                    
                    return
            scores = None
            
            try:
                scores = pickle.loads(zlib.decompress(game.ParticipantsScores))
                game.ParticipantsScores = None
                if len(scores) == 0:
                    scores = {}
            except:
                scoresdicts = marshal.loads(zlib.decompress(game.ParticipantsScores))
                game.ParticipantsScores = None
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
                #b.Pairings = i
            
                            
            aBattles = apair.Battles
            #bBattles = bpair.Battles
            
            inv_ab = 1.0/(aBattles + 1.0)    

            apair.APS *= float(aBattles)*inv_ab
            apair.APS += APSa*inv_ab
            apair.__dict__["Min_APS"] = min(APSa,apair.__dict__.get("Min_APS",100))
            #bpair.APS *= float(bBattles)/(bBattles + 1)
            #bpair.APS += APSb/(bBattles+1)
            bpair.APS = 100 - apair.APS
            bpair.__dict__["Min_APS"] = min(100-APSa,bpair.__dict__.get("Min_APS",100))
                        
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
                alivePairings = 0
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
                            alivePairings += 1

                            
                    aps /= alivePairings
                    survival /= alivePairings
                    b.APS = aps
                    b.Survival = survival
                    b.PL = pl
                    b.Battles = battles
                    
                b.PairingsList = db.Blob(zlib.compress(pickle.dumps(pairings,pickle.HIGHEST_PROTOCOL),1))
                b.LastUpload = apair.LastUpload
                b.Pairings = alivePairings
                
                
            
            game.TotalUploads += 1
            
            #self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
            game.LastUpload = apair.LastUpload
            game.AvgBattles = game.AvgBattles * 0.99 + 0.005 * (bots[0].Battles + bots[1].Battles)
            if game.Uploaders is None:
                uploaders = None
            else:
                uploaders = pickle.loads(zlib.decompress(game.Uploaders))
            if uploaders is None or len(uploaders) == 0:
                uploaders = {}
            uploaderName = results["user"]
            
            try:
                uploader = uploaders[uploaderName]
                uploader.latest = apair.LastUpload
                uploader.total += 1
            except KeyError:
                uploader = structures.User(name=uploaderName)
                uploaders[uploaderName] = uploader
            game.Uploaders = zlib.compress(pickle.dumps(uploaders,-1),1)
            
            for b in bots:
                try:
                    bUploaders = b.Uploaders
                    if uploaderName not in bUploaders:
                        bUploaders.append(uploaderName)
                except:
                    b.__dict__["Uploaders"] = [uploaderName]
                    
                    

            with sync_lock:
                for b in bots:
                    key = None
                    if isinstance(b,structures.BotEntry):
                        key = b.key().name()
                    else:
                        key = b.key_name
                    botsync[key] = botsync.get(key,0) + 1

            minSize = min(60,len(scores)/2)
            wrote = False

                        
            if len(botsync) > minSize and not write_lock.locked():# and time.time() > last_write_time + 20:
                
                with write_lock:
                    syncset = None
                    with sync_lock:
                        #last_write[syncname] = time.time()
                        syncset = botsync.keys()
                        #medianVal = numpy.median(botsync.values())
                        #if medianVal > 1:
                        #syncset = filter(lambda b: botsync[b] >= 2,syncset)
                    if len(syncset) >= min(10, len(scores)/2):
                        syncbotsDict = memcache.get_multi(syncset)
                        #botsDict.update(syncbotsDict)
                        with sync_lock:
                            syncbots = []
                            for sb in syncset:
                                b = syncbotsDict.get(sb,None)
                                
                                if b is None or b.PairingsList is None:
                                    botsync.pop(sb,1)
                                    syncbotsDict.pop(sb,1)
                                else:
                                    syncbots.append(b)
                                    botsync.pop(sb,1)
                                    
                    
                        try:
                            thisput = []
                            while len(syncbots) > 0:
                                b = syncbots.pop(-1)
                                
                                key = None
                                if isinstance(b,structures.BotEntry):
                                    key = b.key().name()
                                else:
                                    key = b.key_name                                
                                
                                putb = structures.BotEntry(key_name = key)
                                putb.init_from_cache(b)
                                thisput.append(putb)
    
                            db.put(thisput)
                            
                            logging.info("wrote " + str(len(thisput)) + " results to database")
                            for b in thisput:
                                s = b.key().name()
                                botsync.pop(s,1)
                                syncbotsDict.pop(s,1)
                            wrote = True
                            
                        except Exception, e:
                            logging.error('Failed to write data: '+ str(e))
                            #self.response.out.write('Failed to write data: '+ str(e.__class__))
                        
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
                    wrote = True
                    
            if newBot or wrote:
                game.put()
                #db.put(bots)
                memcache.delete("home")
            
            botsDict = {rumble:game} 
            global_dict[rumble] = game
            for b in bots:
                if isinstance(b,structures.BotEntry):
                    b = structures.CachedBotEntry(b)
                    
                key = b.key_name
                botsDict[key] = b
            memcache.set_multi(botsDict)

        
       # puttime = time.time() - scorestime - retrievetime - starttime
        scoreVals = scores.values()
        maxPairs = len(scoreVals) - 1           
        if game.PriorityBattles and ((not game.Melee) or 
        (random.random() < 0.0222 
        or bots[0].Pairings != maxPairs or bots[1].Pairings != maxPairs
        or min([bots[0].Battles,bots[1].Battles]) == min([b.Battles for b in scoreVals])
        )): # or min(bots, key = lambda b: b.Battles) < game.AvgBattles):
            #do a gradient descent to the lowest battled pairings:
            #1: take the bot of this pair which has less pairings/battles
            #2: find an empty pairing or take a low pairing
            #3: ????
            #4: PROFIT!!!
            
            priobot = None
            priopairs = None
            
            # this just does a gradient descent... let's do a direct search since we alread have the data

            priobot2 = None                                
            if bots[0].Pairings != maxPairs:
                priobot = bots[0]
                priopairs = pairingsarray[0]
            elif bots[1].Pairings != maxPairs:
                priobot = bots[1]
                priopairs = pairingsarray[1]
            elif not all([b.Pairings == maxPairs for b in scoreVals if b.Active]) :
                possBots = filter(lambda b: b.Pairings != maxPairs and b.Active,scoreVals)
                total = 0
                weighted = [(abs(maxPairs - b.Pairings),b) for b in possBots]
                for t in weighted:
                    total += t[0]
                running = 0
                point = random.randint(0,total-1)
                for t in weighted:
                    running += t[0]
                    if running > point:
                        priobot = t[1]
                        break
                        
                bhash = priobot.Name + "|" + rumble
                fullPrioBot = memcache.get(bhash)
                if fullPrioBot:
                    priopairs = pickle.loads(zlib.decompress(fullPrioBot.PairingsList))
                    logging.info("memcache lookup shortcut to local search")
                else:
                    priobot2 = random.choice(scoreVals).Name
                    catch = 10
                    while priobot2 == priobot.Name and catch > 0:
                        priobot2 = random.choice(scoreVals).Name
                        catch -= 1
                    if catch == 0:
                        priobot2 = None
                        logging.info("repeatedly found same bot for prio")
                    else:
                        logging.info("global min search successful for non-paired bot")
            else:
                minBattles = 1.1*min([b.Battles for b in scoreVals if b.Active])
                possBots = filter(lambda b: b.Battles <= minBattles and b.Active, scoreVals )
                
                names = [b.Name for b in possBots]
                if bots[1].Name not in names and bots[0].Name not in names:
                    priobot = random.choice(possBots)
                    priobot2 = random.choice(scoreVals).Name
                    catch = 10
                    while priobot2 == priobot.Name and catch > 0:
                        priobot2 = random.choice(scoreVals).Name
                        catch -= 1
                    if catch == 0:
                        priobot2 = None
                        logging.info("repeatedly found same bot for prio")
                    else:
                        logging.info("global min search successful for low-battled bot")
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
                        if p not in pairsdict and p != priobot.Name and scores[p].Active:
                            possPairs.append(p)
                            
                    if len(possPairs) > 0:
                        #choose a random new pairing to prevent overlap
                        priobot2 = random.choice(possPairs)
                        logging.info("successful local search for new pair")
                    else:
                        logging.info("unsuccessful local search for new pair")

                            
                                
                else:
                    #sort for lowest battled pairing
                    #priopairs = sorted(priopairs, key = lambda score: score.Battles)
                    minbat = min([p.Battles for p in priopairs if p.Name in scores and scores[p.Name].Active])
                    possPairs = filter(lambda p: p.Battles <= minbat + 1 and p.Name != priobot.Name and p.Name in scores and scores[p.Name].Active,priopairs)
                    if len( possPairs) > 0:
                        priobot2 = random.choice(possPairs).Name
                        logging.info("successful local search for low-battled pair")
                        #choose low battles, but still random - prevents lots of duplicates
                    else:
                        logging.info("unsuccessful local search for low-battled pair")
                    
                    
            if priobot is not None and priobot2 is not None:    
                priobots = [priobot.Name,priobot2]
                priobots = [b.replace(' ','_') for b in priobots]
                
                prio_string = "[" + string.join(priobots,",") + "]\n"
                #prio_string = "\nOK. A priority battle got sent back!"
                #q = taskqueue.Queue("priority-battles")
                #q.add(taskqueue.Task(payload=prio_string,method="PULL",tag=rumble))
                logging.info("adding priority battle: " + prio_string + ", " + rumble)
                
                rq_name = rumble + "|queue"
                try:
                    rumble_queue = global_dict[rq_name]
                    try:
                        rumble_queue.put_nowait(prio_string)
                        #logging.info("Added prio battles to queue: " + prio_string)
                    except Queue.Full:
                        #logging.info("Queue for priority battles full")
                        prio_string = None
                except KeyError:
                    logging.info("No queue for rumble " + rumble + ", adding one!")
                    global_dict[rq_name] = Queue.Queue(maxsize=300)
                    rumble_queue = global_dict[rq_name]
                    rumble_queue.put_nowait(prio_string)
            else:
                logging.info("no suitable priority battle found in " + rumble)
                if priobot is None:
                    logging.info("priobot is None")
                else:
                    logging.info("priobot2 is None")
        else:
            logging.info("no priority battle attempted for " + rumble)
       # priotime = time.time() - puttime - scorestime - retrievetime - starttime
        
        self.response.out.write("\nOK. " + bota + " vs " + botb + " received")
        

        #time.sleep(0.5)
        #self.response.out.write(" retrieve:" + str(int(round(retrievetime*1000))) + "ms")
        #self.response.out.write(" scores:" + str(int(round(scorestime*1000))) + "ms")
        #self.response.out.write(" priority battles:" + str(int(round(priotime*1000))) + "ms")
        #self.response.out.write(" put:" + str(int(round(puttime*1000))) + "ms")
        #self.response.out.write(", wrote " + str(syncsize) + " bots")
        #self.response.out.write(", " + str(len(sync)) + " bots waiting to write.")
        #self.response.out.write(", newBot: " + str(newBot))
        
        
        
#        if put_result is not None:
#            put_result.get_result()



application = webapp.WSGIApplication([
    ('/HandleQueuedResults', HandleQueuedResults)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
