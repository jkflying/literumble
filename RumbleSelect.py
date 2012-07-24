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
#from structures import global_dict
class RumbleSelect(webapp.RequestHandler):
	def get(self):
		#global global_dict
		global_dict = {}
		starttime = time.time()
		query = self.request.query_string
		query = query.replace("%20"," ")
		parts = query.split("&")
		requests = {}
		if parts[0] != "":
			for pair in parts:
				ab = pair.split('=')
				requests[ab[0]] = ab[1]
		
		timing = bool(requests.get("timing",False))
		regen = bool(requests.get("regen",False))
		
		
		extraArgs = ""
		
		
		if timing:
			extraArgs += "&timing=1"
		outstr = global_dict.get("home",None)
		if outstr is None and not regen:
			outstr = memcache.get("home")
		if outstr is None or regen:
			
			#gameHref = "<a href=Rankings?game=" + game + extraArgs + ">" + game + "</a>"
			out = []
			out.append("<html><head><title>LiteRumble - Home</title></head>LiteRumble - Home<br>\n")
			q = structures.Rumble.all()
			
			rumbles = [[],[],[]]
			categories = ["1v1","Melee","Teams"]
			
			for r in q.run():
				memr = memcache.get(r.Name)
				if memr is not None:
					r = memr
					
				if r.Melee:
					rumbles[1].append(r)
				elif r.Teams:
					rumbles[2].append(r)
				else:
					rumbles[0].append(r)
			
			for cat,rumbs in zip(categories,rumbles):
				for r in rumbs:
					try:
						scoresdicts = json.loads(zlib.decompress(r.ParticipantsScores))
						entries = len(scoresdicts)
#					print entries
#					try:
#						print "fun!"
					except:
						try:
							scores = pickle.loads(zlib.decompress(r.ParticipantsScores))
							entries = len(scores)
						except:
							entries = len(r.Participants)
					r.__dict__["entries"] = entries	
				rumbs.sort(key = lambda r: -r.__dict__["entries"])
				
				out.append(  "<table border=\"0\" bgcolor=\"#D0D0D0\">\n	<tr>")
				
				out.append(  "\n		<th colspan=\"2\">" + cat + "</th>\n		<th>Participants</th>\n	</tr>")
				
				for i,r in enumerate(rumbs):
					game = r.Name
					gameHref = "<a href=Rankings?game=" + game + extraArgs + ">" + game + "</a>"
					topHref = "<a href=Rankings?game=" + game +"&limit=50"+ extraArgs + ">top 50</a>"
					if i%2 == 0:
						color = "FFFFFF"
					else:
						color = "F8F8F8"
						
					out.append( "\n	<tr bgcolor=\"" + color + "\">\n		<td>" + gameHref + "</td>\n		<td>" + topHref + "</td>\n		<td align=\"center\">")
					out.append(str(r.__dict__["entries"]) + "</td>\n	</tr>")
					memcache.set(r.Name,r)
				out.append(  "\n	<br>\n	<br>")
			
			out.append(  "	</table>")
			outstr = string.join(out,"")
			if not timing:
				memcache.set("home",outstr)
			
		elapsed = time.time() - starttime
		if timing:
			outstr += "<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms."
		outstr += "</body></html>"

		self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/RumbleSelect', RumbleSelect),
	('/',RumbleSelect)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
