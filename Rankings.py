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
			
		q = structures.BotEntry.all()
		q.filter("Rumble =",game)
		q.filter("Active =",True)
		
		#q.filter("Uploader =",structures.total) - Not needed as BotEntry is TOTAL only
		
		if lim == -1:
			lim = None
		else:
			q.order("-APS")
			
		r = q.fetch(limit = lim, offset = ofst)
		bots = []
		for bot in r:
			bots.append(bot)
		
		bots = sorted(bots, key=attrgetter(order), reverse=reverseSort)

		outstr = "<html>\n<body>RANKINGS - " + string.upper(game) + "<br>\n<table border=\"1\">\n<tr>"
		headings = ["Rank","Competitor","APS","PL","Survival","Pairings","Battles"]
		for heading in headings:
			outstr += "\n<th>" + heading + "</th>"
		outstr += "\n</tr>"
		rank = 1
		for bot in bots:
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


application = webapp.WSGIApplication([
	('/Rankings', Rankings)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
