#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
import time
try:
    import json
except:
    import simplejson as json
import string

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from operator import attrgetter
import structures

class Rankings(webapp.RequestHandler):
	def get(self):
		starttime = time.time()
		parts = self.request.query_string.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
			
		game = requests.get("game","meleerumble")
		lim = int(requests.get("limit","-1"))
		ofst = int(requests.get("offset","0"))
		order = requests.get("order","APS")
		
		reverseSort = True
		if order[0] == "-":
			order = order[1:]
			reverseSort = False
			

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
		
		bots = []

		for bot in r:
			bots.append(bot)

		
		bots = sorted(bots, key=attrgetter(order), reverse=reverseSort)

		outstr = "<html>\n<body>RANKINGS - " + string.upper(game) + "<br>\n<table border=\"1\">\n<tr>"
		headings = ["  ","Competitor","APS","PL","Survival","Pairings","Battles"]
		for heading in headings:
			outstr += "\n<th>" + heading + "</th>"
		outstr += "\n</tr>"
		rank = 1
		for bot in bots:
			if rank > lim:
				break
			cells = [str(rank),bot.Name,bot.APS,bot.PL,bot.Survival,bot.Pairings,bot.Battles]
			line = "\n<tr>"
			for cell in cells:
				line += "\n<td>" + str(cell) + "</td>"
			line += "\n</tr>"
			
			outstr += line
			rank += 1
		outstr += "</table>"
		elapsed = time.time() - starttime
		outstr += "<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms"
		outstr += "</body></html>"
		self.response.out.write(outstr)
		
		if len(rmis) > 0:
			botsdict = {}
			for bot in rmis:
				botsdict[bot.key().name()] = bot
			memcache.set_multi(botsdict)
			
		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/Rankings', Rankings)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
