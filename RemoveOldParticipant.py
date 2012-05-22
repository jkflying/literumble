#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
import time
from time import strftime
try:
    import json
except:
    import simplejson as json
import string

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

import structures

class RemoveOldParticipant(webapp.RequestHandler):
	def get(self):
		parts = self.request.query_string.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
		self.response.out.write(removeFromRumble(self,requests))
	
	def post(self):
		parts = self.request.body.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
		self.response.out.write(removeFromRumble(self,requests))
		

	def removeFromRumble(self,requests):
		if "version" not in requests or requests["version"] is not "1":
			return "ERROR. bad/no version"
			
			
		game = requests.get("game",None)
		if game is None:
			return "ERROR. no game specified"
			
			
		name = requests.get("name",None)
		if name is None:
			return "ERROR. no name specified"
			
		
		entry = structures.BotEntry.get_by_key_name(name + "|" + game)
		if entry is None:
			return "ERROR. name/game combination does not exist"
			
		entry.Active = False
		qa = structures.Pairing.all()
		qa.filter("BotA =",name)
		qa.filter("Rumble =",game)
		qa.filter("Active =",True)
		
		qb = structures.Pairing.all()
		qb.filter("BotB =",name)
		qb.filter("Rumble =",game)
		qb.filter("Active =",True)
		
		pairs = []
		for pair in qa.run():
			pairs.append(pair)
			pairs.Active = False
		
		opponentHashes = []
		modBots = []
		for pair in pairs:
			if pair.uploader == structures.total:
				opponentHashes.append(pair.BotB + "|" + rumble)
				
		opponentBots = structures.BotEntry.get_by_key_name(opponentHashes)
		for bot in opponentBots:
			if bot is not None:
				bot.APS -= pair.APS/bot.Pairings
				bot.APS *= float(bot.Pairings)/(bot.Pairings - 1)
				bot.Pairings -= 1
				bot.Battles -= pair.Battles
				modBots.append(bot)
			#else:
				#return "internal database structure error"
									
		for pair in qb.run():
			pairs.append(pair)
			pairs.Active = False

		db.put(pairs)
		db.put(modBots)
		entry.put()
		return "OK. " + name + " retired from " + game

application = webapp.WSGIApplication([
	('/RemoveOldParticipant', RemoveOldParticipant)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
