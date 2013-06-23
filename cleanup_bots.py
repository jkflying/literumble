# -*- coding: utf-8 -*-
"""
Created on Sun Jun 02 13:20:19 2013

@author: jk
"""
games = ["gigarumble","teamrumble","twinduel","roborumble","minirumble","microrumble","nanorumble","meleerumble","minimeleerumble","micromeleerumble","nanomeleerumble"]
for game in games:
    import urllib
    import pprint
    a = urllib.urlopen("http://literumble.appspot.com/Rankings?game=" + game + "&order=-Pairings&api=True")
    b = a.read()
    
    import json
    c = json.loads(b)
    #pprint.pprint(str(c))
    d = filter(lambda e: 2 <= e["name"].count(" "),c)
    pprint.pprint(game + ":")
    e = [f["name"] for f in d]
    pprint.pprint(str(e))
    #f = [urllib.urlopen("http://literumble.appspot.com/RemoveOldParticipant?version=1&game=" + game + "&name=" + g).read() for g in e]
    #pprint.pprint(str(f))