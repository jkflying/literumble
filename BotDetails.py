#!/usr/bin/env python
#import cgi
import datetime
import wsgiref.handlers
import time
#try:
#    import json
#except:
#    import simplejson as json
import string

import zlib
import cPickle as pickle
import marshal

#from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures
from structures import global_dict
from PIL import Image
import base64
import cStringIO
import numpy
class BotDetails(webapp.RequestHandler):
    def get(self):
#        global_dict = {}
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
        api = bool(requests.get("api",False))
        
        
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
        #bot = global_dict.get(keyhash,None)
        #if bot is None:
        bot = memcache.get(keyhash)
#            global_dict[keyhash] = bot
            
        if bot is None or bot.PairingsList is None:
            bot = structures.BotEntry.get_by_key_name(keyhash)

            if bot is not None:
                
                memcache.set(keyhash,bot)
#                global_dict[keyhash] = bot
                cached = False
        rumble = None
        if not api:
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
                
                
        if bot is None:
            self.response.out.write( "ERROR. name/game combination does not exist: " + name + "/" + game)
        else:

            flagmap = global_dict.get(structures.default_flag_map)
            if flagmap is None:
                flagmap = memcache.get(structures.default_flag_map)
                if flagmap is None:
                    flagmapholder = structures.FlagMap.get_by_key_name(structures.default_flag_map)
                    if flagmapholder is None:
                        flagmap = zlib.compress(pickle.dumps({}))
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

            bots = None
            if lim > 0 or not api:
                try:
                    bots = pickle.loads(zlib.decompress(bot.PairingsList))
                except:
                    botsDicts = marshal.loads(zlib.decompress(bot.PairingsList))
                    bots = [structures.ScoreSet() for _ in botsDicts]
                    for s,d in zip(bots,botsDicts):
                        s.__dict__.update(d)


                removes = []
                for b in bots:
                    lastUpload = None
                    try:
                        lastUpload = b.LastUpload
                    except:
                        b.LastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    package = string.split(b.Name,".")[0]
                    if package in flagmap:
                        b.Flag = flagmap[package]
                    else:
                        b.Flag = "NONE"
                    try:
                        b.APS = float(b.APS)
                        b.KNNPBI = float(b.KNNPBI)
                        b.NPP = float(b.NPP)
                        b.Battles = int(b.Battles)
                        
                    except:
                        removes.append(b)
                for b in removes:
                    bots.pop(bots.index(b))
                        
            package = string.split(bot.Name,".")[0]
            if package in flagmap:
                bot.Flag = flagmap[package]
            else:
                bot.Flag = "NONE"
            
                
            retrievetime = time.time() - parsetime - starttime
            
            if lim > 0:
                bots = filter(lambda b: getattr(b,'Alive',True), bots)
                bots = sorted(bots, key=attrgetter(order), reverse=reverseSort)            
            
            if api:
                outs = ["{"]
                outs.append("\n\"name\":\"")
                outs.append(name)
                outs.append("\",\n\"flag\":\"")
                outs.append(bot.Flag)
                outs.append("\",\n\"APS\":")
                outs.append(str(bot.APS))
                outs.append(",\n\"PWIN\":")
                outs.append(str(50.0*float(bot.PL)/bot.Pairings + 50.0))
                outs.append(",\n\"ANPP\":")
                outs.append(str(bot.ANPP))
                outs.append(",\n\"vote\":")
                outs.append(str(bot.VoteScore))
                outs.append(",\n\"survival\":")
                outs.append(str(bot.Survival))
                outs.append(",\n\"pairings\":")
                outs.append(str(bot.Pairings))
                outs.append(",\n\"battles\":")
                outs.append(str(bot.Battles))
                outs.append(",\n\"latest\":\"")
                outs.append(str(bot.LastUpload))
                outs.append("\"")
                if lim > 0:
                    outs.append(",\n\"pairingsList\":[\n")
                    headings = [
                    "\"name\"",
                    "\"flag\"",
                    "\"rank\"",
                    "\"APS\"",
                    "\"NPP\"",
                    "\"survival\"",
                    "\"KNNPBI\"",
                    "\"battles\"",
                    "\"latest\""]
                    escapes = ["\"","\"","","","","","","","\""]
                    count = 0
                    for b in bots:
                        count += 1
                        if count > lim:
                            break
                        
                        cells = [b.Name,
                                 b.Flag,
                                 count,
                        round(100.0*b.APS)*0.01,
                        round(100.0*b.NPP)*0.01,
                        round(100.0*b.Survival)*0.01,
                        round(100.0*b.KNNPBI)*0.01,
                        b.Battles,b.LastUpload]
                        
                        outs.append("    {")
                        for i in range(len(cells)):
                            outs.append(headings[i])
                            outs.append(":")
                            outs.append(escapes[i])
                            outs.append(str(cells[i]))
                            outs.append(escapes[i])
                            outs.append(",")
                        outs[-1] = "},\n"
                    outs[-1] = "}\n]"
                outs.append("\n}")
                self.response.out.write(''.join(outs))
                
            else:
                                
                sorttime = time.time() - retrievetime - parsetime - starttime
                if order == "LastUpload":
                    order = "Latest Battle"
                
                out = []
                
                gameHref = "<a href=\"Rankings?game=" + game + extraArgs + "\">" + game + "</a>"
                gameTitle = "Bot details of <b>" + name + "</b> in "+ gameHref + " vs. " + str(len(bots)) + " bots."
                
                flagtag = "<img id='flag' src=\"/flags/" + bot.Flag + ".gif\">  " + bot.Flag
                
                out.append(structures.html_header % (game,gameTitle))
                out.append("<table>\n")
                out.append("<tr>\n<th>Name</th>\n<td>\n" + name + "</td>\n<th>Score Distribution</th></tr>")
                out.append("<tr>\n<th>Flag</th>\n<td>\n" + flagtag + "</td><td rowspan=\"9\">")
                
                enemyScores = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
                
                #def pngString(arr)
                size = 219
                a = numpy.empty((size+1,size+1,4))
                a[...,(0,1,2)]=255
                a[size - int(.5*size),...,(0,1,2)] = 127
                for b in bots:
                    eScore = enemyScores.get(b.Name,None)
                    if eScore:
                        a[max(0,min(size,size-int(round(b.APS*0.01*size)))),
                          int(round(eScore.APS*0.01*size)),(0)]=0
                        a[max(0,min(size,size-int(round(b.Survival*0.01*size)))),
                          int(round(eScore.Survival*0.01*size)),(1)]=0
                        
                        a[max(0,min(size,size-int(round((b.KNNPBI+50)*0.01*size)))),
                          int(round(eScore.APS*0.01*size)),(2)]=0
