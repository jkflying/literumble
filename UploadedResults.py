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

global_sync = {}
last_write = {}
locks = {}


class UploadedResults(webapp.RequestHandler):
    def post(self):
        global global_dict
        global global_sync
        global locks
        global last_write
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
        bota = results.get("fname",None)
        botb = results.get("sname",None)

        now = datetime.datetime.now()
        battleTimeStr = results.get("time",None)
        if battleTimeStr is not None:
            battleTime = datetime.datetime.utcfromtimestamp(int(battleTimeStr)/1e3)
            logging.info("Uploaded battle run at " + str(battleTime))
            if battleTime < now - datetime.timedelta(1):
                self.response.out.write("OK. ERROR: your uploaded data is more than 24 hours old!")
                logging.info("Old data uploaded, discarding " +  bota_name + " vs " + botb_name + " fought at " + battleTime)
                return

        uploads_allowed = global_dict.get("uploads allowed",None)
        uploads_allowed_expired = global_dict.get("uploads allowed check time",None)
        if uploads_allowed is None or uploads_allowed_expired is None or now > uploads_allowed_expired :
            tq = taskqueue.Queue()
            tqs_r = tq.fetch_statistics_async()
            tqs = tqs_r.get_result()
            last_min = tqs.executed_last_minute
            if last_min is None or last_min <= 250:
                last_min = 250
            tasks = tqs.tasks
            if tasks is None:
                tasks is 0
            backlog = float(tasks)/last_min
            uploads_allowed = backlog < 5
            global_dict["uploads allowed"]=uploads_allowed
            global_dict["uploads allowed check time"] = now + datetime.timedelta(1./(24*60))
        if not uploads_allowed:
            bota_name = bota.split(" ")[0].split(".")[-1]
            botb_name = botb.split(" ")[0].split(".")[-1]
            self.response.out.write("OK. Queue full," + bota_name + " vs " + botb_name + " discarded.")
            logging.info("Queue full, discarding " +  bota_name + " vs " + botb_name)
            return

        if (version in structures.allowed_versions
            and client in structures.allowed_clients
            and rumble is not None
            and bota is not None
            and botb is not None):
            #prio_q = taskqueue.Queue("priority-battles")
            #prio_task_list_rpc = prio_q.lease_tasks_by_tag_async(30,1,rumble)
            try:
                taskqueue.add(url='/HandleQueuedResults', payload=json.dumps(results))
                bota_name = bota.split(" ")[0].split(".")[-1]
                botb_name = botb.split(" ")[0].split(".")[-1]
                logging.info("adding " +  bota_name + " vs " + botb_name )
            except apiproxy_errors.OverQuotaError:
                bota_name = bota.split(" ")[0].split(".")[-1]
                botb_name = botb.split(" ")[0].split(".")[-1]
                self.response.out.write("OK. Queue full," + bota_name + " vs " + botb_name + " discarded.")
                logging.info("discarding " +  bota_name + " vs " + botb_name + " via error")
                #time.sleep(0.5)
                return
            except taskqueue.Error:
                bota_name = bota.split(" ")[0].split(".")[-1]
                botb_name = botb.split(" ")[0].split(".")[-1]
                self.response.out.write("OK. Task queue error," + bota_name + " vs " + botb_name + " discarded.")

            rq_name = rumble + "|queue"
            try:
                rumble_queue = global_dict[rq_name]
                try:
                    prio_string = rumble_queue.get_nowait()
                    logging.info("sending back priority battle: " + prio_string + ", " + rumble)
                    self.response.out.write(prio_string)
                    #logging.info("Sent back priority battles: " + prio_string)
                except Queue.Empty:
                    #logging.info("No available priority battles")
                    prio_string = None
            except KeyError:
                logging.info("No queue for rumble " + rumble + ", adding one!")
                global_dict[rq_name] = Queue.Queue(maxsize=300)
            bota_name = bota.split(" ")[0].split(".")[-1]
            botb_name = botb.split(" ")[0].split(".")[-1]
            self.response.out.write("OK. " + bota_name + " vs " + botb_name + " added to queue")

            elapsed = time.time() - starttime
            self.response.out.write(" in " + str(int(round(elapsed*1000))) + "ms")
            if results["user"] == "Put_Your_Name_Here":
                self.response.out.write("\nPlease set your username in /robocode/roborumble/{rumblename}.txt!")

        else:
            logging.info("version: " + client)
            self.response.out.write("OK. CLIENT NOT SUPPORTED. Use one of: " + str(structures.allowed_clients) + ", not " + client)

        #time.sleep(0.0)



application = webapp.WSGIApplication([
    ('/UploadedResults', UploadedResults)
], debug=True)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
