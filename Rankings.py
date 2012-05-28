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
from google.appengine.api import memcache
from operator import attrgetter
import structures

class Rankings(webapp.RequestHandler):
	def get(self):
		starttime = time.time()
		query = self.request.query_string
		query = query.replace("%20"," ")
		parts = query.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
			
		game = requests.get("game","meleerumble")
		lim = int(requests.get("limit","10000000"))
		ofst = int(requests.get("offset","0"))
		order = requests.get("order","APS")
		timing = bool(requests.get("timing",False))
		
		extraArgs = ""
		
		
		if timing:
			extraArgs += "&timing=1"
			
			
		reverseSort = True
		if order[0] == "-":
			order = order[1:]
			reverseSort = False
		if order == "Latest Battle":
			order = "LastUpload"
		elif order == "Competitor":
			order = "Name"
		
		parsing = time.time() - starttime
		
		rumble = memcache.get(game)
		if rumble is None:
			rumble = structures.Rumble.get_by_key_name(game)
		if rumble is None:
			self.response.out.write("RUMBLE NOT FOUND")
			return
			
		botHashes = [b + "|" + game for b in rumble.Participants]
		litebotHashes = [h + "|lite" for h in botHashes]
		lbdict = memcache.get_multi(litebotHashes)
		bots = [lbdict.get(h,None) for h in litebotHashes]
		missingLite = False
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
			
		missingHashes = []
		missingIndexes = []
		for i in xrange(len(bots)):
			if bots[i] is None:
				missingHashes.append(botHashes[i])
				missingIndexes.append(i)
		rmis = None
		if len(missingHashes) > 0:
			rmis = structures.BotEntry.get_by_key_name(missingHashes)
			lost = False
			botsdict = {}
			for i in xrange(len(missingHashes)):
				if rmis[i] is not None:
					bots[missingIndexes[i]] = rmis[i]
					botsdict[rmis[i].key().name()] = rmis[i]
				else:
					partSet = set(rumble.Participants)
					partSet.discard(missingHashes[i])
					rumble.Participants = list(partSet)
					memcache.set(game,rumble)
					rumble.put()
					lost = True
			missingLite = True	
			memcache.set_multi(botsdict)
			if lost:
				bots = filter(lambda b: b is not None, bots)
		
		lbots = None
		if missingLite:
			lbots = [structures.LiteBot(b) for b in bots]
			lbotKeys = [b.Name + "|" + game + "|lite" for b in lbots]
			lbdict = {}
			for lbot, key in zip(lbots,lbotKeys):
				lbdict[key] = lbot
			memcache.set_multi(lbdict)
		else:
			lbots = bots
			
		retrievetime = time.time() - starttime - parsing
		
		for b in lbots:
			b.PWIN = round(1000.0*float(b.PL)/b.Pairings)*0.05 + 50
			b.Survival = round(100.0*b.Survival)*0.01
			b.APS = round(100.0*b.APS)*0.01
			
		
		bots = sorted(lbots, key=attrgetter(order), reverse=reverseSort)
		
		sorttime = time.time() - parsing - retrievetime - starttime
		
		if	order == "LastUpload":
			order = "Latest Battle"
		elif order == "Name":
			order = "Competitor"
		out = []
		out.append("<html><head><title>LiteRumble - " + game + "</title></head>")
		out.append("\n<body>RANKINGS - " + string.upper(game) + " WITH " + str(len(rumble.Participants)) + " BOTS<br>\n<table border=\"1\">\n<tr>")
		headings = ["  ","Competitor","APS","PWIN","Survival","Pairings","Battles","Latest Battle"]
		for heading in headings:
			sortedBy = order == heading
			if order == heading and reverseSort:
				heading = "-" + heading
				
			orderHref = "<a href=Rankings?game="+game+"&order="+ heading.replace(" ","%20") + extraArgs + ">"+heading+"</a>"
			if sortedBy:
				orderHref = "<i>" + orderHref + "</i>"
			out.append( "\n<th>" + orderHref + "</th>")
		out.append("\n</tr>")
		rank = 1
		for bot in bots:
			if rank > lim:
				break
				
			botName=bot.Name
			botNameHref = "<a href=BotDetails?game="+game+"&name=" + botName.replace(" ","%20")+extraArgs+">"+botName+"</a>"
			
			cells = [str(rank),botNameHref,bot.APS,bot.PWIN,bot.Survival,bot.Pairings,bot.Battles,bot.LastUpload]
			out.append("\n<tr>")
			for cell in cells:
				out.append( "\n<td>" + str(cell) + "</td>")
			out.append("\n</tr>")
			
			rank += 1
			
		out.append( "</table>")
		htmltime = time.time() - parsing - retrievetime - sorttime - starttime
		
		elapsed = time.time() - starttime
		if timing:
			out.append( "\n<br> Page served in " + str(int(round(elapsed*1000))) + "ms. " + str(len(missingHashes)) + " bots retrieved from datastore.")
			if missingLite:
				out.append(" Bots without participants cached for quick load.")
			out.append("\n<br> parsing: " + str(int(round(parsing*1000))) )
			out.append("\n<br> retrieve: " + str(int(round(retrievetime*1000))) )
			out.append("\n<br> sort: " + str(int(round(sorttime*1000))) )
			out.append("\n<br> html generation: " + str(int(round(htmltime*1000))) )
		out.append( "</body></html>")
		
		outstr = string.join(out,"")
			
		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/Rankings', Rankings)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
