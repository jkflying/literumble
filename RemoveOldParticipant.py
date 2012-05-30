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
	name = name.replace("_"," ")
	
	rumble = memcache.get(game)
	if rumble is None:
		rumble = structures.Rumble.get_by_key_name(game)

	
	keyhash = name + "|" + game
	entry = memcache.get(keyhash)
	if entry is None:
		entry = structures.BotEntry.get_by_key_name(keyhash)
	if entry is None:
		return "ERROR. game does not exist: " + game
		
	entry.Active = False
	pset = set(rumble.Participants)#avoid duplicates etc - a bit of spring cleaning
	pset.discard(entry.Name)
	
	rumble.Participants = list(pset)
	
	memcache.delete("home")
	
	memcache.set(entry.key().name() + "|lite", structures.LiteBot(entry))
	memcache.set(entry.key().name(),entry)
	entry.put()
	
	memcache.set(game,rumble)
	rumble.put()
	
	return "OK. " + name + " retired from " + game

application = webapp.WSGIApplication([
	('/RemoveOldParticipant', RemoveOldParticipant)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
