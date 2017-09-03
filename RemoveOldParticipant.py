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
#import string
import cPickle as pickle
import zlib
import marshal

#from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache

import structures

def nth_repl(s, sub, repl, nth):
    find = s.find(sub)
    # if find is not p1 we have found at least one match for the substring
    i = find != -1
    # loop util we find the nth or we find no match
    while find != -1 and i != nth:
        # find + 1 means we start at the last match start index + 1
        find = s.find(sub, find + 1)
        i += 1
    # if i  is equal to nth we found nth matches so replace
    if i == nth:
        return s[:find]+repl+s[find + len(sub):]
    return s

class RemoveOldParticipant(webapp.RequestHandler):
    def get(self):
        parts = self.request.query_string.split("&")
        requests = {}
        if parts[0] != "":
            for pair in parts:
                ab = pair.split('=')
                requests[ab[0]] = ab[1]
        self.response.out.write(removeFromRumble(self,requests))
    
    def post(self):
        parts = self.request.body.split("&")
        requests = {}
        if parts[0] != "":
            for pair in parts:
                ab = pair.split('=')
                requests[ab[0]] = ab[1]
        self.response.out.write(removeFromRumble(self,requests))
        

def removeFromRumble(self,requests):
    #global global_dict
    global_dict = {}
    if "version" not in requests or requests["version"] is not "1":
        return "ERROR. bad/no version"
        
        
    game = requests.get("game",None)
    if game is None:
        return "ERROR. no game specified"
        
        
    name = requests.get("name",None)
    if name is None:
        return "ERROR. no name specified"
    while name.count("%20") > 0:
        name = rreplace(name,"%20"," ",1)
        
    
    rumble = global_dict.get(game,None)
    if rumble is None:
        rumble = memcache.get(game)
        if rumble is None:
            rumble = structures.Rumble.get_by_key_name(game)

    if name.count(" ") == 0:
        num_underscores = name.count("_")
        error_messages = []
        for n in range(num_underscores):
            check_name = nth_repl(name,"_"," ",n+1)

            keyhash = check_name + "|" + game
            entry = global_dict.get(keyhash,None)
            if entry is None:
                entry = memcache.get(keyhash)
                if entry is None:
                    entry = structures.BotEntry.get_by_key_name(keyhash)
                    if entry is None:
                        error_messages.append("ERROR. name/game does not exist: " + check_name + "/" + game)
                    else:
                        entry = structures.CachedBotEntry(entry)

            if entry is not None:
                name = check_name
                break
        if entry is None:
            return "\n".join(error_messages)
    
    if isinstance(entry,structures.BotEntry):
        entry = structures.CachedBotEntry(entry)
        
    global_dict.pop(keyhash,0)
    memcache.delete(keyhash)
        
    entry.Active = False
    
    try:
        scores = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
    except:
        scoresdicts = marshal.loads(zlib.decompress(rumble.ParticipantsScores))
        scoreslist = [structures.LiteBot() for _ in scoresdicts]
        for s,d in zip(scoreslist,scoresdicts):
            s.__dict__.update(d)
        scores = {s.Name:s for s in scoreslist}

        
        
    scores.pop(name,1)
    rumble.ParticipantsScores = zlib.compress(pickle.dumps(scores,pickle.HIGHEST_PROTOCOL),4)
    
    
    memcache.delete("home")
    global_dict.pop("home",0)

    memcache.set(entry.key_name,entry)
    global_dict[entry.key_name] = entry
    modelBot = structures.BotEntry(key_name = entry.key_name)
    modelBot.init_from_cache(entry)
    modelBot.put()
    
    global_dict[game]=rumble
    memcache.set(game,rumble)
    rumble.put()
    
    return "OK. " + name + " retired from " + game

application = webapp.WSGIApplication([
    ('/RemoveOldParticipant', RemoveOldParticipant)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
