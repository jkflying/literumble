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
from google.appengine.api import memcache

import structures

class RatingsFile(webapp.RequestHandler):
	def get(self):
		parts = self.request.query_string.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
			
		
		if "version" not in requests or requests["version"] != "1":
			return
			
		game = requests.get("game",None)
		
		if game is None:
			return
		
		rumble = memcache.get(game)
		if rumble is None:
			rumble = structures.Rumble.get_by_key_name(game)
			if rumble is not None:
				memcache.set(game,rumble)
		if rumble is None:
			return ""
			
		#botnames = rumble.Participants.split("|")
		#botHashes = [n + "|" + game for n in botnames]
		#botdict = memcache.get_multi(botHashes)
		#bots = [botdict.get(h,None) for h in botHashes]
		#hashesMissing = []
		#hmIndexes = []
		#for i in range(len(bots)):
			#if bots[i] is None:
				#hashesMissing.append(botHashes[i])
				#hmIndexes.append(i)
		#dbbots = structures.BotEntry.get_by_key_name(hashesMissing)
		
		#for i in range(len(dbbots)):
			#bots[hmIndexes[i]] = dbbots[i]
			#memcache.set(hashesMissing[i],dbbots[i])
		
		botNames = memcache.get(game + "|" + structures.participants)
		r = None
		if botNames is None or len(botNames) == 0 or (len(botNames) == 1 and botNames[0] == ""):
			botNames = None
			q = structures.BotEntry.all()
			q.filter("Rumble =",game)
			q.filter("Active =",True)
			r = q.run()
			#structures.prefetch_refprops(r,structures.BotEntry.Name, structures.BotEntry.APS, structures.BotEntry.Battles, structures.BotEntry.LastUpload)
		else:
			botNameList = botNames.split("|")
			botHashes = [b + "|" + game for b in botNameList]
			rdict = memcache.get_multi(botHashes)
			r = [rdict.get(h,None) for h in botHashes]
			missingHashes = []
			missingIndexes = []
			for i in range(len(r)):
				if r[i] is None:
					missingHashes.append(botHashes[i])
					missingIndexes.append(i)
			
			rmis = structures.BotEntry.get_by_key_name(missingHashes)
			for i in range(len(missingHashes)):
				r[missingIndexes[i]] = rmis[i]
				
			
		outstr = ""
		bots = {}
		botlist = []
		for bot in r:
			line = bot.Name + "=" + str(bot.APS) + "," + str(bot.Battles) + "," + str(bot.LastUpload) + "\n"
			outstr += line
			bots[bot.key().name()] = bot
			botlist.append(bot.Name)
			#memcache.set(bot.key().name(),bot)
		memcache.set_multi(bots)

		if botNames is None:
			memcache.set(game + "|" + structures.participants,botlist)
			rumble.Participants = string.join(botlist, "|")
			db.put(rumble)
			
		self.response.out.write(outstr)
		
class Rankings(webapp.RequestHandler):
	def get(self):
		starttime = time.time()
		parts = self.request.query_string.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
			
		game = requests.get("game",None)
		if game is None:
			self.response.out.write("NO RUMBLE SPECIFIED IN FORM game=____")
			return
		
		version = requests.get("version",None)
		if version is None or version != "1":
			self.response.out.write("VERSION NOT SPECIFIED AS version=1")
			return

		rumble = memcache.get(game)
		if rumble is None:
			rumble = structures.Rumble.get_by_key_name(game)
		if rumble is None:
			self.response.out.write("RUMBLE NOT FOUND")
			return
		

		botHashes = [b + "|" + game for b in rumble.Participants]
		rdict = memcache.get_multi(botHashes)
		r = [rdict.get(h,None) for h in botHashes]
		missingHashes = []
		missingIndexes = []
		for i in range(len(r)):
			if r[i] is None:
				missingHashes.append(botHashes[i])
				missingIndexes.append(i)
		
		rmis = structures.BotEntry.get_by_key_name(missingHashes)
		for i in range(len(missingHashes)):
			r[missingIndexes[i]] = rmis[i]

		for bot in r:
			line = bot.Name + "=" + str(bot.APS) + "," + str(bot.Battles) + "," + str(bot.LastUpload) + "\n"
			outstr += line

		self.response.out.write(outstr)
		
		if len(rmis) > 0:
			botsdict = {}
			for bot in rmis:
				botsdict[bot.key().name()] = bot
			memcache.set_multi(botsdict)
			
		self.response.out.write(outstr)
		


application = webapp.WSGIApplication([
	('/RatingsFile', RatingsFile)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
