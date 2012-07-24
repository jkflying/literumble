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
import cPickle as pickle
import zlib

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache

import structures
#from structures import global_dict
		
class RatingsFile(webapp.RequestHandler):
	def get(self):
		#global global_dict
		global_dict = {}
		
		starttime = time.time()
		parts = self.request.query_string.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
		
		game = requests.get("game",None)
		if game is None:
			self.response.out.write("NO RUMBLE SPECIFIED IN FORM game=____")
			return
		
		version = requests.get("version",None)
		if version is None or version != "1":
			self.response.out.write("VERSION NOT SPECIFIED AS version=1")
			return

		rumble = memcache.get(game)
		if rumble is None:
			rumble = global_dict.get(game,None)
			if rumble is None:
				rumble = structures.Rumble.get_by_key_name(game)
				if rumble is None:
					self.response.out.write("RUMBLE NOT FOUND")
					return
				else:
					global_dict[game]=rumble
					memcache.set(game,rumble)
		else:
			global_dict[game] = rumble
		
		try:
			botsdict = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
			r = botsdict.values()

		except:
			try:
				scoresdicts = json.loads(zlib.decompress(rumble.ParticipantsScores))
				scoreslist = [structures.LiteBot() for _ in scoresdicts]
				for s,d in zip(scoreslist,scoresdicts):
					s.__dict__.update(d)
				r = scoreslist #{s.Name:s for s in scoreslist}

			except:
				botHashes = [b + "|" + game for b in rumble.Participants]
				membots = [h for h in botHashes if h not in global_dict]
				botsdict = {}
				if len(membots) > 0:
					bdict = memcache.get_multi(membots)
					for key in bdict:
						if isinstance(bdict[key],structures.BotEntry):
							bdict[key] = structures.CachedBotEntry(bdict[key])
							botsdict[key] = bdict[key]
					#global_dict.update(bdict)
				r = [global_dict.get(h,None) for h in botHashes]

				missingHashes = []
				missingIndexes = []
				for i in xrange(len(r)):
					if r[i] is None:
						missingHashes.append(botHashes[i])
						missingIndexes.append(i)
				
				if len(missingHashes) > 0:
					rmis = structures.BotEntry.get_by_key_name(missingHashes)
					lost = False
					
					for i in xrange(len(missingHashes)):
						if rmis[i] is not None:
							cb = structures.CachedBotEntry(rmis[i])
							r[missingIndexes[i]] = cb
							botsdict[missingHashes[i]] = cb
						else:
							partSet = set(rumble.Participants)
							partSet.discard(missingHashes[i].split("|")[0])
							rumble.Participants = list(partSet)

							lost = True
											
					
					if lost:
						r = filter(lambda b: b is not None, r)
						global_dict[game] = rumble
						memcache.set(game,rumble)
						rumble.put()
				
				if len(botsdict) > 0:
					memcache.set_multi(botsdict)
					#global_dict.update(botsdict)
					
				scores = {}
				for b in r:
					scores[b.Name] = structures.LiteBot(b)
				rumble.ParticipantsScores = zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),1)
				#rumble.Participants = []
				global_dict[game] = rumble
				memcache.set(game,rumble)
				rumble.put()
			
		out = []
		for bot in r:
			name = bot.Name
			name = name.replace(" ","_")
			out.append(name)
			out.append("=")
			out.append(str(bot.APS))
			out.append(",")
			out.append(str(bot.Battles))
			out.append(",")
			out.append(bot.LastUpload)
			out.append("\n")
			#line = name + "=" + str(bot.APS) + "," + str(bot.Battles) + "," + bot.LastUpload + "\n"
			#out.append(line)

		self.response.out.write(''.join(out))
		


application = webapp.WSGIApplication([
	('/RatingsFile', RatingsFile)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
