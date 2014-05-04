import os
import pprint

from google.appengine.api import memcache
from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.ext import db

#pprint.pprint(os.environ.copy())
import numpy

import structures
import pickle
import zlib

for game in ["meleerumble","minimeleerumble","micromeleerumble","nanomeleerumble",
             "roborumble","minirumble","microrumble","nanorumble","gigarumble",
             "teamrumble",
             "twinduel",
             ]:
    #rumble = structures.Rumble.get_by_key_name(game)
    rumble = None
    botsdict = pickle.loads(zlib.decompress(rumble.ParticipantsScores))
    bots = botsdict.values()
    keys = [db.Key.from_path('BotEntry',b.Name + "|" + game) for b in bots]
    db.delete(keys)
    db.delete(rumble)
    pprint.pprint("Success! " + str(len(keys)) + " keys deleted!")