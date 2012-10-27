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

class BotDetails(webapp.RequestHandler):
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
        
        name = requests.get("name",None)
        if name is None:
            self.response.out.write("ERROR: BOT NOT SPECIFIED IN FORMAT name=____")
            return
        
        lim = int(requests.get("limit","10000000"))
        order = requests.get("order",None)
        timing = bool(requests.get("timing",False))
        
        
        extraArgs = ""
        
        
        if timing:
            extraArgs += "&amp;timing=1"
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
        keyhash = name + "|" + game
        bot = memcache.get(keyhash)
        if bot is None:
            bot = global_dict.get(keyhash,None)
        else:
            global_dict[keyhash] = bot
            
        if bot is None or bot.PairingsList is None:
            bot = structures.BotEntry.get_by_key_name(keyhash)

            if bot is not None:
                
                memcache.set(keyhash,bot)
                global_dict[keyhash] = bot
                cached = False
                
        if bot is None:
            self.response.out.write( "ERROR. name/game combination does not exist: " + name + "/" + game)
        else:
            bots = None

            try:
                botsDicts = json.loads(zlib.decompress(bot.PairingsList))
                bots = [structures.ScoreSet() for _ in botsDicts]
                for s,d in zip(bots,botsDicts):
                    s.__dict__.update(d)
            except:
                bots = pickle.loads(zlib.decompress(bot.PairingsList))

            
            retrievetime = time.time() - parsetime - starttime
            
            for b in bots:
                lastUpload = None
                try:
                    lastUpload = b.LastUpload
                except:
                    b.LastUpload = datetime.datetime.now()

            bots = sorted(bots, key=attrgetter(order), reverse=reverseSort)
            
            sorttime = time.time() - retrievetime - parsetime - starttime
            if order == "LastUpload":
                order = "Latest Battle"
            
            out = []
            
            gameHref = "<a href=\"Rankings?game=" + game + extraArgs + "\">" + game + "</a>"
            gameTitle = "Bot details of <b>" + name + "</b> in "+ gameHref + " vs. " + str(len(bots)) + " bots."
            
            out.append(html_header % (game,gameTitle))
            out.append("<table>\n")
            out.append("<tr>\n<th>Name</th>\n<td>\n" + name + "</td></tr>")
            out.append("<tr>\n<th>APS</th>\n<td>\n" + str(bot.APS) + "</td></tr>")
            out.append("<tr>\n<th>PWIN</th>\n<td>\n" + str(50.0*float(bot.PL)/bot.Pairings + 50.0) + "</td></tr>")
            out.append("<tr>\n<th>ANPP</th>\n<td>\n" + str(bot.ANPP) + "</td></tr>")
            out.append("<tr>\n<th>Vote</th>\n<td>\n" + str(bot.VoteScore) + "</td></tr>")
            out.append("<tr>\n<th>Survival</th>\n<td>\n" + str(bot.Survival) + "</td></tr>")
            out.append("<tr>\n<th>Pairings</th>\n<td>\n" + str(bot.Pairings) + "</td></tr>")
            out.append("<tr>\n<th>Battles</th>\n<td>\n" + str(bot.Battles) + "</td></tr>")
            out.append("<tr>\n<th>Latest Battle</th>\n<td>\n" + str(bot.LastUpload) + " UTC</td></tr>")
            out.append("<tr>\n<td colspan=\"2\">")
            out.append("<form name=\"input\" action=\"BotCompare\" method=\"get\">")
            out.append("<input type=\"hidden\" name=\"game\" value=\"" + game+ "\" />")
            out.append("<input type=\"hidden\" name=\"bota\" value=\"" + name + "\" />")
            out.append("<input type=\"text\" name=\"botb\" value=\"" + name + "\" />")
            out.append("<input type=\"submit\" value=\"Compare\" /></form>")
            out.append("</td></tr></table>\n<table>\n")

            headings = ["  ",
            "Name",
            "",
            "APS",
            "NPP",
            "Survival",
            "KNNPBI",
            "Battles",
            "Latest Battle"]
            
            for heading in headings:
                sortedBy = (order == heading)
                headinglink = heading
                if sortedBy and reverseSort:
                    heading = "-" + heading
                    headinglink = heading
                elif not sortedBy:
                    headinglink = "-" + headinglink
                    
                orderHref = "<a href=\"BotDetails?game="+game+"&amp;name="+name.replace(" ","%20")+"&amp;order="+ headinglink.replace(" ","%20") + extraArgs + "\">"+heading+"</a>"
                if sortedBy:
                    out.append(  "\n<th class=\"sortedby\">" + orderHref + "</th>")
                else:
                    out.append(  "\n<th>" + orderHref + "</th>")
            out.append(  "\n</tr>")
            rank = 1
            highlightKey = [False,False,False,True,True,True,True,False,False]
            mins = [0,0,0,40,40,40,-0.1,0,0]
            maxs = [0,0,0,60,70,60,0.1,0,0]
            for bot in bots:
                if rank > lim:
                    break

                botName=bot.Name
                botNameHref = "<a href=\"BotDetails?game="+game+"&amp;name=" + botName.replace(" ","%20")+extraArgs+"\">"+botName+" </a>"
                compareHref = "<a href=\"BotCompare?game="+game+"&amp;bota=" + name.replace(" ","%20") + "&amp;botb=" + botName.replace(" ","%20") + extraArgs + "\"> compare</a>"
                cells = [str(rank),
                botNameHref,
                compareHref,
                round(100.0*bot.APS)*0.01,
                round(100.0*bot.NPP)*0.01,
                round(100.0*bot.Survival)*0.01,
                round(100.0*bot.KNNPBI)*0.01,
                bot.Battles,
                bot.LastUpload]
                
                out.append("\n<tr>")
                for i,cell in enumerate(cells):
                    if highlightKey[i]:
                        if cell < mins[i]:
                            out.append(  "\n<td class=\"red\">" + str(cell) + "</td>")
                        elif cell > maxs[i]:
                            out.append(  "\n<td class=\"green\">" + str(cell) + "</td>")
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
                out.append(  "<br />\n Page served in " + str(int(round(elapsed*1000))) + "ms. Bot cached: " + str(cached))
                out.append("\n<br /> parsing: " + str(int(round(parsetime*1000))) )
                out.append("\n<br /> retrieve: " + str(int(round(retrievetime*1000))) )
                out.append("\n<br /> sort: " + str(int(round(sorttime*1000))) )
                out.append("\n<br /> html generation: " + str(int(round(htmltime*1000))) )
            out.append(  "</body></html>")
            
            outstr = string.join(out,"")
                
            self.response.out.write(outstr)


application = webapp.WSGIApplication([
    ('/BotDetails', BotDetails)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
