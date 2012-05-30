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

allowed_clients = ["1.7.3.0","1.7.3.2","1.7.3.6"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
	def post(self):
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
			
			game = memcache.get(rumble)
			if(game is None):
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
			botPairingsHashes = [h + "|pairings" for h in botHashes]
			botdict = memcache.get_multi(botHashes + botPairingsHashes)
			bots = [botdict.get(h,None) for h in botHashes]
			pairsZip = [botdict.get(h,None) for h in botPairingsHashes]
			
			pairingsarray = [[],[]]
			for i in [0, 1]:
				if bots[i] is None or pairsZip[i] is None:
					bots[i] = structures.BotEntry.get_by_key_name(botHashes[i])
					#if bots[i] is not None:
					#	memcache.set(botHashes[i], bots[i])
						
				if bots[i] is None:
					bots[i] = structures.BotEntry(key_name = botHashes[i],
							Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0.0,
							Survival = 0.0, PL = 0, Rumble = rumble, Active = False,
							PairingsList = zlib.compress(json.dumps([]),5))
					newBot = True
				
				pairsDicts = None
				if pairsZip[i] is None:
					pairsDicts = json.loads(zlib.decompress(bots[i].PairingsList))
				else:
					pairsDicts =  json.loads(zlib.decompress(pairsZip[i]))
				
				pairingsarray[i] = [structures.ScoreSet() for _ in pairsDicts]
				for s,d in zip(pairingsarray[i],pairsDicts):
					s.__dict__.update(d)
				
				if not bots[i].Active:
					game.Participants.append(bd[i][0])
					game.Participants = list(set(game.Participants))
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

			for b in bots:
				b.Battles += 1
				if not b.Active:
					b.Active = True
					if b.Name not in participantsSet:
						game.Participants.append(b.Name)
						participantsSet.add(b.Name)
						newBot = True
						
				b.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			
			
			#user.TotalUploads += 1
			game.TotalUploads += 1
			
			#user.LastUpload = datetime.datetime.now()
			
				
			self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
			
			game.__dict__["AvgBattles"] = game.__dict__.get("AvgBattles",0.0) * 0.99 + 0.005 * (bots[0].Pairings + bots[1].Pairings)
			
			scorestime = time.time() - retrievetime - starttime
			
			if not game.Melee or min(pairingsarray, key = lambda plist: min(plist, key = lambda p: p.Battles)) < game.AvgBattles:
				#do a gradient descent to the lowest battled pairings
				#1: take the bot of this pair which has less battles
				#2: find an empty pairing or take a low pairing
				#3: ????
				#4: PROFIT!!!
				
				priobot = None
				priopairs = None
				if bots[0].Pairings < bots[1].Pairings:
					priobot = bots[0]
					priopairs = plista
				elif bots[0].Pairings > bots[1].Pairings:
					priobot = bots[1]
					priopairs = plistb
				elif bots[0].Battles <= bots[1].Battles:
					priobot = bots[0]
					priopairs = plista
				else:
					priobot = bots[1]
					priopairs = plistb
				
				priobot2 = None
				if priobot.Pairings < len(game.Participants):
					#create the first battle of a new pairing
					pairsdict = {}
					for b in priopairs:
						pairsdict[b.Name] = b
					for p in game.Participants:
						b = pairsdict.get(p,None)
						if b is None:
							priobot2 = memcache.get(p + "|" + rumble)
							if priobot2 is None:
								priobot2 = structures.BotEntry.get_by_key_name(p + "|" + rumble)
							if priobot2 is not None and priobot2.Active:
								break
							else:
								self.response.out.write("\nERROR: Participants list points to nonexistant/retired bot " + p)
								
				else:
					#find the lowest battled pairing
					priopairs = sorted(priopairs, key = lambda score: score.Battles)
					pIndex = int(random.random()**3 * priobot.Pairings)
					priobot2 = priopair[pIndex]
					
				priobots = [priobot.Name,priobot2.Name]
				priobots = [b.replace(' ','_') for b in priobots]
				self.response.out.write("\n[" + string.join(priobots,",") + "]")
			

			priotime = time.time() - scorestime - retrievetime - starttime
			
			sync = memcache.get(rumble + "|" + structures.sync)
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
				uploadsize = 10*2 - 1
			
			updates = min(len(sync),sorted(sync.values())[-min(len(sync),uploadsize*3 + 3)])
				
			#memcache.set(user.key().name(),user)
			memcache.set(game.Name,game)
			wrote = -1
			syncsize = -1
			if (game.Melee and updates >= uploadsize and len(sync) >= game.MeleeSize) or (not game.Melee and len(sync) > uploadsize):
				syncset = sync.keys()
				#if game.Melee:
				#	syncset = filter(lambda b: sync[b] >= uploadsize,syncset)
				wrote = 0
				syncbotsDict = memcache.get_multi(syncset)
				syncbotsPairs = [b + "|pairings" for b in syncbotsDict.keys() if syncbotsDict[b].PairingsList is None]
				syncbotsPairsDict = memcache.get_multi(syncbotsPairs)
				syncbots = []
				for sb in syncbotsPairsDict:
					pl = syncbotsPairsDict.get(sb, None)
					if pl is None:
						pl = syncbotsDict[sb[:-9]].PairingsList
					if pl is None:
						sync.pop(sb,1)
					else:
						syncbotsDict[sb[:-9]].PairingsList = pl
						syncbots.append(syncbotsDict[sb[:-9]])
						
				syncsize = len(syncbotsPairs)		

				sizelim = 800000
				#try:
				while len(syncbots) > 0:
					size = 0
					thisput = []
					while len(syncbots) > 0:
						b = syncbots[-1]
						l = len(pickle.dumps(b,pickle.HIGHEST_PROTOCOL))
						if l+size > sizelim:
							break
						size += l
						syncbots.pop(-1)
						thisput.append(b)
						wrote += 1
						
					db.put(thisput)
					for b in thisput:
						sync.pop(b.key().name(),1)
				#except:
				#	self.response.out.write("\nOK. Out of quota. Will write when quota reset.")
					
			
			
			if newBot:
				game.put()
				memcache.delete("home")
			memcache.set(rumble + "|" + structures.sync,zlib.compress(json.dumps(sync),5))
			

			
			botdict = {}
			for b in bots:
				botdict[b.key().name() + "|pairings"] = b.PairingsList
				b.PairingsList = None
				botdict[b.key().name()] = b
				
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
