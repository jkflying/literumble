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

class BatchRankings(webapp.RequestHandler):
	def get(self):
		starttime = time.time()

		q = structures.Rumble.all()
		
		for r in q.run():
			particHash = [p + "|" + r.Name for p in r.Participants]
			pairHash = [p + "|pairings" for p in particHash]
			ppDict = memcache.get_multi(particHash + pairHash)
			
			bots = [ppDict.get(h,None) for h in particHash]
			pairs = [ppDict.get(h,None) for h in pairHash]
			
			botsdict = {}


			missingHashes = []
			missingIndexes = []
			for i in xrange(len(bots)):
				if bots[i] is None or pairs[i] is None:
					missingHashes.append(particHash[i])
					missingIndexes.append(i)
			if len(missingHashes) > 0:
				bmis = structures.BotEntry.get_by_key_name(missingHashes)

				lost = False
				lostList = []
				for i in xrange(len(missingHashes)):
					if bmis[i] is not None:
						bots[missingIndexes[i]] = bmis[i]
						pairs[missingIndexes[i]] = bmis[i].PairingsList
						botsdict[missingHashes[i]] = bmis[i]
						botsdict[missingHashes[i] + "|pairings"] = bmis[i].PairingsList
						bmis[i].PairingsList = None
					else:
						bots[missingIndexes[i]] = None
						pairs[missingIndexes[i]] = None
						lostList.append(missingHashes[i])
						lost = True
				
			#if len(botsdict) > 0:		
			#	memcache.set_multi(botsdict)
			
			
			#i = 0
			#while i < len(bots):
				#if bots[i] is None or pairs[i] is None:
					#bots.pop(i)
					#pairs.pop(i)
				#i += 1
			bots = filter(lambda b: b is not None, bots)
			pairs = filter(lambda p: p is not None, pairs)
			
			botIndexes = {}
			for i,b in enumerate(bots):
				botIndexes[b.Name] = i
				b.VoteScore = 0.0
				
			for b,p in zip(bots,pairs):	
				pairdicts = json.loads(zlib.decompress(p))
				m = min(pairdicts,key = lambda a: a["APS"])
				if m["Name"] in botIndexes:
					bots[botIndexes[m["Name"]]].VoteScore += 1
			
			if len(bots) > 0:
				inv_len = 100.0/len(bots)
				
				for b in bots:
					b.PairingsList = None
					b.VoteScore *= inv_len
					botsdict[b.key().name()] = b
					
			if len(botsdict) > 0:
				memcache.set_multi(botsdict)
				
			
		elapsed = time.time() - starttime	
		self.response.out.write("Success in " + str(round(1000*elapsed)) + "ms")


application = webapp.WSGIApplication([
	('/BatchRankings', BatchRankings)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
