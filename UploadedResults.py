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

import structures

allowed_clients = ["1.7.3.0","1.7.3.2","1.7.3.6"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
	def post(self):
		post_headers = self.request.headers
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
			
			user = structures.Uploader.get_by_key_name(user + "|" + version)
			
			rumble = results["game"]
			bota = results["fname"]
			botb = results["sname"]
			pd =   [[bota , botb ,rumble , uploader], 
						[botb ,bota , rumble , uploader],
						[bota , botb , rumble , structures.total],
						[botb , bota , rumble , structures.total]]
			pairHashes = [string.join(a,"|") for a in pd]
						
			pairs = structures.Pairing.get_by_key_name(pairHashes)
			for i = [0 1 2 3]:
				pair = pairs[i]
				if pair is None:
					pairs[i] = structures.Pairing(key_name = pairHashes[i],
						BotA = pd[i][0], BotB = pd[i][1], Rumble = pd[i][2],
						Uploader = pd[i][3], Battles = 0, APS = 0, Survival = 0)
				
			bd = [[botA, rumble], [botB, rumble]]
			
			botHashes = [string.join(a,"|") for a in bd]
				  
			bots = structures.BotEntry.get_by_key_name(botHashes)
			for i in [0 1 2 3]:
				bot = bots[i]
				if bot is None:
					bots[i] = structures.BotEntry(key_name = botHashes[i],
							Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0,
							PL = 0, Rumble = rumble, Active = True)				
						
			
			scorea = float(results["fscore"])
			scoreb = float(results["sscore"])
			APSa = 100*scorea/(scorea+scoreb)
			APSb = 100 - APSa
			
			survivala = float(results["fsurvival"])
			survivalb = float(results["ssurvival"])
			survivala = 100*survivala/(survivala+survivalb)
			survivalb = 100 - survivala
			
			uploaderBattles = pairs[0].Battles
			
			pairs[0].APS*= float(uploaderBattles)/(uploaderBattles + 1)
			pairs[0].APS += APSa/(uploaderBattles + 1)
			
			pairs[1].APS = 100 - pairs[0].APS
			
			pairs[0].Survival *= float(uploaderBattles)/(uploaderBattles + 1)
			pairs[0].Survival += survivala/(uploaderBattles + 1)
			
			pairs[1].Survival = 100 - pairs[0].Survival
			
			pairs[0].Battles += 1
			pairs[1].Battles += 1
			
			totalBattles = pairs[2].Battles
			botaPairs = float(bot[0].Pairings)
			botbPairs = float(bot[1].Pairings)
			if totalBattles == 0:
				bot[0].APS *= botaPairs/(botaPairs+1)
				bot[0].Survival *= botPairs/(botaPairs+1)
				bot[1].APS *= botbPairs/(botbPairs+1)
				bot[1].Survival *= botbPairs/(botbPairs+1)
			else:
				bot[0].APS -= pairs[2].APS/botaPairs
				bot[0].Survival -= pairs[2].Survival/botaPairs
				bot[1].APS -= pairs[3].APS/botbPairs
				bot[1].Survival -= pairs[3].Survival/botbPairs
				
			
			wasLoss = pairs[2].APS < 50.0
			pairs[2].APS *= float(totalBattles)/(totalBattles + 1)
			pairs[2].APS += APSa/(totalBattles+1)
			nowLoss = pairs[2].APS < 50.0
			
			if wasLoss and !nowLoss:
				bots[0].PL += 1
				bots[1].PL -= 1
			
			pairs[3].APS = 100 - pairs[2].APS
			
			pairs[2].Survival *= float(totalBattles)/(totalBattles + 1)
			pairs[2].Survival += survivala/(totalBattles+1)
			
			pairs[3].Survival = 100 - pairs[2].Survival
			

			if totalBattles == 0:	
				bot[0].APS += pairs[2].APS/(botaPairs+1)
				bot[0].Survival += pairs[2].Survival/(botaPairs+1)
				bot[1].APS += pairs[3].APS/(botbPairs+1)
				bot[1].Survival += pairs[3].Survival/(botbPairs+1)
				
				bot[0].Pairings += 1
				bot[1].Pairings += 1
			else:
				bot[0].APS += pairs[2].APS/botaPairs
				bot[0].Survival += pairs[2].Survival/botaPairs
				bot[1].APS += pairs[3].APS/botbPairs
				bot[0].Survival += pairs[3].Survival/botbPairs
			
			

			
			pairs[2].Battles += 1
			pairs[3].Battles += 1
			user.Battles += 1
			
			try:
				db.put(pairs)
				db.put(bots)
				db.put(user)
			except:
				self.response.out.write("ERROR PUTTING PAIRS DATA \r\n")

			
			
			self.response.out.write("OK." + post_body)
			
		else:
			self.response.out.write("CLIENT NOT SUPPORTED")


application = webapp.WSGIApplication([
	('/UploadedResults', UploadedResults)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
