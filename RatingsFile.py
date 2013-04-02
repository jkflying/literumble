#!/usr/bin/env python
#import cgi
#import datetime
import wsgiref.handlers
#import time
#from time import strftime
#try:
#    import json
#except:
#    import simplejson as json
import string
import cPickle as pickle
import zlib
import marshal
#from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache

import structures
#from structures import global_dict
        
class RatingsFile(webapp.RequestHandler):
    def get(self):
        #global global_dict
        global_dict = {}
        
        #starttime = time.time()
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
        
        try:
            scoresdicts = marshal.loads(zlib.decompress(rumble.ParticipantsScores))
            scoreslist = [structures.LiteBot() for _ in scoresdicts]
            for s,d in zip(scoreslist,scoresdicts):
                s.__dict__.update(d)
            r = scoreslist
        except:
            botsdict = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
            r = botsdict.values()     
                
            
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
