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

import zlib
import pickle

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures

class BotDetails(webapp.RequestHandler):
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
			
		game = requests.get("game",)
		if game is None:
			self.response.out.write("ERROR: RUMBLE NOT SPECIFIED IN FORMAT game=____")
			return
		
		name = requests.get("name",None)
		if name is None:
			self.response.out.write("ERROR: BOT NOT SPECIFIED IN FORMAT name=____")
			return
		
		lim = int(requests.get("limit","10000000"))
		order = requests.get("order",None)
		timing = bool(requests.get("timing",False))
		
		
		extraArgs = ""
		
		
		if timing:
			extraArgs += "&timing=1"
		reverseSort = True
		
		if order is None:
			order = "Name"
			reverseSort = False
			
		elif order[0] == "-":
			order = order[1:]
			reverseSort = False
		if order == "Latest Battle":
			order = "LastUpload"
		
		parsetime = time.time() - starttime
		
		cached = True
		keyhash = name + "|" + game
		entry = memcache.get(keyhash)
		if entry is None:
			entry = structures.BotEntry.get_by_key_name(keyhash)
			if entry is not None:
				memcache.set(keyhash,entry)
				cached = False
		if entry is None:
			return "ERROR. name/game combination does not exist: " + name + " " + game
		bots = None
		try:
			botsDicts = json.loads(zlib.decompress(entry.PairingsList))
			bots = [structures.ScoreSet() for _ in xrange(len(botsDicts))]
			for s,d in zip(bots,botsDicts):
				s.__dict__.update(d)
		except:
			bots = pickle.loads(zlib.decompress(entry.PairingsList))
			for b in bots:
				if b.__dict__.get("LastUpload",None) is not None:
					b.LastUpload = b.LastUpload.strftime("%Y-%m-%d %H:%M:%S")
				else:
					b.__dict__["LastUpload"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
				
			dbots = [b.__dict__ for b in bots]
			entry.PairingsList = zlib.compress(json.dumps(dbots),4)
			memcache.set(keyhash,entry)
			#self.response.out.write("Updated to JSON")
		
		retrievetime = time.time() - parsetime - starttime
		
		for b in bots:
			b.Survival = round(100.0*b.Survival)*0.01
			b.APS = round(100.0*b.APS)*0.01
			lastUpload = None
			try:
				lastUpload = b.LastUpload
			except:
				b.LastUpload = datetime.datetime.now()

		bots = sorted(bots, key=attrgetter(order), reverse=reverseSort)
		
		sorttime = time.time() - retrievetime - parsetime - starttime
		if order == "LastUpload":
			order = "Latest Battle"
		
		out = []
		
		gameHref = "<a href=Rankings?game=" + game + extraArgs + ">" + game + "</a>"
		out.append( "<html><head><title>LiteRumble - " + game + "</title></head>")
		out.append( "\n<body>Bot details of <b>" + name + "</b> in "+ gameHref + " vs. " + str(len(bots)) + " bots.<br>\n<table border=\"1\">\n<tr>")

		headings = ["  ",
		"Name",
		"APS",
		"Survival",
		"Battles",
		"Latest Battle"]
		
		for heading in headings:
			sortedBy = order == heading
			if order == heading and reverseSort:
				heading = "-" + heading
				
			orderHref = botNameHref = "<a href=BotDetails?game="+game+"&name="+name.replace(" ","%20")+"&order="+ heading.replace(" ","%20") + extraArgs + ">"+heading+"</a>"
			if sortedBy:
				orderHref = "<i>" + orderHref + "</i>"
			out.append(  "\n<th>" + orderHref + "</th>")
		out.append(  "\n</tr>")
		rank = 1
		for bot in bots:
			if rank > lim:
				break

			botName=bot.Name
			botNameHref = "<a href=BotDetails?game="+game+"&name=" + botName.replace(" ","%20")+extraArgs+">"+botName+"</a>"
			cells = [str(rank),botNameHref,bot.APS,bot.Survival,bot.Battles,bot.LastUpload]
			out.append( "\n<tr>")
			for cell in cells:
				out.append(  "\n<td>" + str(cell) + "</td>")
			out.append( "\n</tr>")
			
			rank += 1
			
		out.append(  "</table>")
		htmltime = time.time() - sorttime - retrievetime - parsetime - starttime 
		elapsed = time.time() - starttime
		if timing:
			out.append(  "<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms. Bot cached: " + str(cached))
			out.append("\n<br> parsing: " + str(int(round(parsetime*1000))) )
			out.append("\n<br> retrieve: " + str(int(round(retrievetime*1000))) )
			out.append("\n<br> sort: " + str(int(round(sorttime*1000))) )
			out.append("\n<br> html generation: " + str(int(round(htmltime*1000))) )
		out.append(  "</body></html>")
		
		outstr = string.join(out,"")
			
		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/BotDetails', BotDetails)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
