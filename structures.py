#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string
import time

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

total = "TOTAL"
participants = "PARTICIPANTS"
sync = "SYNCHRONIZE"

global_dict = {}

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

class ComparePair:
	def __init__ (self, bota, botb):
		self.Name = bota.Name
		self.A_APS = bota.APS
		self.B_APS = botb.APS
		self.A_Survival = bota.Survival
		self.B_Survival = botb.Survival
		self.Diff_APS = self.A_APS - self.B_APS
		self.Diff_Survival = self.A_Survival - self.B_Survival
		

class ScoreSet:
	def __init__ (self, name = "", aps = 0.0, survival = 0.0, battles = 0, lastUpload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")):
		self.Name = name
		self.APS = aps
		self.Survival = survival
		self.Battles = battles
		self.LastUpload = lastUpload
		self.KNNPBI = 0
		self.NPP = -1
		
class LiteBot:
	def __init__ (self, bot = None):
		if bot is not None:
			self.Name = bot.Name
			self.Battles = bot.Battles
			self.Pairings = bot.Pairings
			self.APS = bot.APS
			self.Survival = bot.Survival
			self.PL = bot.PL
			self.VoteScore = bot.VoteScore
			self.Rumble = bot.Rumble
			self.LastUpload = bot.LastUpload
			self.Active = bot.Active
			self.ANPP = bot.ANPP
		
class CachedBotEntry:
	def __init__(self,bot):
		self.key_name = bot.key().name()
		self.Name = bot.Name
		self.Battles = bot.Battles
		self.Pairings = bot.Pairings
		self.APS = bot.APS
		self.Survival = bot.Survival
		self.PL = bot.PL
		self.VoteScore = bot.VoteScore
		self.Rumble = bot.Rumble
		self.LastUpload = bot.LastUpload
		self.Active = bot.Active
		self.PairingsList = bot.PairingsList
		self.ANPP = bot.ANPP
		
class BotEntry(db.Model):
	def init_from_cache(self,bot):
		self.key_name = bot.key_name
		self.Name = bot.Name
		self.Battles = bot.Battles
		self.Pairings = bot.Pairings
		self.APS = bot.APS
		self.Survival = bot.Survival
		self.PL = bot.PL
		self.VoteScore = bot.VoteScore
		self.Rumble = bot.Rumble
		self.LastUpload = bot.LastUpload
		self.Active = bot.Active
		self.PairingsList = bot.PairingsList
		self.ANPP = bot.ANPP
		
	#NR = db.StringProperty() --> key_name
	Name = db.StringProperty(indexed = False)
	Battles = db.IntegerProperty(indexed = False)
	Pairings = db.IntegerProperty(indexed = False)
	APS = db.FloatProperty(indexed = False)
	Survival = db.FloatProperty(indexed = False)
	PL = db.IntegerProperty(indexed = False)
	VoteScore = db.FloatProperty(indexed = False,default = 0.0)
	Rumble = db.StringProperty(indexed = False)
	LastUpload = db.StringProperty(indexed = False)
	Active = db.BooleanProperty(indexed = False)
	PairingsList = db.BlobProperty(indexed = False)
	ANPP = db.FloatProperty(indexed = False, default = 0.0)
	
	
#class Uploader(db.Model):
#	#NC = db.StringProperty() --> key_name
#	Name = db.StringProperty(indexed = False)
#	Client = db.StringProperty(indexed = False)
#	LastUpload = db.DateTimeProperty(indexed = False)
#	TotalUploads = db.IntegerProperty(indexed = False)
class User:
    def __init__(self,name,total=0,latest=datetime.datetime.now()):
        self.name = name
        self.total = total
        self.latest = latest
	
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
	AvgBattles = db.FloatProperty(indexed = False, default = 0.0)
	PriorityBattles = db.BooleanProperty(indexed = False, default = True)
	BatchScoresAccurate = db.BooleanProperty(default = False)
	ParticipantsScores = db.BlobProperty(indexed = False)
	


# USAGE:
#	html_header % (Title, PageTitleHeader)
html_header = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>LiteRumble - %s</title><link rel="stylesheet" type="text/css" media="all" href="style.css" /></head><body><h3>%s</h3>"""