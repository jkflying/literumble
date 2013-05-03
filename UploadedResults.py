#!/usr/bin/env python
#import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string
import cPickle as pickle
#import pickle
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import db
#from google.appengine.api import users
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.api import memcache
#from operator import attrgetter
import random
import time
import zlib
import threading

import structures
import logging
from structures import global_dict
import numpy
import marshal
import Queue
#from Queue import EMPTY

global_sync = {}
#sync_lock = threading.Lock()
#write_lock = threading.Lock()
last_write = {}
locks = {}

allowed_clients = ["1.8.1.0"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
    def post(self):
        global global_dict
        global global_sync
        global locks
        global last_write
        #global sync_lock
        starttime = time.time()
        
        post_body = self.request.body
        
        sections = post_body.split('&')
        results = {}
        for pair in sections:
            ab = pair.split('=')
            if ab is not None and len(ab) == 2:
                results[ab[0]] = ab[1]
        
        client = results.get("client","ERROR")

        version = results.get("version","ERROR")
        rumble = results.get("game",None)        
        if version in allowed_versions and client in allowed_clients and rumble is not None:
            
            try:
                taskqueue.add(url='/HandleQueuedResults', payload=json.dumps(results))
            except apiproxy_errors.OverQuotaError:
                bota = results["fname"]
                botb = results["sname"]
                bota_name = bota.split(" ")[0].split(".")[-1]
                botb_name = botb.split(" ")[0].split(".")[-1]
                self.response.out.write("OK. Queue full," + bota_name + " vs " + botb_name + " discarded.")
                #time.sleep(0.5)
                return
            except taskqueue.Error:
                bota = results["fname"]
                botb = results["sname"]
                bota_name = bota.split(" ")[0].split(".")[-1]
                botb_name = botb.split(" ")[0].split(".")[-1]                
                self.response.out.write("OK. Task queue error," + bota_name + " vs " + botb_name + " discarded.")

            rq_name = rumble + "|queue"
            try:
                rumble_queue = global_dict[rq_name]
                try:
                    prio_string = rumble_queue.get_nowait()
                    self.response.out.write(prio_string)
                    #logging.info("Sent back priority battles: " + prio_string)
                except Queue.Empty:
                    #logging.info("No available priority battles")
                    prio_string = None
            except KeyError:
                logging.info("No queue for rumble " + rumble + ", adding one!")
                global_dict[rq_name] = Queue.Queue(maxsize=300)
            bota = results["fname"]
            botb = results["sname"]
            bota_name = bota.split(" ")[0].split(".")[-1]
            botb_name = botb.split(" ")[0].split(".")[-1]
            self.response.out.write("OK. " + bota_name + " vs " + botb_name + " added to queue")
            
            elapsed = time.time() - starttime
            self.response.out.write(" in " + str(int(round(elapsed*1000))) + "ms")
            
        else:
            self.response.out.write("OK. CLIENT NOT SUPPORTED. Use one of: " + str(allowed_clients) + ", not " + client)
        
        #time.sleep(0.0)



application = webapp.WSGIApplication([
    ('/UploadedResults', UploadedResults)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
