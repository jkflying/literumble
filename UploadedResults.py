#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache

import random

import structures

allowed_clients = ["1.7.3.0","1.7.3.2","1.7.3.6"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
	def post(self):
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
				MeleeSize = 10)
				self.response.out.write("CREATED NEW GAME TYPE " + rumble + "\n")
			else:
				field = game.Field == results["field"]
				rounds = (game.Rounds == int(results["rounds"]))
				teams = game.Teams == bool(results["teams"] == "YES")
				melee = game.Melee == bool(results["melee"] == "YES")
				allowed = field and rounds and teams and melee
				if not allowed:
					self.response.out.write("OK. ERROR. YOUR RUMBLE CONFIG DOES NOT MATCH RUMBLE NAME!!!")
					return
				
			
			bota = results["fname"]
			botb = results["sname"]
			
			bd = [[bota, rumble], [botb, rumble]]
			
			botHashes = [string.join(a,"|") for a in bd]
			botdict = memcache.get_multi(botHashes)
			bots = [botdict.get(botHashes[i],None) for i in [0,1]]
		
			for i in [0, 1]:
				if bots[i] is None:
					bots[i] = structures.BotEntry.get_by_key_name(botHashes[i])
					if bots[i] is not None:
						memcache.set(botHashes[i], bots[i])
						
				if bots[i] is None:
					bots[i] = structures.BotEntry(key_name = botHashes[i],
							Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0.0,
							Survival = 0.0, PL = 0, Rumble = rumble, Active = True)
					bq = structures.BotEntry.all()
					bq.filter("Rumble =",rumble)
					bq.filter("Active =", True)
					newpairs = []
					for b in bq.run():
						npd =   [[b.Name , bd[i][0] ,rumble , structures.total], 
								[bd[i][0] ,b.Name , rumble , structures.total]]
						npairHashes = [string.join(a,"|") for a in npd]
						p1 = structures.Pairing(key_name = npairHashes[0],
							BotA = b.Name, BotB = bd[i][0], Rumble = rumble, 
							Uploader = structures.total, Battles = 0, APS = 0.0, Survival = 0.0,
							Active = True)
						p2 = structures.Pairing(key_name = npairHashes[0],
							BotB = b.Name, BotA = bd[i][0], Rumble = rumble, 
							Uploader = structures.total, Battles = 0, APS = 0.0, Survival = 0.0,
							Active = True)
						newpairs.append(p1)
						newpairs.append(p2)
					npdict = {}
					for p in newpairs:
						npdict[p.key().name()] = p
					memcache.set_multi(npdict)
					db.put(newpairs)
					self.response.out.write("Added " + bd[i][0] + " to " + rumble)
					
			pd =   [[bota , botb ,rumble , uploader], 
						[botb ,bota , rumble , uploader],
						[bota , botb , rumble , structures.total],
						[botb , bota , rumble , structures.total]]
			pairHashes = [string.join(a,"|") for a in pd]
			
			pairsmemdict = memcache.get_multi(pairHashes)
			pairs = [pairsmemdict.get(pairHashes[i],None) for i in [0,1,2,3]]

			for i in [0, 1, 2, 3]:
				if pairs[i] is None:
					pairs[i] = structures.Pairing.get_by_key_name(pairHashes[i])
					if pairs[i] is not None:
						memcache.set(pairHashes[i],pairs[i])
				if pairs[i] is None:
					pairs[i] = structures.Pairing(key_name = pairHashes[i],
						BotA = pd[i][0], BotB = pd[i][1], Rumble = pd[i][2],
						Uploader = pd[i][3], Battles = 0, APS = 0.0, Survival = 0.0,
						Active = True)
				

			
			scorea = float(results["fscore"])
			scoreb = float(results["sscore"])
			APSa = 100*scorea/(scorea+scoreb)
			APSb = 100 - APSa
			
			survivala = float(results["fsurvival"])
			survivalb = float(results["ssurvival"])
			if survivala + survivalb > 0.0:
				survivala = 100.0*survivala/(survivala+survivalb)
				survivalb = 100.0 - survivala
			else:
				survivala = 50.0
				survivalb = 50.0
			uploaderBattles = pairs[0].Battles
			
			pairs[0].APS*= float(uploaderBattles)/(uploaderBattles + 1)
			pairs[0].APS += APSa/(uploaderBattles + 1)
			
			pairs[1].APS = 100 - pairs[0].APS
			
			pairs[0].Survival *= float(uploaderBattles)/(uploaderBattles + 1)
			pairs[0].Survival += survivala/(uploaderBattles + 1)
			
			pairs[1].Survival = 100 - pairs[0].Survival

			totalBattles = pairs[2].Battles
			botaPairs = float(bots[0].Pairings)
			botbPairs = float(bots[1].Pairings)
			if totalBattles == 0:
				bots[0].APS *= botaPairs/(botaPairs+1)
				bots[0].Survival *= botaPairs/(botaPairs+1)
				bots[1].APS *= botbPairs/(botbPairs+1)
				bots[1].Survival *= botbPairs/(botbPairs+1)
			else:
				bots[0].APS -= pairs[2].APS/botaPairs
				bots[0].Survival -= pairs[2].Survival/botaPairs
				bots[1].APS -= pairs[3].APS/botbPairs
				bots[1].Survival -= pairs[3].Survival/botbPairs
				
			
			wasLoss = pairs[2].APS < 50.0
			pairs[2].APS *= float(totalBattles)/(totalBattles + 1)
			pairs[2].APS += APSa/(totalBattles+1)
			nowLoss = pairs[2].APS < 50.0
			
			if wasLoss and not nowLoss:
				bots[0].PL += 1
				bots[1].PL -= 1
			
			pairs[3].APS = 100 - pairs[2].APS
			
			pairs[2].Survival *= float(totalBattles)/(totalBattles + 1)
			pairs[2].Survival += survivala/(totalBattles+1)
			
			pairs[3].Survival = 100 - pairs[2].Survival
			

			if totalBattles == 0:	
				bots[0].APS += pairs[2].APS/(botaPairs+1)
				bots[0].Survival += pairs[2].Survival/(botaPairs+1)
				bots[1].APS += pairs[3].APS/(botbPairs+1)
				bots[1].Survival += pairs[3].Survival/(botbPairs+1)
				
				bots[0].Pairings += 1
				bots[1].Pairings += 1
			else:
				bots[0].APS += pairs[2].APS/botaPairs
				bots[0].Survival += pairs[2].Survival/botaPairs
				bots[1].APS += pairs[3].APS/botbPairs
				bots[1].Survival += pairs[3].Survival/botbPairs
			
			
			for b in bots:
				b.Battles += 1
				b.Active = True
				b.LastUpload = datetime.datetime.now()
				
			for p in pairs:
				p.Battles += 1
				p.Active = True
				p.LastUpload = datetime.datetime.now()
			
			user.TotalUploads += 1
			game.TotalUploads += 1
			
			user.LastUpload = datetime.datetime.now()
			
			
			try:
				pairdict = {}
				for p in pairs:
					pairdict[p.key().name()] = p
				memcache.set_multi(pairdict)
				botdict = {}
				for b in bots:
					botdict[b.key().name()] = b
				memcache.set_multi(botdict)
				
				memcache.set(user.key().name(),user)
				memcache.set(game.key().name(),game)
				
				db.put(pairs)
				db.put(bots)
				user.put()
				game.put()
			except:
				self.response.out.write("ERROR PUTTING PAIRS DATA \r\n")
				
			self.response.out.write("<" + str(bots[0].Battles) + " " + str(bots[1].Battles) + ">")
			
			if (game.Melee and (game.MeleeSize*random.random())**2 < 1) or not game.Melee:
				#TODO: priority battles. can't do with current auto-add rumble. 
				#could make assumption that melee = 10 bots, and teams = 5, but not future compatible for things like 5vs5
				#Need to modify client to send meleesize=(int)
				#Or could set it manually for each rumble.
				bq = structures.BotEntry.all()
				bq.filter("Active =",True)
				bq.filter("Rumble =",rumble)
				bq.order("Battles")
				bq.order("Pairings")
				nextbot = None
				for b in bq.fetch(limit = 1):
					nextbot = b
				
				pq = structures.Pairing.all()
				pq.filter("Uploader =",structures.total)
				pq.filter("Active =",True)
				pq.filter("Rumble =",rumble)
				pq.filter("BotB =", nextbot.Name)
				pq.order("Battles")
				
				shortPairs = []
				for pair in pq.fetch(limit = 10):
					shortPairs.append(pair)
				if len(shortPairs) > 0:
					index = 0
					if len(shortPairs) > 1:
						index = random.randint(0,len(shortPairs)-1)
					
					priopair = shortPairs[index]
					priobots = [nextbot.Name, priopair.BotA]

					priobots = [b.replace(' ','_') for b in priobots]
					self.response.out.write("\n[" + string.join(priobots,",") + "]")

			
			self.response.out.write("\nOK. " + bota + " vs " + botb + " received.")

			
		else:
			self.response.out.write("CLIENT NOT SUPPORTED")


application = webapp.WSGIApplication([
	('/UploadedResults', UploadedResults)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
