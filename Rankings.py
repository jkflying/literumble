#!/usr/bin/env python
#import cgi
#import datetime
import wsgiref.handlers
import time
#try:
#    import json
#except:
#    import simplejson as json
import string
import cPickle as pickle
import marshal
#from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures
import zlib
from structures import global_dict
class Rankings(webapp.RequestHandler):
    def get(self):
        global global_dict
        #global_dict = {}
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
        #ofst = int(requests.get("offset","0"))
        order = requests.get("order","APS")
        timing = bool(requests.get("timing",False))
        api = bool(requests.get("api",False))
        
        extraArgs = ""
        
        
        if timing:
            extraArgs += "&amp;timing=1"
        if lim < 100000:
            extraArgs += "&amp;limit=" + str(lim)
            
            
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
        rumble = global_dict.get(game,None)
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
        
        flagmap = global_dict.get(structures.default_flag_map,None)
        if flagmap is None:
            flagmap = memcache.get(structures.default_flag_map)
            if flagmap is None:
                flagmapholder = structures.FlagMap.get_by_key_name(structures.default_flag_map)
                if flagmapholder is None:
                    flagmap = zlib.compress(marshal.dumps({}))
                else:
                    flagmap = flagmapholder.InternalMap
                    memcache.set(structures.default_flag_map,flagmap)
                    global_dict[structures.default_flag_map] = flagmap
            else:
                global_dict[structures.default_flag_map] = flagmap
        
        try:
            flagmap = pickle.loads(zlib.decompress(flagmap))
        except:
            flagmap = marshal.loads(zlib.decompress(flagmap))
        
        
        try:
        #print "try json"
            botsdict = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
            bots = botsdict.values()
#       try:        
#           self.response.out.write( " json worked")
        except:
           
#               self.response.out.write( "\ntry pickle")
                scoresdicts = marshal.loads(zlib.decompress(rumble.ParticipantsScores))
                scoreslist = [structures.LiteBot() for _ in scoresdicts]
                for s,d in zip(scoreslist,scoresdicts):
                    s.__dict__.update(d)
                #r = {s.Name:s for s in scoreslist}
                bots = scoreslist

#               print " pickle worked"
            
               
            
        retrievetime = time.time() - starttime - parsing
        #newbots = []
        for b in bots:
            b.PWIN = 50.0*float(b.PL)/b.Pairings + 50.0
            
            if b.VoteScore is None:
                b.VoteScore = 0
            if b.ANPP is None:
                b.ANPP = 0
            package = string.split(b.Name,".")[0]
            if package in flagmap:
                b.Flag = flagmap[package]
            else:
                b.Flag = "NONE"
            
        
        get_key = attrgetter(order)
        bots.sort( key=lambda b: get_key(b), reverse=reverseSort)
        
        if api:
            headings = ["\"name\"",
                        "\"flag\"",
                        "\"rank\"",
                        "\"APS\"",
                        "\"PWIN\"",
                        "\"ANPP\"",
                        "\"vote\"",
                        "\"survival\"",
                        "\"pairings\"",
                        "\"battles\"",
                        "\"latest\""]
            escapes = ["\"","\"","","","","","","","","","\""]
            outs = ["[\n"]
            count = 0
            for bot in bots:
                count += 1
                if count > lim:
                    break
                
                
                cells = [
                bot.Name,bot.Flag,count,
                round(100.0*bot.APS)*0.01,
                round(100.0*bot.PWIN)*0.01,
                round(100.0*bot.ANPP)*0.01,
                round(100.0*bot.VoteScore)*0.01,
                round(100.0*bot.Survival)*0.01,
                bot.Pairings,bot.Battles,bot.LastUpload]
                
                outs.append("{")
                for i in range(len(cells)):
                    outs.append(headings[i])
                    outs.append(":")
                    outs.append(escapes[i])
                    outs.append(str(cells[i]))
                    outs.append(escapes[i])
                    outs.append(",")
                outs[-1] = "},\n"
            outs[-1] = ("}\n]")
            self.response.out.write(''.join(outs))

                
        else:

        
            sorttime = time.time() - parsing - retrievetime - starttime
            
            if  order == "LastUpload":
                order = "Latest Battle"
            elif order == "Name":
                order = "Competitor"
            elif order == "VoteScore":
                order = "Vote"
            out = []
            
            gameTitle = "RANKINGS - " + string.upper(game) + " WITH " + str(len(bots)) + " BOTS"
            out.append(structures.html_header % (game,gameTitle))
            
            pairVals = [b.Pairings for b in bots]
            if max(pairVals) == min(pairVals) == (len(bots)-1):
                out.append("<big>Rankings Stable</big>")
            else:
                out.append("<big>Rankings Not Stable</big>")
            out.append("\n<table>\n<tr>");
            
            headings = ["","Flag","Competitor","APS","PWIN","ANPP","Vote","Survival","Pairings","Battles","Latest Battle"]
            for heading in headings:
                sortedBy = order == heading
                if order == heading and reverseSort:
                    heading = "-" + heading
                orderl = []
                orderl.append("<a href=\"Rankings?game=")
                orderl.append(game)
                orderl.append("&amp;order=")
                orderl.append(heading.replace(" ","%20"))
                orderl.append(extraArgs)
                orderl.append("\">")
                orderl.append(heading)
                orderl.append("</a>")
                orderHref = ''.join(orderl)
                if sortedBy:
                    out.append( "\n<th class=\"sortedby\">" + orderHref + "</th>")
                else:
                    out.append( "\n<th>" + orderHref + "</th>")
            out.append("\n</tr>")
            rank = 1
            for bot in bots:
                if rank > lim:
                    break
                    
                botName=bot.Name
                bnh = []
                bnh.append("<a href=\"BotDetails?game=")
                bnh.append(game)
                bnh.append("&amp;name=")
                bnh.append(botName.replace(" ","%20"))
                bnh.append(extraArgs)
                bnh.append("\" >")
                bnh.append(botName)
                bnh.append("</a>")
                botNameHref = ''.join(bnh) #"<a href=BotDetails?game="+game+"&name=" + botName.replace(" ","%20")+extraArgs+">"+botName+"</a>"
                
                ft = []
                ft.append("<img id='flag' src=\"/flags/")
                ft.append(bot.Flag)
                ft.append(".gif\">")
                flagtag = ''.join(ft)
                
                cells = [rank,flagtag,botNameHref,
                    round(100.0*bot.APS)*0.01,
                    round(100.0*bot.PWIN)*0.01,
                    round(100.0*bot.ANPP)*0.01,
                    round(100.0*bot.VoteScore)*0.01,
                    round(100.0*bot.Survival)*0.01,
                    bot.Pairings,bot.Battles,bot.LastUpload]
                    
                out.append("\n<tr>")
                for cell in cells:
                    out.append( "\n<td>")
                    out.append(str(cell))
                    out.append("</td>")
                out.append("\n</tr>")
                del bot.PWIN
                rank += 1
                
            out.append( "</table>")
            htmltime = time.time() - parsing - retrievetime - sorttime - starttime
            
            elapsed = time.time() - starttime
            if timing:
                out.append("\n<br> Page served in " + str(int(round(elapsed*1000))) + "ms. ")# + str(len(missingHashes)) + " bots retrieved from datastore.")
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
