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
			uploader = results["user"]
			
			user = memcache.get(uploader + "|" + client)
			if user is None:
				user = structures.Uploader.get_by_key_name(uploader + "|" + client)
				
			if user is None:
				user = structures.Uploader(key_name = uploader + "|" + client,
				Name = uploader, Version = version, TotalUploads = 0)
			
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
				
			
			bota = results["fname"]
			botb = results["sname"]
			
			bd = [[bota, rumble], [botb, rumble]]
			
			botHashes = [string.join(a,"|") for a in bd]
			botdict = memcache.get_multi(botHashes)
			bots = [botdict.get(h,None) for h in botHashes]
		
			for i in [0, 1]:
				if bots[i] is None:
					bots[i] = structures.BotEntry.get_by_key_name(botHashes[i])
					#if bots[i] is not None:
					#	memcache.set(botHashes[i], bots[i])
						
				if bots[i] is None:
					bots[i] = structures.BotEntry(key_name = botHashes[i],
							Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0.0,
							Survival = 0.0, PL = 0, Rumble = rumble, Active = True,
							PairingsList = pickle.dumps([]))
					game.Participants.append(bd[i][0])
					game.Participants = list(set(game.Participants))
					self.response.out.write("Added " + bd[i][0] + " to " + rumble + "\n")
					
			
			
			scorea = float(results["fscore"])
			scoreb = float(results["sscore"])
			APSa = 100*scorea/(scorea+scoreb)
			APSb = 100 - APSa
			
			survivala = float(results["fsurvival"])
			survivalb = float(results["ssurvival"])
			
			survivala = 100.0*survivala/game.Rounds
			survivalb = 100.0*survivalb/game.Rounds
			plista = None
			try:
				plista = pickle.loads(bots[0].PairingsList)
			except:
				plista = []
			#assert bots[0].Pairings == len(plista)
			
			try:
				plistb = pickle.loads(bots[1].PairingsList)
			except:
				plistb = []
				
			#assert bots[1].Pairings == len(plistb)
			
			apair = None
			for p in plista:
				if p.Name == botb:
					apair = p
			if apair is None:
				apair = structures.ScoreSet(name = botb)
				plista.append(apair)

			bpair = None
			for p in plistb:
				if p.name == bota:
					bpair = p
			if bpair is None:
				bpair = structures.ScoreSet(name = bota)
				plistb.append(bpair)
			
			
			botaPairs = bots[0].Pairings
			botbPairs = bots[1].Pairings
			
			totalBattles = apair.Battles
			if totalBattles == 0:
				bots[0].APS *= botaPairs/(botaPairs+1)
				bots[0].Survival *= botaPairs/(botaPairs+1)
				bots[1].APS *= botbPairs/(botbPairs+1)
				bots[1].Survival *= botbPairs/(botbPairs+1)
			else:
				bots[0].APS -= apair.APS/botaPairs
				bots[0].Survival -= apair.Survival/botaPairs
				bots[1].APS -= bpair.APS/botbPairs
				bots[1].Survival -= bpair.Survival/botbPairs
			
			
			
			wasLoss = apair.APS < 50.0
			apair.APS *= float(totalBattles)/(totalBattles + 1)
			apair.APS += APSa/(totalBattles+1)
			nowLoss = apair.APS < 50.0
			
			if wasLoss and not nowLoss:
				bots[0].PL += 1
				bots[1].PL -= 1
			
			bpair.APS = 100 - apair.APS
			
			apair.Survival *= float(totalBattles)/(totalBattles + 1)
			apair.Survival += survivala/(totalBattles+1)
			
			bpair.Survival *= float(totalBattles)/(totalBattles + 1)
			bpair.Survival += survivalb/(totalBattles+1)
			

			if totalBattles == 0:	
				bots[0].APS += APSa/(botaPairs+1)
				bots[0].Survival += survivala/(botaPairs+1)
				bots[1].APS += APSb/(botbPairs+1)
				bots[1].Survival += survivalb/(botbPairs+1)
				
				bots[0].Pairings += 1
				bots[1].Pairings += 1
			else:
				bots[0].APS += APSa/botaPairs
				bots[0].Survival += survivala/botaPairs
				bots[1].APS += APSb/botbPairs
				bots[1].Survival += survivalb/botbPairs
			
			
			participantsSet = set(game.Participants)
			
			for b in bots:
				b.Battles += 1
				if not b.Active:
					b.Active = True
					if b.Name not in participantsSet:
						game.Participants.append(b.Name)
						participantsSet.add(b.Name)
						
						
				b.LastUpload = datetime.datetime.now()

			user.TotalUploads += 1
			game.TotalUploads += 1
			
			user.LastUpload = datetime.datetime.now()
			
			pairingsarray = [plista,plistb]
			for i in [0,1]:
				b = bots[i]
				pairings = pairingsarray[i]
				while i < len(pairings):
					if pairings[i].Name not in participantsSet:
						pairings.pop(i)
						b.Pairings = len(pairings)
					i += 1
				b.PairingsList = pickle.dumps(pairings)
				
			self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
			
			if not game.Melee or 0.5*game.MeleeSize*(1 + game.MeleeSize)*random.random() < 1:
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
					priopair = plistb
				elif bots[0].Battles <= bots[1].Battles:
					priobot = bots[0]
					priopair = plista
				else:
					priobot = bots[1]
					priopair = plistb
				
				priobot2 = None
				if priobot.Pairings < len(game.Participants):
					#create the first battle of a new pairing
					pairsdict = {}
					for b in priopair:
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
					priopair = sorted(priopair, key = lambda score: score.Battles)
					pIndex = int(random.random()**3 * priobot.Pairings)
					priobot2 = priopair[pIndex]
					
				priobots = [priobot.Name,priobot2.Name]
				priobots = [b.replace(' ','_') for b in priobots]
				self.response.out.write("\n[" + string.join(priobots,",") + "]")

			for i in [0,1]:
				bots[i].PairingsList = pickle.dumps(pairingsarray[i])
			
			try:
				botdict = {}
				for b in bots:
					botdict[b.key().name()] = b
				memcache.set_multi(botdict)
				
				memcache.set(user.key().name(),user)
				memcache.set(game.Name,game)
				
				db.put(bots)
				user.put()
				game.put()
			except:
				self.response.out.write("ERROR PUTTING PAIRS DATA \r\n")
			
			self.response.out.write("\nOK. " + bota + " vs " + botb + " received")
			
			
		else:
			self.response.out.write("CLIENT NOT SUPPORTED")
		
		elapsed = time.time() - starttime
		self.response.out.write(" in " + str(int(round(elapsed*1000))) + "ms")


application = webapp.WSGIApplication([
	('/UploadedResults', UploadedResults)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
