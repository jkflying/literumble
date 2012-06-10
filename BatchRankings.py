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
import cPickle as pickle
import math

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures
#from structures import global_dict

class BatchRankings(webapp.RequestHandler):
	def get(self):
		#global global_dict
		starttime = time.time()

		q = structures.Rumble.all()
		
		for r in q.run():
			if r.BatchScoresAccurate:
				continue
			memr = memcache.get(r.Name)
			if memr is not None:
				r = memr
			scores = pickle.loads(zlib.decompress(r.ParticipantsScores))
			
			particHash = [p + "|" + r.Name for p in scores]
			
			#memHash = [h for h in particHash if p not in global_dict]
			ppDict = memcache.get_multi(particHash)
			#global_dict.update(ppDict)
			
			bots = [ppDict.get(h,None) for h in particHash]
			
			botsdict = {}


			missingHashes = []
			missingIndexes = []
			for i in xrange(len(bots)):
				if bots[i] is None:
					missingHashes.append(particHash[i])
					missingIndexes.append(i)
				
				elif isinstance(bots[i],structures.BotEntry):
					bots[i] = structures.CachedBotEntry(bots[i])
					
			if len(missingHashes) > 0:
				bmis = structures.BotEntry.get_by_key_name(missingHashes)

				lost = False
				lostList = []
				for i in xrange(len(missingHashes)):
					if bmis[i] is not None:
						cb = structures.CachedBotEntry(bmis[i])
						bots[missingIndexes[i]] = cb
						botsdict[missingHashes[i]] = cb
						
					else:
						bots[missingIndexes[i]] = None
						lostList.append(missingHashes[i])
						lost = True
				if len(lostList) > 0:
					for l in lostList:
						scores.pop(l.split("|")[0],1)
					

			bots = filter(lambda b: b is not None, bots)
			
			botIndexes = {}
			for i,b in enumerate(bots):
				botIndexes[b.Name] = i
				b.VoteScore = 0.0
				b.__dict__["minScore"] = 100.0
				b.__dict__["maxScore"] = 0.0
				
			uzipPairs = {}
			uzipDictPairs = {}
			for b in bots:	
				try:
					pairings = pickle.loads(zlib.decompress(b.PairingsList))
				except:
					pairsDicts = json.loads(zlib.decompress(b.PairingsList))

					pairings = [structures.ScoreSet() for _ in pairsDicts]
					for s,d in zip(pairings,pairsDicts):
						s.__dict__.update(d)
				uzipPairs[b.Name] = pairings
				dictPairs = {}
				for p in pairings:
					dictPairs[p.Name] = p
				uzipDictPairs[b.Name] = dictPairs
				botsdict[b.Name] = b
				
			#Vote
			for b in bots:
				pairings = uzipPairs[b.Name]	
				minBot = min(pairings,key = lambda a: a.APS)
				if minBot.Name in botIndexes:
					bots[botIndexes[minBot.Name]].VoteScore += 1
			
			for b in bots:
				if b.Pairings > 0:
					b.VoteScore *= 100.0/b.Pairings
					
			
			#KNN PBI
			bots.sort(key = lambda b: b.APS, reverse = True)
			half_k = int(math.ceil(math.sqrt(len(bots))/2))
			for i,b in enumerate(bots):
				b = botsdict[b.Name]
				min_index = max(0,i-half_k)
				max_index = min(len(bots) - 1, i + half_k)
				knn = bots[min_index:max_index]
				pairings = uzipPairs[b.Name]
				for p in pairings:
					avgAPS = 0
					count = 0
					for compareBot in knn:
						pCompare = uzipDictPairs[compareBot.Name].get(p.Name,None)
						if pCompare is not None:
							avgAPS += pCompare.APS
							count += 1
					if count > 0:
						p.KNNPBI = p.APS - avgAPS/count 
			
			# Avg Normalised Pairing Percentage
			for b in bots:
				pairings = uzipPairs[b.Name]
				apsScores = [p.APS for p in pairings]
				b.__dict__["minScore"] = 100 - max(apsScores)
				b.__dict__["maxScore"] = 100 - min(apsScores)
			
			for b in bots:
				pairings = uzipPairs[b.Name]
				npps = 0.0
				count = 0
				for p in pairings:
					other = botsdict.get(p.Name,None)
					if other is not None:
						minS = other.__dict__["minScore"]
						maxS = other.__dict__["maxScore"]
						if maxS > minS:
							p.NPP = 100*(p.APS - minS)/(maxS-minS)
						else:
							p.NPP = p.APS
						npps += p.NPP
						count += 1
				if count > 0:
					b.ANPP = npps/count
				
			# save to cache
			botsdict = {}
			for b in bots:
				pairings = uzipPairs[b.Name]
				#b.PairingsList = zlib.compress(json.dumps([p.__dict__ for p in pairings]),4)
				b.PairingsList = zlib.compress(pickle.dumps(pairings,pickle.HIGHEST_PROTOCOL),4)
				b.__dict__.pop("minScore",1)
				b.__dict__.pop("maxScore",1)
				if b.Pairings > 0:
					botsdict[b.key_name] = b
			
			if len(botsdict) > 0:
				memcache.set_multi(botsdict)
				#global_dict.update(botsdict)
			
			scores = {b.Name: structures.LiteBot(b) for b in bots}
			
			r.ParticipantsScores = zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),7)
			
			r.BatchScoresAccurate = True
			memcache.set(r.Name,r)
			r.put()
			#gc.collect(2)
				
			
		elapsed = time.time() - starttime	
		self.response.out.write("Success in " + str(round(1000*elapsed)) + "ms")


application = webapp.WSGIApplication([
	('/BatchRankings', BatchRankings)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
