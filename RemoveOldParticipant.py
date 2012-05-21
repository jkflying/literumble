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
			
		
		if "version" not in requests or requests["version"] is not "1":
			self.response.out.write("ERROR. bad/no version")
			return
			
		game = requests.get("game",None)
		if game is None:
			self.response.out.write("ERROR. no game specified")
			return
			
		name = requests.get("name",None)
		if name is None:
			self.response.out.write("ERROR. no name specified")
			return
		
		entry = structures.BotEntry.get_by_key_name(name + "|" + game)
		if entry is None:
			self.response.out.write("ERROR. name/game combination does not exist")
			return
		
		entry.Active = False
		
		entry.put()
		self.response.out.write("OK. " + name + " retired from " + game)
	
	def post(self):
		parts = self.request.body.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
			
		
		if "version" not in requests or requests["version"] is not "1":
			self.response.out.write("ERROR. bad/no version")
			return
			
		game = requests.get("game",None)
		if game is None:
			self.response.out.write("ERROR. no game specified")
			return
			
		name = requests.get("name",None)
		if name is None:
			self.response.out.write("ERROR. no name specified")
			return
		
		entry = structures.BotEntry.get_by_key_name(name + "|" + game)
		if entry is None:
			self.response.out.write("ERROR. name/game combination does not exist")
			return
		
		entry.Active = False
		
		entry.put()
		self.response.out.write("OK. " + name + " retired from " + game)


application = webapp.WSGIApplication([
	('/RemoveOldParticipant', RemoveOldParticipant)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
