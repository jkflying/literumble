#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string
import pickle

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import random
import time
import zlib

import structures
from structures import global_dict

allowed_clients = ["1.7.3.0","1.7.3.2","1.7.3.6"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
	def post(self):
		global global_dict
		starttime = time.time()
		post_body = self.request.body
		
		sections = post_body.split('&')
		results = {}
		for pair in sections:
			ab = pair.split('=')
			results[ab[0]] = ab[1]
		
		client = results["client"]
		
		version = results["version"]
		if version in allowed_versions and client in allowed_clients:
			rumble = results["game"]
			game = global_dict.get(rumble,None)
			if game is None:
				game = memcache.get(rumble)
				if game is None:
					game = structures.Rumble.get_by_key_name(rumble)
				
			if game is None:
				game = structures.Rumble(key_name = rumble,
				Name = rumble, Rounds = int(results["rounds"]),
				Field = results["field"], Melee = bool(results["melee"] == "YES"),
				Teams = bool(results["teams"] == "YES"), TotalUploads = 0,
				MeleeSize = 10, Participants = [])
				self.response.out.write("CREATED NEW GAME TYPE " + rumble + "\n")
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
				
			newBot = False
			bota = results["fname"]
			botb = results["sname"]
			
			bd = [[bota, rumble], [botb, rumble]]
			
			botHashes = [string.join(a,"|") for a in bd]
			#botPairingsHashes = [h + "|pairings" for h in botHashes]
			syncname = rumble + "|" + structures.sync
			getHashes = botHashes + [syncname]
			getHashes = [h for h in getHashes]# if h not in global_dict]
			
			botdict = memcache.get_multi(getHashes)
			global_dict.update(botdict)
			
			bots = [global_dict.get(h,None) for h in botHashes]
			#pairsZip = [botdict.get(h,None) for h in botPairingsHashes]
			
			pairingsarray = [[],[]]
			for i in [0, 1]:
				if bots[i] is None or bots[i].PairingsList is None:
					bots[i] = structures.BotEntry.get_by_key_name(botHashes[i])
					#if bots[i] is not None:
					#	memcache.set(botHashes[i], bots[i])
						
				if bots[i] is None:
					bots[i] = structures.BotEntry(key_name = botHashes[i],
							Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0.0,
							Survival = 0.0, PL = 0, Rumble = rumble, Active = False,
							PairingsList = zlib.compress(json.dumps([]),5))
					newBot = True

				pairsDicts = json.loads(zlib.decompress(bots[i].PairingsList))

				pairingsarray[i] = [structures.ScoreSet() for _ in pairsDicts]
				for s,d in zip(pairingsarray[i],pairsDicts):
					s.__dict__.update(d)
				
				if not bots[i].Active:
					game.Participants.append(bd[i][0])
					game.Participants = list(set(game.Participants))
					bots[i].Active = True
					newBot = True
					self.response.out.write("Added " + bd[i][0] + " to " + rumble + "\n")
			
					
			retrievetime = time.time() - starttime
			
			scorea = float(results["fscore"])
			scoreb = float(results["sscore"])
			APSa = 100*scorea/(scorea+scoreb)
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
				
			participantsSet = set(game.Participants)
			for b, pairings in zip(bots, pairingsarray):
				i = 0
				while i < len(pairings):
					if pairings[i].Name not in participantsSet:
						pairings.pop(i)
				
					i += 1
				b.Pairings = len(pairings)
			
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
				#b = bots[i]
				#pairings = pairingsarray[i]
				dlist = [p.__dict__ for p in pairings]
				b.PairingsList = zlib.compress(json.dumps(dlist),4)
				
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

			#for b in bots:
				#b.Battles += 1
				#if not b.Active:
					#b.Active = True
					#if b.Name not in participantsSet:
						#game.Participants.append(b.Name)
						#participantsSet.add(b.Name)
						#newBot = True
						
				b.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			
			
			#user.TotalUploads += 1
			game.TotalUploads += 1
			
			#user.LastUpload = datetime.datetime.now()
			
				
			self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
			
			game.AvgBattles = game.AvgBattles * 0.99 + 0.005 * (bots[0].Pairings + bots[1].Pairings)
			
			scorestime = time.time() - retrievetime - starttime
			
			if game.PriorityBattles and ((not game.Melee and random.random() < 0.9) or min(pairingsarray, key = lambda plist: min(plist, key = lambda p: p.Battles)) < game.AvgBattles):
				#do a gradient descent to the lowest battled pairings
				#1: take the bot of this pair which has less pairings/battles
				#2: find an empty pairing or take a low pairing
				#3: ????
				#4: PROFIT!!!
				
				priobot = None
				priopairs = None
				if bots[0].Pairings < bots[1].Pairings:
					priobot = bots[0]
					priopairs = pairingsarray[0]
				elif bots[0].Pairings > bots[1].Pairings:
					priobot = bots[1]
					priopairs = pairingsarray[1]
				elif bots[0].Battles <= bots[1].Battles:
					priobot = bots[0]
					priopairs = pairingsarray[0]
				else:
					priobot = bots[1]
					priopairs = pairingsarray[1]
				
				priobot2 = None
				if priobot.Pairings < len(game.Participants):
					#create the first battle of a new pairing
					pairsdict = {}
					for b in priopairs:
						pairsdict[b.Name] = b
					possPairs = []
					for p in game.Participants:
						if p not in pairsdict and p != priobot.Name:
							possPairs.append(p)
					if len(possPairs) > 0:
						#pIndex = int(random.random() * (len(possPairs)-1))
						priobot2 = random.choice(possPairs)
							
								
				else:
					#find the lowest battled pairing
					priopairs = sorted(priopairs, key = lambda score: score.Battles)
					while priobot2 is None:
						pIndex = int(random.random()**3 * (priobot.Pairings-1))
						#more likely to choose low battles by cubic distribution, but random
						if priopairs[pIndex].Name != priobot.Name:
							priobot2 = priopairs[pIndex].Name
						
				if priobot is not None and priobot2 is not None:	
					priobots = [priobot.Name,priobot2]
					priobots = [b.replace(' ','_') for b in priobots]
					self.response.out.write("\n[" + string.join(priobots,",") + "]")
			

			priotime = time.time() - scorestime - retrievetime - starttime
			
			sync = global_dict.get(syncname,None)
			if sync is None:
				sync = {}
			else:
				try:
					sync = json.loads(zlib.decompress(sync))
				except:
					sync = {}
			
			for b in bots:
				key = b.key().name()
				sync[key] = sync.get(key,0) + 1

			uploadsize = None
			if game.Melee:
				uploadsize = game.MeleeSize -1
			else:
				uploadsize = 1000
			
			updates = min(len(sync),sorted(sync.values())[-min(len(sync),game.MeleeSize*10)])
				
			#memcache.set(user.key().name(),user)
			
			wrote = -1
			syncsize = -1
			if (game.Melee and updates >= uploadsize and len(sync) >= game.MeleeSize) or (not game.Melee and sum(sync.values()) > uploadsize):
				syncset = sync.keys()
				if game.Melee:
					syncset = filter(lambda b: sync[b] >= game.MeleeSize-1,syncset)
				else:
					syncset = filter(lambda b: sync[b] >= 3,syncset)
				#wrote = 0
				#syncbotsPairs = [b + "|pairings" for b in syncset]
				syncsetMem = [s for s in syncset if s not in global_dict]
				if len(syncsetMem) > 0:
					syncbotsDict = memcache.get_multi(syncsetMem)# + syncbotsPairs)
					global_dict.update(syncbotsDict)
				#syncbotsPairsDict = memcache.get_multi(syncbotsPairs)
				syncbots = []
				for sb in syncset:
					b = global_dict.get(sb,None)
					if b is not None:
						pl = b.PairingsList
						if pl is None:
							b = None
					if b is None:
						sync.pop(sb,1)
					else:
						syncbots.append(b)
						
				syncsize = len(syncbots)		

				sizelim = 800000
				try:
					while len(syncbots) > 0:
						size = 0
						thisput = []
						while len(syncbots) > 0:
							b = syncbots[-1]
							l = len(pickle.dumps(b,-1))
							if l+size > sizelim:
								break
							size += l
							syncbots.pop(-1)
							thisput.append(b)
							wrote += 1
						#try:
						db.put(thisput)
						for b in thisput:
							sync.pop(b.key().name(),1)
						#except:
						#	self.response.out.write("\nERROR WRITING DATA!! QUOTA REACHED?")
				except:
					self.response.out.write("\nERROR WRITING DATA!! QUOTA REACHED?")
					
			
			
			if newBot:
				game.put()
				db.put(bots)
				memcache.delete("home")
			elif game.BatchScoresAccurate:
				game.BatchScoresAccurate = False
				game.put()
			
			#memcache.set(game.Name,game)	
			#memcache.set(rumble + "|" + structures.sync,zlib.compress(json.dumps(sync),5))
			

			
			botdict = {rumble:game,rumble + "|" + structures.sync:zlib.compress(json.dumps(sync),5)}
			for b in bots:
				#botdict[b.key().name() + "|pairings"] = str(b.PairingsList)
				#b.PairingsList = None
				botdict[b.key().name()] = b
			
			global_dict.update(botdict)	
			memcache.set_multi(botdict)
			
			puttime = time.time() - priotime - scorestime - retrievetime - starttime
			
			self.response.out.write("\nOK. " + bota + " vs " + botb + " received")
			
			elapsed = time.time() - starttime
			self.response.out.write(" in " + str(int(round(elapsed*1000))) + "ms")
			#self.response.out.write(" retrieve:" + str(int(round(retrievetime*1000))) + "ms")
			#self.response.out.write(" scores:" + str(int(round(scorestime*1000))) + "ms")
			#self.response.out.write(" priority battles:" + str(int(round(priotime*1000))) + "ms")
			#self.response.out.write(" put:" + str(int(round(puttime*1000))) + "ms")
			#self.response.out.write(", wrote " + str(syncsize) + " bots")
			#self.response.out.write(", " + str(len(sync)) + " bots waiting to write.")
			
		else:
			self.response.out.write("CLIENT NOT SUPPORTED")
		



application = webapp.WSGIApplication([
	('/UploadedResults', UploadedResults)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
