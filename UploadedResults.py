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

import structures



class UploadedResults(webapp.RequestHandler):
	def post(self):
		post_headers = self.request.headers
		post_body = self.request.body
		out_str = "headers: \n"
		for key,value in post_headers:
			out_str += "key: " + key + "   value:" + value + "\n"
		out_str += "\nbody:"
		out_str += post_body
		print out_str
		self.response.out.write(out_str)


application = webapp.WSGIApplication([
	('/UploadedResults', UploadedResults)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
