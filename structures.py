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

total = "TOTAL"

class Pairing(db.Model):
	#ABRU = db.StringProperty() --> key_name
	BotA = db.StringProperty()
	BotB = db.StringProperty()
	APS = db.FloatProperty()
	Survival = db.FloatProperty()
	Battles = db.IntegerProperty()
	Rumble = db.StringProperty()
	Uploader = db.StringProperty()
	LastUpload = db.DateTimeProperty()
	

class BotEntry(db.Model):
	#NRU = db.StringProperty() --> key_name
	Name = db.StringProperty()
	Battles = db.IntegerProperty()
	Pairings = db.IntegerProperty()
	APS = db.FloatProperty()
	Survival = db.FloatProperty()
	PL = db.IntegerProperty()
	Rumble = db.StringProperty()
	LastUpload = db.DateTimeProperty()
	Active = db.BooleanProperty()

class Uploader(db.Model):
	#NC = db.StringProperty() --> key_name
	Name = db.StringProperty()
	Client = db.StringProperty()
	LastUpload = db.DateTimeProperty()
	TotalUploads = db.IntegerProperty()
	
class Rumble(db.Model):
	Teams = db.BooleanProperty()
	Melee = db.BooleanProperty()
	Rounds = db.IntegerProperty()
	Field = db.StringProperty()
	Name = db.StringProperty() # key_name
