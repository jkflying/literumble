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
from google.appengine.api import urlfetch

from structures import global_dict
class FetchParseFlags(webapp.RequestHandler):
    def get(self):
        global global_dict
        url = "http://robowiki.net/wiki/RoboRumble/Country_Flags?action=raw"
        
        result = urlfetch.fetch(url,method=urlfetch.GET)
        if result.status_code == 200:
            tag = "<pre>"
            endtag = "</pre>"
            startIndex = string.find(result.content,tag) + len(tag)
            endIndex = string.find(result.content,endtag,startIndex)
            assoc = result.content[startIndex:endIndex]
            lines = assoc.split("\n")
            flag_map = {}
            for line in lines:
                if len(line) > 0:
                    parts = line.split(",")
                    if len(parts) == 2 and parts[1] in structures.allowed_flags:
                        flag_map[parts[0]] = parts[1]
            
            db_map = structures.FlagMap(key_name = structures.default_flag_map)
            db_map.InternalMap = db.Blob(zlib.compress(pickle.dumps(flag_map,pickle.HIGHEST_PROTOCOL)))
            db.put(db_map)
            memcache.set(structures.default_flag_map,db_map.InternalMap)
            global_dict[structures.default_flag_map] = db_map.InternalMap
            
            #self.response.out.write(str(flag_map))

            self.response.out.write("\nSuccess!")


application = webapp.WSGIApplication([
    ('/FetchParseFlags', FetchParseFlags)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
