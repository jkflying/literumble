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
import marshal
import zlib
import pickle

#from google.appengine.ext import db
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.api import memcache
#from operator import attrgetter
import structures
from structures import global_dict
def formatSecs(secs):
    mins = int(round(secs/60.0 - 0.49999))
    secs = int(round(secs%60))
    hours =int(round(mins/60.0 - 0.49999))
    mins = int(round(mins%60))
    days = int(round(hours/24.0 - 0.49999))
    #years = days/365.0
    timeSince = ""
    if days > 0:
        timeSince = str(days) + " day"
        if days != 1:
            timeSince += "s"
    elif hours > 0:
        timeSince = str(hours) + " hour"
        if hours != 1:
            timeSince += "s"
    else:# mins > 0:
        timeSince = str(mins) + " minute"
        if mins != 1:
            timeSince += "s"
#    else:
#        timeSince = str(secs) + " second"
#        if secs != 1:
#            timeSince += "s"
    #timeSince += " ago"
    return timeSince

def timeSince(timestring):                        
    t = datetime.datetime.strptime(timestring,"%Y-%m-%d %H:%M:%S")
    secs = (datetime.datetime.now() - t).total_seconds()
    return formatSecs(secs)

class RumbleStats(webapp.RequestHandler):
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
        
        timing = bool(requests.get("timing",False))
        regen = bool(requests.get("regen",False))
        
        
        extraArgs = ""
        
        
        #if timing:
        #    extraArgs += "&amp;timing=1"
        outstr = None 
        if not regen:        
            outstr = global_dict.get("stats",None)
            if outstr is None:
                outstr = memcache.get("stats")
        if outstr is None:
            tq = taskqueue.Queue()
            tqs_r = tq.fetch_statistics_async()
            #gameHref = "<a href=Rankings?game=" + game + extraArgs + ">" + game + "</a>"
            out = []
            out.append(structures.html_header % ("Statistics","LiteRumble Statistics"))
            out.append("Stats generated: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "<br><br>\n")
            q = structures.Rumble.all()
            
            rumbles = [[],[],[]]
            categories = ["1v1","Melee","Teams"]
            
            for r in q.run():
                memr = global_dict.get(r.Name,None)
                if memr is None:
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
                    scores = pickle.loads(zlib.decompress(r.ParticipantsScores))
                    entries = len(scores)
                    if r.LastUpload is None:
                        latest = None
                        for s in scores.values():
                            t = s.LastUpload
                            if latest is None or t > latest:
                                latest = t
                        r.LastUpload = latest
                        
                    r.__dict__["entries"] = entries 
                    #r.__dict__["scores"] = scores 
                rumbs.sort(key = lambda r: -r.__dict__["entries"])
 
                    
                out.append(  "<table class=\"rumble\">\n<tr>")
                
                out.append(  "\n<b><th>" + cat + "</th>\n<th>Participants/Uploader</th>\n<th>Total Uploads</th>\n<th>Last Upload</th>\n</b></tr>")
                
                for i,r in enumerate(rumbs):
                    game = r.Name
                    gameHref = "<a href=\"Rankings?game=" + game + extraArgs + "\" ><b>" + game + "</b></a>"
                    

                        
                    lastTimeSince = timeSince(r.LastUpload) + " ago"
                    out.append( "\n<tr>\n<td>" + gameHref + "</td>\n<th>" + str(r.__dict__["entries"]) + "</th>\n<th>")
                    out.append(str(r.TotalUploads) + "</th><th>"+lastTimeSince+"</th>\n</tr>")
                    try:
                        uploaders = pickle.loads(zlib.decompress(r.Uploaders))
                        if len(uploaders) == 0:
                            uploaders = {}
                    except TypeError:
                        uploaders = {}

                    
                    #out.append("\n<tr><td></td><td><i><u>Uploader Name</u></i></td><td></td><td></td></tr>")
                    uv = uploaders.values()
                    uv.sort(key = lambda u: u.latest, reverse=True)                    
                    for u in uv:
                        out.append("\n<tr><td></td><td>")
                        out.append(u.name)
                        out.append("</td><td>")
                        out.append(str(u.total))
                        out.append("</td><td>")
                        out.append(timeSince(u.latest) + " ago")
                        out.append("</td></tr>")
                    
                
                for r in rumbs:
                    r.__dict__.pop("entries",1)
                    #r.__dict__.pop("scores",1)
                out.append(  "</table>")
            tqs = tqs_r.get_result()
            tasks = tqs.tasks
            last_min = tqs.executed_last_minute
            if last_min is None or last_min == 0:
                last_min = 1
            if tasks is None:
                tasks is 0
            backlog = float(tasks)*60.0/last_min
            
            #out.append()
            tq_string =  "<table><tr><th>Upload Queue Delay</th><th>" + formatSecs(backlog) + "</th></tr>"
            tq_string += "<tr><th>Upload Queue Size</th><th>" + str(tasks) + " item"
            if tasks != 1:
                tq_string += "s"
            tq_string += "</th><tr></table><br>"
            out.insert(2,tq_string)
            outstr = string.join(out,"")
            

        memcache.set("stats",outstr)
        global_dict["stats"] = outstr
            
        elapsed = time.time() - starttime
        if timing:
            outstr += "<br>\n Page served in " + str(int(round(elapsed*1000))) + "ms."
        outstr += "</body></html>"

        self.response.out.write(outstr)


application = webapp.WSGIApplication([
    ('/RumbleStats', RumbleStats)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
