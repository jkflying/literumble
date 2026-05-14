#!/usr/bin/env python
import datetime
import json
import logging
import time
from collections import deque

from flask import request
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors

import structures
from structures import global_dict


def uploaded_results():
    starttime = time.time()
    out = []

    post_body = request.get_data(as_text=True)

    sections = post_body.split('&')
    results = {}
    for pair in sections:
        ab = pair.split('=')
        if ab is not None and len(ab) == 2:
            results[ab[0]] = ab[1]

    client = results.get("client", "ERROR")
    version = results.get("version", "ERROR")
    rumble = results.get("game", None)
    bota = results.get("fname", None)
    botb = results.get("sname", None)
    bota_name = botb_name = ""
    if bota and botb:
        bota_name = bota.split(" ")[0].split(".")[-1]
        botb_name = botb.split(" ")[0].split(".")[-1]

    now = datetime.datetime.now()
    battleTimeStr = results.get("time", None)
    if battleTimeStr is not None:
        battleTime = datetime.datetime.utcfromtimestamp(int(battleTimeStr) / 1e3)
        logging.info("Uploaded battle run at " + str(battleTime))
        if battleTime < now - datetime.timedelta(1):
            logging.info("Old data uploaded, discarding " + bota_name + " vs " + botb_name + " fought at " + str(battleTime))
            return "OK. ERROR: your uploaded data is more than 24 hours old!"

    uploads_allowed = global_dict.get("uploads allowed", None)
    uploads_allowed_expired = global_dict.get("uploads allowed check time", None)
    if uploads_allowed is None or uploads_allowed_expired is None or now > uploads_allowed_expired:
        tq = taskqueue.Queue()
        tqs_r = tq.fetch_statistics_async()
        tqs = tqs_r.get_result()
        last_min = tqs.executed_last_minute
        if last_min is None or last_min <= 250:
            last_min = 250
        tasks = tqs.tasks
        if tasks is None:
            tasks = 0
        backlog = float(tasks) / last_min
        uploads_allowed = backlog < 5
        global_dict["uploads allowed"] = uploads_allowed
        global_dict["uploads allowed check time"] = now + datetime.timedelta(1. / (24 * 60))
    if not uploads_allowed:
        logging.info("Queue full, discarding " + bota_name + " vs " + botb_name)
        return "OK. Queue full," + bota_name + " vs " + botb_name + " discarded."

    if (version in structures.allowed_versions
            and client in structures.allowed_clients
            and rumble is not None
            and bota is not None
            and botb is not None):
        try:
            taskqueue.add(url='/HandleQueuedResults', payload=json.dumps(results), headers={'X-AppEngine-FailFast': 'True'})
            logging.info("adding " + bota_name + " vs " + botb_name)
        except apiproxy_errors.OverQuotaError:
            logging.info("discarding " + bota_name + " vs " + botb_name + " via error")
            return "OK. Queue full," + bota_name + " vs " + botb_name + " discarded."
        except taskqueue.Error:
            return "OK. Task queue error," + bota_name + " vs " + botb_name + " discarded."

        rq_name = rumble + "|queue"
        try:
            rumble_queue = global_dict[rq_name]
            try:
                prio_string = rumble_queue.pop()
                logging.info("sending back priority battle: " + prio_string + ", " + rumble)
                out.append(prio_string)
            except IndexError:
                prio_string = None
        except KeyError:
            logging.info("No queue for rumble " + rumble + ", adding one!")
            global_dict[rq_name] = deque()

        out.append("OK. " + bota_name + " vs " + botb_name + " added to queue")

        elapsed = time.time() - starttime
        out.append(" in " + str(int(round(elapsed * 1000))) + "ms")
        if results.get("user") == "Put_Your_Name_Here":
            out.append("\nPlease set your username in /robocode/roborumble/{rumblename}.txt!")

        return "".join(out)

    logging.info("version: " + client)
    return "OK. CLIENT NOT SUPPORTED. Use one of: " + str(structures.allowed_clients) + ", not " + client
