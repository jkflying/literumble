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
participants = "PARTICIPANTS"

#class Pairing(db.Model):
	##ABRU = db.StringProperty() --> key_name
	#BotA = db.StringProperty()
	#BotB = db.StringProperty()
	#APS = db.FloatProperty(indexed = False)
	#Survival = db.FloatProperty(indexed = False)
	#Battles = db.IntegerProperty()
	#Rumble = db.StringProperty()
	#Uploader = db.StringProperty()
	#LastUpload = db.DateTimeProperty()
	#Active = db.BooleanProperty()

class ScoreSet:
	def __init__ (self, name = "", aps = 0.0, survival = 0.0, battles = 0):
		self.Name = name
		self.APS = aps
		self.Survival = survival
		self.Battles = battles
		
#class CachedBot:
	#def __init__ (self, bot):
		#self.Name = bot.Name
		#self.Battles = bot.Battles
		#self.Pairings = bot.Pairings
		#self.APS = bot.APS
		#self.Survival = bot.Survival
		#self.PL = bot.PL
		#self.Rumble = bot.Rumble
		#self.LastUpload = bot.LastUpload
		#self.Active = bot.Active
		#self.PairingsDict = pickle.loabot.PairingsDict

class BotEntry(db.Model):
	#NR = db.StringProperty() --> key_name
	Name = db.StringProperty(indexed = False)
	Battles = db.IntegerProperty(indexed = False)
	Pairings = db.IntegerProperty(indexed = False)
	APS = db.FloatProperty(indexed = False)
	Survival = db.FloatProperty(indexed = False)
	PL = db.IntegerProperty(indexed = False)
	Rumble = db.StringProperty()
	LastUpload = db.DateTimeProperty(indexed = False)
	Active = db.BooleanProperty()
	PairingsList = db.TextProperty()

class Uploader(db.Model):
	#NC = db.StringProperty() --> key_name
	Name = db.StringProperty(indexed = False)
	Client = db.StringProperty(indexed = False)
	LastUpload = db.DateTimeProperty(indexed = False)
	TotalUploads = db.IntegerProperty(indexed = False)
	
class Rumble(db.Model):
	#NRFTM = db.StringProperty() --> key_name
	Teams = db.BooleanProperty(indexed = False)
	Melee = db.BooleanProperty(indexed = False)
	MeleeSize = db.IntegerProperty(indexed = False)
	Rounds = db.IntegerProperty(indexed = False)
	Field = db.StringProperty(indexed = False)
	Name = db.StringProperty(indexed = False) # key_name
	TotalUploads = db.IntegerProperty(indexed = False)
	Participants = db.StringListProperty(indexed = False) 

