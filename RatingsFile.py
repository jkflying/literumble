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
			
		q = structures.BotEntry.all()
		q.filter("Rumble =",game)
		q.filter("Active =",True)

		outstr = ""
		for bot in q.run():
			line = bot.Name + "=" + str(bot.APS) + "," + str(bot.Battles) + "," + str(bot.LastUpload) + "\n"
			outstr += line

		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/RatingsFile', RatingsFile)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
