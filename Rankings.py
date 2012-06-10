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
import cPickle as pickle

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures
import zlib
from structures import global_dict
class Rankings(webapp.RequestHandler):
	def get(self):
		global global_dict
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
		if len(order) == 0:
			order = "APS"
		if order[0] == "-":
			order = order[1:]
			reverseSort = False
		if order == "Latest Battle":
			order = "LastUpload"
		elif order == "Competitor":
			order = "Name"
		elif order == "Vote":
			order = "VoteScore"
			
		parsing = time.time() - starttime
		rumble = global_dict.get(game)
		if rumble is None:
			rumble = memcache.get(game)
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
			bots = botsdict.values()
			#if len(rumble.Participants) > 0:
				#rumble.Participants = []
				#rumble.put()
		#try:
		#	print "hello"
		except:
			print "decompressed unsuccessfully"
			botHashes = [b + "|" + game for b in rumble.Participants]
			membots = [h for h in botHashes if h not in global_dict]
			if len(membots) > 0:
				bdict = memcache.get_multi(membots)
				global_dict.update(bdict)
			bots = [global_dict.get(h,None) for h in botHashes]
			
			botsdict = {}	
			
			missingHashes = []
			missingIndexes = []
			for i,b in enumerate(bots):
				if b is None:
					missingHashes.append(botHashes[i])
					missingIndexes.append(i)
				elif isinstance(b,structures.BotEntry):
					bots[i] = structures.CachedBotEntry(b)
					botsdict[bots[i].key_name] = bots[i]
			
			rmis = None
			if len(missingHashes) > 0:
				rmis = structures.BotEntry.get_by_key_name(missingHashes)
				lost = False
				
				for i in xrange(len(missingHashes)):
					if rmis[i] is not None:
						bots[missingIndexes[i]] = structures.CachedBotEntry(rmis[i])
						botsdict[missingHashes[i]] = bots[missingIndexes[i]]
					else:
						partSet = set(rumble.Participants)
						partSet.discard(missingHashes[i].split("|")[0])
						rumble.Participants = list(partSet)

						lost = True
						
				
				if lost:
					bots = filter(lambda b: b is not None, bots)
					global_dict[game] = rumble
					memcache.set(game,rumble)
					rumble.put()
					
			if len(botsdict) > 0:
				#global_dict.update(botsdict)
				memcache.set_multi(botsdict)
			scores = {}
			for b in bots:
				scores[b.Name] = structures.LiteBot(b)
			rumble.ParticipantsScores = zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),1)
			#rumble.Participants = []
			global_dict[game] = rumble
			memcache.set(game,rumble)
			rumble.put()
			
		retrievetime = time.time() - starttime - parsing
		#newbots = []
		for b in bots:
			b.PWIN = 50.0*float(b.PL)/b.Pairings + 50.0
			
			if b.VoteScore is None:
				b.VoteScore = 0
			if b.ANPP is None:
				b.ANPP = 0
		
		get_key = attrgetter(order)
		
		bots.sort( key=lambda b: get_key(b), reverse=reverseSort)
		
		sorttime = time.time() - parsing - retrievetime - starttime
		
		if	order == "LastUpload":
			order = "Latest Battle"
		elif order == "Name":
			order = "Competitor"
		elif order == "VoteScore":
			order = "Vote"
		out = []
		out.append("<html>\n<head>\n	<title>LiteRumble - " + game + "</title>\n</head>")
		out.append("\n<body>RANKINGS - " + string.upper(game) + " WITH " + str(len(bots)) + " BOTS<br>\n<table border=\"1\">\n	<tr>")
		headings = ["","Competitor","APS","PWIN","ANPP","Vote","Survival","Pairings","Battles","Latest Battle"]
		for heading in headings:
			sortedBy = order == heading
			if order == heading and reverseSort:
				heading = "-" + heading
			orderl = []
			orderl.append("<a href=Rankings?game=")
			orderl.append(game)
			orderl.append("&order=")
			orderl.append(heading.replace(" ","%20"))
			orderl.append(extraArgs)
			orderl.append(">")
			orderl.append(heading)
			orderl.append("</a>")
			orderHref = ''.join(orderl)
			if sortedBy:
				orderHref = "<i>" + orderHref + "</i>"
			out.append( "\n		<th>" + orderHref + "</th>")
		out.append("\n	</tr>")
		rank = 1
		for bot in bots:
			if rank > lim:
				break
				
			botName=bot.Name
			bnh = []
			bnh.append("<a href=BotDetails?game=")
			bnh.append(game)
			bnh.append("&name=")
			bnh.append(botName.replace(" ","%20"))
			bnh.append(extraArgs)
			bnh.append(">")
			bnh.append(botName)
			bnh.append("</a")
			botNameHref = ''.join(bnh) #"<a href=BotDetails?game="+game+"&name=" + botName.replace(" ","%20")+extraArgs+">"+botName+"</a>"
			
			cells = [str(rank),botNameHref,
				round(100.0*bot.APS)*0.01,
				round(100.0*bot.PWIN)*0.01,
				round(100.0*bot.ANPP)*0.01,
				round(100.0*bot.VoteScore)*0.01,
				round(100.0*bot.Survival)*0.01,
				bot.Pairings,bot.Battles,bot.LastUpload]
			out.append("\n	<tr>")
			for cell in cells:
				out.append( "\n		<td>")
				out.append(str(cell))
				out.append("</td>")
			out.append("\n	</tr>")
			del bot.PWIN
			rank += 1
			
		out.append( "</table>")
		htmltime = time.time() - parsing - retrievetime - sorttime - starttime
		
		elapsed = time.time() - starttime
		if timing:
			out.append( "\n<br> Page served in " + str(int(round(elapsed*1000))) + "ms. ")# + str(len(missingHashes)) + " bots retrieved from datastore.")
			out.append("\n<br> parsing: " + str(int(round(parsing*1000))) )
			out.append("\n<br> retrieve: " + str(int(round(retrievetime*1000))) )
			out.append("\n<br> sort: " + str(int(round(sorttime*1000))) )
			out.append("\n<br> html generation: " + str(int(round(htmltime*1000))) )
		out.append( "</body></html>")
		
		outstr = ''.join(out)
			
		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/Rankings', Rankings)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
