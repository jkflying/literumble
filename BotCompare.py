#!/usr/bin/env python
#import cgi
#import datetime
import wsgiref.handlers
import time
#try:
#    import json
#except:
#    import simplejson as json
import marshal
import string

import zlib
import cPickle as pickle

#from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from operator import attrgetter
import structures
import logging
import numpy
from PIL import Image
import base64
import cStringIO

class BotCompare(webapp.RequestHandler):
    def get(self):
        global_dict = {}
        starttime = time.time()
        query = self.request.query_string
        query = query.replace("%20"," ")
        query = query.replace("+"," ")
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
            extraArgs += "&amp;timing=1"
        reverseSort = True
        
        if order is None or order == "" or order.replace(" ","") == "":
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
                
                
                
                retrievetime = time.time() - parsetime - starttime
                
                botabots = None
                botbbots = None
                try:
                    botabots = pickle.loads(zlib.decompress(bota.PairingsList))
                except:
                    botsDicts = marshal.loads(zlib.decompress(botb.PairingsList))
                    botabots = [structures.ScoreSet() for _ in botsDicts]
                    for s,d in zip(botabots,botsDicts):
                        s.__dict__.update(d)
                try:
                    botbbots = pickle.loads(zlib.decompress(botb.PairingsList))
                except:
                    botsDicts = marshal.loads(zlib.decompress(botb.PairingsList))
                    botbbots = [structures.ScoreSet() for _ in botsDicts]
                    for s,d in zip(botbbots,botsDicts):
                        s.__dict__.update(d)
                
                #retrievetime = time.time() - parsetime - starttime
                
                #botabotsDict = {b.Name:b for b in botabots}
                
                botabots = filter(lambda b: getattr(b,'Alive',True),botabots)
                botbbots = filter(lambda b: getattr(b,'Alive',True),botbbots)

                botbbotsDict = {b.Name:b for b in botbbots}
                commonList = []
                for ba in botabots:
                    if ba.Name in botbbotsDict:
                        bb = botbbotsDict[ba.Name]
                        try:
                            bb.APS = float(bb.APS)
                            ba.APS = float(ba.APS)
                            bb.Survival = float(bb.Survival)
                            ba.Survival = float(ba.Survival)
                            
                            commonList.append(structures.ComparePair(ba,bb))
                        except Exception, e:
                            logging.info(str(e))
                        
                for cp in commonList:
                    package = string.split(cp.Name,".")[0]
                    if package in flagmap:
                        cp.Flag = flagmap[package]
                    else:
                        cp.Flag = "NONE"
                
                sortOrder = order.replace(" ","_").replace("(","").replace(")","")
                if len(sortOrder) > 2 and sortOrder[-2] == "_":
                    sortOrder = sortOrder[-1] + "_" + sortOrder[0:-2]
                out = []
                
                #out.append("\n\n" + order + "\n\n")
                #out.append("\n\n" + str(commonList[0].__dict__) + "\n\n")
                
                if sortOrder not in commonList[0].__dict__:
                    order = "Name"
                    sortOrder = "Name"
                    
                commonList = sorted(commonList, key=attrgetter(sortOrder), reverse=reverseSort)
                #order = order.replace("_"," ")
                
                sorttime = time.time() - retrievetime - parsetime - starttime
                if order == "LastUpload":
                    order = "Latest Battle"
                
                
                
                package = string.split(bota.Name,".")[0]
                if package in flagmap:
                    bota.Flag = flagmap[package]
                else:
                    bota.Flag = "NONE"
                package = string.split(botb.Name,".")[0]
                if package in flagmap:
                    botb.Flag = flagmap[package]
                else:
                    botb.Flag = "NONE"


                gameHref = "<a href=\"Rankings?game=" + game + extraArgs + "\">" + game + "</a>"
                gameTitle = "Bot details of <b>" + botaName + " vs. " + botbName + "</b> in "+ gameHref + " vs. " + str(len(commonList)) + " bots."
                out.append(structures.html_header % (game,gameTitle))
                
                out.append("\n<table><tr>")
                
                out.append("\n<th>Name</th>")
                out.append("\n<td>")
                #out.append("<img src=\"/flags/" + bota.Flag + ".gif\">")
                out.append("<a href=\"BotDetails?game="+game+"&amp;name=" + botaName.replace(" ","%20")+extraArgs+"\">"+botaName+"</a>")
                out.append("</td><td>")
                #out.append("<img src=\"/flags/" + botb.Flag + ".gif\">")
                out.append("<a href=\"BotDetails?game="+game+"&amp;name=" + botbName.replace(" ","%20")+extraArgs+"\">"+botbName+"</a>")
                
                out.append("</td><th>Diff Distribution</th></tr>")
                
                out.append("\n<tr><th>Flag</th>")
                out.append("\n<td>")
                out.append("<img id='flag' src=\"/flags/" + bota.Flag + ".gif\">  " + bota.Flag)
                #out.append("<a href=\"BotDetails?game="+game+"&amp;name=" + botaName.replace(" ","%20")+extraArgs+"\">"+botaName+"</a>")
                out.append("</td><td>")
                out.append("<img id='flag' src=\"/flags/" + botb.Flag + ".gif\">  " + botb.Flag)
                #out.append("<a href=\"BotDetails?game="+game+"&amp;name=" + botbName.replace(" ","%20")+extraArgs+"\">"+botbName+"</a>")
                
                out.append("</td><td rowspan=\"7\">")
                enemyScores = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
                # RGB color model
                # Default colors
                # colorSurvival = (0,255,0)
                # colorAPS = (255,0,0)
                # colorAPSvsKNPBI = (0,0,255)
                # Colors suggested at 
                # http://ksrowell.com/blog-visualizing-data/2012/02/02/optimal-colors-for-graphs/
                colorSurvival = (62,150,81)
                colorAPS = (204,37,41)
                #colorAPSvsKNPBI = (57,106,177)
                size = 169
                a = numpy.zeros((size+1,size+1,3), dtype=numpy.uint32)
                
                counts = numpy.zeros((size+1, size+1), dtype=numpy.uint32)
                for cp in commonList:
                    eScore = enemyScores.get(cp.Name,None)
                    if eScore:
                        x = int(round(eScore.APS*0.01*size))
                        yAPS = max(0,min(size,size-int(round((cp.A_APS - cp.B_APS + 50)*0.01*size))))
                        a[yAPS,x,(0,1,2)] += colorAPS
                        counts[yAPS,x] += 1
                        
                        ySurvival = [max(0,min(size,size-int(round((cp.A_Survival - cp.B_Survival + 50)*0.01*size))))]
                        a[ySurvival,x,(0,1,2)] += colorSurvival
                        counts[ySurvival,x] += 1
