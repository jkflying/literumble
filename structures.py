#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

class Pairing(db.Model):
	BotA = db.StringProperty()
	BotB = db.StringProperty()
	APS = db.FloatProperty()
	Survival = db.FloatProperty()
	Battles = db.IntegerProperty()
	Rumble = db.StringProperty()
	

class BotEntry(db.Model)
	Name = db.StringProperty()
	Battles = db.IntegerProperty()
	Pairings = db.IntegerProperty()
	APS = db.FloatProperty()
	PL = db.IntegerProperty()
	Rumble = db.StringProperty()
	
