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
		#if order == "Name":
			#reverseSort = not reverseSort

		rumble = memcache.get(game)
		if rumble is None:
			rumble = structures.Rumble.get_by_key_name(game)
			if rumble is not None:
				memcache.set(game,rumble)
		if rumble is None:
			self.response.out.write("RUMBLE NOT FOUND")
			return
		
		keyhash = name + "|" + game
		entry = memcache.get(keyhash)
		if entry is None:
			entry = structures.BotEntry.get_by_key_name(keyhash)
			if entry is not None:
				memcache.set(keyhash,entry)
		if entry is None:
			return "ERROR. name/game combination does not exist: " + name + " " + game
		
		bots = pickle.loads(zlib.decompress(entry.PairingsList))
			
		for b in bots:
			b.Survival = round(100.0*b.Survival)*0.01
			b.APS = round(100.0*b.APS)*0.01
			lastUpload = None
			try:
				lastUpload = b.LastUpload
			except:
				b.LastUpload = datetime.datetime.now()

		bots = sorted(bots, key=attrgetter(order), reverse=reverseSort)
		
				
		if order == "LastUpload":
			order = "Latest Battle"
		
		gameHref = "<a href=Rankings?game=" + game + extraArgs + ">" + game + "</a>"
		outstr = "<html><head><title>LiteRumble - " + game + "</head>"
		outstr += "\n<body>Bot details of <b>" + name + "</b> in "+ gameHref + " vs. " + str(len(bots)) + " bots.<br>\n<table border=\"1\">\n<tr>"

		headings = ["  ",
		"Name",
		"APS",
		"Survival",
		"Battles",
		"Latest Battle"]
		
		for heading in headings:
			if order == heading and reverseSort:
				heading = "-" + heading
				
			orderHref = botNameHref = "<a href=BotDetails?game="+game+"&name="+name.replace(" ","%20")+"&order="+ heading.replace(" ","%20") + extraArgs + ">"+heading+"</a>"
			outstr += "\n<th>" + orderHref + "</th>"
		outstr += "\n</tr>"
		rank = 1
		for bot in bots:
			if rank > lim:
				break

			botName=bot.Name
			botNameHref = "<a href=BotDetails?game="+game+"&name=" + botName.replace(" ","%20")+extraArgs+">"+botName+"</a>"
			cells = [str(rank),botNameHref,bot.APS,bot.Survival,bot.Battles,bot.LastUpload.strftime("%Y-%m-%d %H:%M:%S")]
			line = "\n<tr>"
			for cell in cells:
				line += "\n<td>" + str(cell) + "</td>"
			line += "\n</tr>"
			
			outstr += line
			rank += 1
			
		outstr += "</table>"
		elapsed = time.time() - starttime
		if timing:
			outstr += "<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms."
		outstr += "</body></html>"
		

			
		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/BotDetails', BotDetails)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