#                        if eScore.ANPP > 0 and b.NPP >= 0:
 #                           a[size-int(round(b.NPP*0.01*size)),int(round(eScore.ANPP*0.01*size)),(0,1)]=0
                a[counts==0,:] = 255
                setVals = counts>0
                for i in range(3):
                    a[setVals,i] = a[setVals,i]/counts[setVals]
                a[size - int(round(.5*size)),...] = 127
                b = Image.fromarray(a.astype("uint8"),"RGB")
                c = cStringIO.StringIO()
                b.save(c,format="png")
                d = c.getvalue()
                c.close()
                e = base64.b64encode(d).decode("ascii")
                out.append('<img title=\"Red = APS Diff, Green = Survival Diff" style=\"border: black 1px solid;\" alt="score distibution" src="data:image/png;base64,')
                out.append(e)
                out.append("\">")#<br>Opponent APS vs. Pairing APS")
                                
                out.append("</td></tr>")
                
                APSa = 0.0
                APSb = 0.0
                Survivala = 0.0
                Survivalb = 0.0
                Winsa = 0.0
                Winsb = 0.0
                Battlesa = 0
                Battlesb = 0
                LastUploada = None
                LastUploadb = None
                for cp in commonList:
                    APSa += cp.A_APS
                    APSb += cp.B_APS
                    Survivala += cp.A_Survival
                    Survivalb += cp.B_Survival
                    if cp.A_APS >= 50.0:
                        Winsa += 1.0
                    if cp.B_APS >= 50.0:
                        Winsb += 1.0
                    Battlesa += cp.A_Battles
                    Battlesb += cp.B_Battles
                    if cp.A_LastUpload > LastUploada:
                        LastUploada = cp.A_LastUpload
                    if cp.B_LastUpload > LastUploadb:
                        LastUploadb = cp.B_LastUpload
                    
                
                inv_len = 1.0/len(commonList)
                APSa *= inv_len
                APSb *= inv_len
                Survivala *= inv_len
                Survivalb *= inv_len
                Winsa *= 100*inv_len
                Winsb *= 100*inv_len
                
                out.append("\n<tr><th>Common APS</th>")
                out.append("\n<td>" + str(APSa) + "</td><td>" + str(APSb) + "</td></tr>")
                out.append("\n<tr><th>Common Survival</th>")
                out.append("\n<td>" + str(Survivala) + "</td><td>" + str(Survivalb) + "</td>")
                out.append("</tr>")
                out.append("\n<tr><th>Common PWin</th>")
                out.append("\n<td>" + str(Winsa) + "</td><td>" + str(Winsb) + "</td></tr>")
                out.append("\n<tr><th>Common Battles</th>")
                out.append("\n<td>" + str(Battlesa) + "</td><td>" + str(Battlesb) + "</td></tr>")
                out.append("\n<tr><th>Common Last Upload</th>")
                out.append("\n<td>" + str(LastUploada) + "</td><td>" + str(LastUploadb) + "</td></tr>")
                out.append("\n<tr><th>Common Pairings</th>")
                out.append("\n<td colspan=\"2\" align=\"center\">" + str(len(commonList)) + "</td>")
                #out.append("<td>Opponent (X) vs. Diff (Y)</td>")
                out.append("</tr>")
                
                out.append("\n</table>\n<br>\n<table>\n<tr>")

                out.append("\n<td colspan=\"3\"></td><th colspan=\"2\">" + botaName + "</th><th colspan=\"2\">" + botbName + "</th><td colspan=\"2\">")
                out.append("</td></tr><tr class=\"dim\">")
                
                headings = [
                "  ",
                "Flag",
                "Name",
                "APS (A)",
                "Survival (A)",
                "APS (B)",
                "Survival (B)",
                "Diff APS",
                "Diff Survival"
                ]
                #out.append("\n\n" + order + "\n\n")
                for heading in headings:
                    headinglink = heading
                    sortedBy = (order == heading)
                    if sortedBy and reverseSort:
                        heading = "-" + heading
                        headinglink = heading
                    elif not sortedBy:
                        headinglink = "-" + headinglink
      
                    orderHref = "<a href=\"BotCompare?game="+game+"&amp;bota="+botaName.replace(" ","%20")+"&amp;botb="+botbName.replace(" ","%20")+"&amp;order="+ headinglink.replace(" ","%20") + extraArgs + "\">"+heading+"</a>"
                    if sortedBy:
                        out.append("\n<th class=\"sortedby\">" + orderHref + "</th>")
                    else:
                        out.append("\n<th>" + orderHref + "</th>")
                        
                out.append("\n</tr>")
                rank = 1
                highlightKey = [False,False,False,True,True,True,True,True,True]
                mins = [0,0,0,40,40,40,40,-0.1,-5]
                maxs = [0,0,0,60,60,60,60, 0.1, 5]
                for cp in commonList:
                    if rank > lim:
                        break

                    botName=cp.Name
                    botNameHref = "<a href=\"BotDetails?game="+game+"&amp;name=" + botName.replace(" ","%20")+extraArgs+"\">"+botName+"</a>"
                    flagtag = "<img id='flag' src=\"/flags/" + cp.Flag + ".gif\">"
                    cells = [
                            str(rank),
                            flagtag,
                            botNameHref,
                            round(100.0*cp.A_APS)*0.01,
                            round(100.0*cp.A_Survival)*0.01,
                            round(100.0*cp.B_APS)*0.01,
                            round(100.0*cp.B_Survival)*0.01,
                            round(100.0*cp.Diff_APS)*0.01,
                            round(100.0*cp.Diff_Survival)*0.01
                            ]
                        
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
                    out.append("<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms. Bot cached: " + str(cached))
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