#                        if eScore.ANPP > 0 and b.NPP >= 0:
 #                           a[size-int(round(b.NPP*0.01*size)),int(round(eScore.ANPP*0.01*size)),(0,1)]=0
                
                b = Image.fromarray(a.astype("uint8"), "CMYK")
                
                b = b.convert("RGB")
                a = numpy.array(b)
                a[(a == (0,0,0)).all(axis=2)] = (255,255,255)
                
                
                b = Image.fromarray(a,"RGB")
                c = cStringIO.StringIO()
                b.save(c,format="png")
                d = c.getvalue()
                c.close()
                e = base64.b64encode(d).decode("ascii")
                out.append('<img title=\"Red = APS, Green = Survival, Blue = APS vs (KNNPBI+50)\" style=\"border: black 1px solid;\" alt="score distibution" src="data:image/png;base64,')
                out.append(e)
                out.append("\">")#<br>Opponent APS vs. Pairing APS")
                                
                
                out.append("</td></tr>")
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
                out.append("</td><td>Opponent (X) vs. Pairing (Y) </td></tr></table>")
                
                
                
                
                
                
                if lim > 0:
                    out.append("\n<table>\n<tr>\n")
                    headings = ["  ",
                    "Flag",
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
                    rank = 0
                    highlightKey = [False,False,False,False,True,True,True,True,False,False]
                    mins = [0,0,0,0,40,40,40,-0.1,0,0]
                    maxs = [0,0,0,0,60,70,60,0.1,0,0]
                    for bot in bots:
                        rank += 1
                        if rank > lim:
                            break
        
                        botName=bot.Name
                        botNameHref = "<a href=\"BotDetails?game="+game+"&amp;name=" + botName.replace(" ","%20")+extraArgs+"\">"+botName+" </a>"
                        compareHref = "<a href=\"BotCompare?game="+game+"&amp;bota=" + name.replace(" ","%20") + "&amp;botb=" + botName.replace(" ","%20") + extraArgs + "\">compare</a>"
                        ft = []
                        ft.append("<img id='flag' src=\"/flags/")
                        ft.append(bot.Flag)
                        ft.append(".gif\">")
                        flagtag = ''.join(ft)
                        
                        cells = [str(rank),
                                    flagtag,
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
