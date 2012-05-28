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
		bots = None
		missingLite = False

		litebotHashes = [h + "|lite" for h in botHashes]
		lbdict = memcache.get_multi(litebotHashes)
		bots = [lbdict.get(h,None) for h in litebotHashes]


				
		if None in bots:
			missingHashes = []
			missingIndexes = []
			for i in xrange(len(bots)):
				if bots[i] is None:
					missingHashes.append(botHashes[i])
					missingIndexes.append(i)
			rdict = memcache.get_multi(missingHashes)
			for key in rdict:
				bots[missingIndexes[missingHashes.index(key)]] = rdict[key]
			missingLite = True
				
		r = bots
		missingHashes = []
		missingIndexes = []
		for i in xrange(len(r)):
			if r[i] is None:
				missingHashes.append(botHashes[i])
				missingIndexes.append(i)
		if len(missingHashes) > 0:
			rmis = structures.BotEntry.get_by_key_name(missingHashes)
			lost = False
			botsdict = {}
			for i in xrange(len(missingHashes)):
				if rmis[i] is not None:
					r[missingIndexes[i]] = rmis[i]
					botsdict[rmis[i].key().name()] = rmis[i]
				else:
					partSet = set(rumble.Participants)
					partSet.discard(missingHashes[i])
					rumble.Participants = list(partSet)
					memcache.set(game,rumble)
					rumble.put()
					lost = True
									
			memcache.set_multi(botsdict)
			if lost:
				r = filter(lambda b: b is not None, r)

		if missingLite:
			lbots = [structures.LiteBot(b) for b in r]
			lbotKeys = [b.Name + "|" + game + "|lite" for b in lbots]
			lbdict = {}
			for lbot, key in zip(lbots,lbotKeys):
				lbdict[key] = lbot
			memcache.set_multi(lbdict)
			
		out = []
		for bot in r:
			name = bot.Name
			name = name.replace(" ","_")
			line = name + "=" + str(bot.APS) + "," + str(bot.Battles) + "," + bot.LastUpload + "\n"
			out.append(line)

		self.response.out.write(string.join(out,""))
		


application = webapp.WSGIApplication([
	('/RatingsFile', RatingsFile)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
