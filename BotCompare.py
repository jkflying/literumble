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

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures

class BotCompare(webapp.RequestHandler):
	def get(self):
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
			
		game = requests.get("game",)
		if game is None:
			self.response.out.write("ERROR: RUMBLE NOT SPECIFIED IN FORMAT game=____")
			return
		
		botaName = requests.get("bota",None)
		if botaName is None:
			self.response.out.write("ERROR: BOT_A NOT SPECIFIED IN FORMAT bota=____")
			return
			
		botbName = requests.get("botb",None)
		if botbName is None:
			self.response.out.write("ERROR: BOT_B NOT SPECIFIED IN FORMAT botb=____")
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
		
		parsetime = time.time() - starttime
		
		cached = True
		keyhasha = botaName + "|" + game
		bota = memcache.get(keyhasha)
		if bota is None:
			bota = global_dict.get(keyhasha,None)
		else:
			global_dict[keyhasha] = bota
			
		if bota is None or bota.PairingsList is None:
			bota = structures.BotEntry.get_by_key_name(keyhasha)

			if bota is not None:
				
				memcache.set(keyhasha,bota)
				global_dict[keyhasha] = bota
				cached = False
				
		if bota is None:
			self.response.out.write("ERROR. name/game combination does not exist: " + botaName + "/" + game)
			#return
		else:	
		
		
			keyhashb = botbName + "|" + game
			botb = memcache.get(keyhashb)
			if botb is None:
				botb = global_dict.get(keyhashb,None)
			else:
				global_dict[keyhashb] = botb
				
			if botb is None or botb.PairingsList is None:
				botb = structures.BotEntry.get_by_key_name(keyhashb)

				if botb is not None:
					
					memcache.set(keyhashb,botb)
					global_dict[keyhashb] = botb
					cached = False
					
			if botb is None:
				self.response.out.write("ERROR. name/game combination does not exist: " + botbName + "/" + game)
				#return
			else:
				
				retrievetime = time.time() - parsetime - starttime
				
				botabots = None
				botbbots = None
				try:
					botabots = pickle.loads(zlib.decompress(bota.PairingsList))
				except:
					botsDicts = json.loads(zlib.decompress(botb.PairingsList))
					botabots = [structures.ScoreSet() for _ in botsDicts]
					for s,d in zip(botabots,botsDicts):
						s.__dict__.update(d)
				try:
					botbbots = pickle.loads(zlib.decompress(botb.PairingsList))
				except:
					botsDicts = json.loads(zlib.decompress(botb.PairingsList))
					botbbots = [structures.ScoreSet() for _ in botsDicts]
					for s,d in zip(botbbots,botsDicts):
						s.__dict__.update(d)
				
				#retrievetime = time.time() - parsetime - starttime
				
				#botabotsDict = {b.Name:b for b in botabots}
				botbbotsDict = {b.Name:b for b in botbbots}
				commonList = []
				for ba in botabots:
					if ba.Name in botbbotsDict:
						bb = botbbotsDict[ba.Name]
						commonList.append(structures.ComparePair(ba,bb))
				
				
				order = order.replace(" ","_")
				commonList = sorted(commonList, key=attrgetter(order), reverse=reverseSort)
				order = order.replace("_"," ")
				
				sorttime = time.time() - retrievetime - parsetime - starttime
				if order == "LastUpload":
					order = "Latest Battle"
				
				out = []
				
				gameHref = "<a href=Rankings?game=" + game + extraArgs + ">" + game + "</a>"
				out.append( "<html><head><title>LiteRumble - " + game + "</title></head>")
				out.append( "\n<body>Bot details of <b>" + botaName + " vs. " + botbName + "</b> in "+ gameHref + " vs. " + str(len(commonList)) + " bots.<br>")
				out.append("\n<table border=\"0\" bgcolor=\"#D0D0D0\">\n<tr bgcolor=\"F8F8F8\">")
				
				out.append("\n<th>Name</th>")
				out.append("\n<td>")
				out.append("<a href=BotDetails?game="+game+"&name=" + botaName.replace(" ","%20")+extraArgs+">"+botaName+"</a>")
				out.append("</td><td>")
				out.append("<a href=BotDetails?game="+game+"&name=" + botbName.replace(" ","%20")+extraArgs+">"+botbName+"</a>")
				
				out.append("</td></tr>")
				
				APSa = 0.0
				APSb = 0.0
				Survivala = 0.0
				Survivalb = 0.0
				Winsa = 0.0
				Winsb = 0.0
				
				for cp in commonList:
					APSa += cp.A_APS
					APSb += cp.B_APS
					Survivala += cp.A_Survival
					Survivalb += cp.B_Survival
					if cp.A_APS >= 50.0:
						Winsa += 1.0
					if cp.B_APS >= 50.0:
						Winsb += 1.0
				
				
				inv_len = 1.0/len(commonList)
				APSa *= inv_len
				APSb *= inv_len
				Survivala *= inv_len
				Survivalb *= inv_len
				Winsa *= 100*inv_len
				Winsb *= 100*inv_len
				
				out.append("\n<tr bgcolor=\"F8F8F8\"><th>Common APS</th>")
				out.append("\n<td>" + str(APSa) + "</td><td>" + str(APSb) + "</td></tr>")
				out.append("\n<tr bgcolor=\"F8F8F8\"><th>Common Survival</th>")
				out.append("\n<td>" + str(Survivala) + "</td><td>" + str(Survivalb) + "</td></tr>")
				out.append("\n<tr bgcolor=\"F8F8F8\"><th>Common PWin</th>")
				out.append("\n<td>" + str(Winsa) + "</td><td>" + str(Winsb) + "</td></tr>")
				out.append("\n</table>\n<br>\n<table border=\"0\" bgcolor=\"#D0D0D0\">\n<tr bgcolor=\"FFFFFF\">")
				
				

				out.append("\n<td colspan=\"2\"></td><th colspan=\"2\">" + botaName + "</td><th colspan=\"2\">" + botbName + "</td><td colspan=\"2\"></td></tr><tr>")
				
				headings = [
				"  ",
				"Name",
				"A APS",
				"A Survival",
				"B APS",
				"B Survival",
				"Diff APS",
				"Diff Survival"]
				
				for heading in headings:
					sortedBy = (order == heading)
					if sortedBy and reverseSort:
						heading = "-" + heading
						
					orderHref = "<a href=BotCompare?game="+game+"&bota="+botaName.replace(" ","%20")+"&botb="+botbName.replace(" ","%20")+"&order="+ heading.replace(" ","%20") + extraArgs + ">"+heading+"</a>"
					if sortedBy:
						orderHref = "<i>" + orderHref + "</i>"
					out.append(  "\n<th>" + orderHref + "</th>")
				out.append(  "\n</tr>")
				rank = 1
				highlightKey = [False,False,True,True,True,True,True,True]
				mins = [0,0,40,40,40,40,-0.1,-5]
				maxs = [0,0,60,60,60,60,0.1,5]
				for cp in commonList:
					if rank > lim:
						break

					botName=cp.Name
					botNameHref = "<a href=BotDetails?game="+game+"&name=" + botName.replace(" ","%20")+extraArgs+">"+botName+"</a>"
					cells = [
					str(rank),
					botNameHref,
					round(100.0*cp.A_APS)*0.01,
					round(100.0*cp.A_Survival)*0.01,
					round(100.0*cp.B_APS)*0.01,
					round(100.0*cp.B_Survival)*0.01,
					round(100.0*cp.Diff_APS)*0.01,
					round(100.0*cp.Diff_Survival)*0.01
					]
					if rank%2 == 0:
						color = "FFFFFF"
					else:
						color = "F8F8F8"
						
					out.append("\n	<tr bgcolor=" + color + ">")

					for i,cell in enumerate(cells):
						if highlightKey[i]:
							if cell < mins[i]:
								out.append(  "\n<td bgcolor=\"FF6600\">" + str(cell) + "</td>")
							elif cell > maxs[i]:
								out.append(  "\n<td bgcolor=\"99CC00\">" + str(cell) + "</td>")
							else:
								out.append(  "\n<td>" + str(cell) + "</td>")
						else:
							out.append(  "\n<td>" + str(cell) + "</td>")
					out.append( "\n</tr>")
					
					rank += 1
					
				out.append(  "</table>")
				htmltime = time.time() - sorttime - retrievetime - parsetime - starttime 
				elapsed = time.time() - starttime
				if timing:
					out.append(  "<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms. Bot cached: " + str(cached))
					out.append("\n<br> parsing: " + str(int(round(parsetime*1000))) )
					out.append("\n<br> retrieve: " + str(int(round(retrievetime*1000))) )
					out.append("\n<br> sort: " + str(int(round(sorttime*1000))) )
					out.append("\n<br> html generation: " + str(int(round(htmltime*1000))) )
				out.append(  "</body></html>")
				
				outstr = string.join(out,"")
					
				self.response.out.write(outstr)


application = webapp.WSGIApplication([
	('/BotCompare', BotCompare)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
