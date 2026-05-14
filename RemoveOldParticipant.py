#!/usr/bin/env python
import pickle
import zlib

from flask import request
from google.appengine.api import memcache

import structures
from structures import load_blob


def nth_repl(s, sub, repl, nth):
    find = s.find(sub)
    i = find != -1
    while find != -1 and i != nth:
        find = s.find(sub, find + 1)
        i += 1
    if i == nth:
        return s[:find] + repl + s[find + len(sub):]
    return s


def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)


def remove_old_participant():
    if request.method == "POST":
        raw = request.get_data(as_text=True)
    else:
        raw = request.query_string.decode('utf-8')

    parts = raw.split("&")
    requests = {}
    if parts[0] != "":
        for pair in parts:
            ab = pair.split('=')
            if len(ab) == 2:
                requests[ab[0]] = ab[1]
    return _remove_from_rumble(requests)


def _remove_from_rumble(requests):
    global_dict = {}
    if "version" not in requests or requests["version"] != "1":
        return "ERROR. bad/no version"

    game = requests.get("game", None)
    if game is None:
        return "ERROR. no game specified"

    name = requests.get("name", None)
    if name is None:
        return "ERROR. no name specified"
    while name.count("%20") > 0:
        name = rreplace(name, "%20", " ", 1)

    rumble = global_dict.get(game, None)
    if rumble is None:
        rumble = memcache.get(game)
        if rumble is None:
            rumble = structures.Rumble.get_by_key_name(game)

    entry = None
    keyhash = None
    if name.count(" ") == 0:
        num_underscores = name.count("_")
        error_messages = []
        for n in range(num_underscores):
            check_name = nth_repl(name, "_", " ", n + 1)

            keyhash = check_name + "|" + game
            entry = global_dict.get(keyhash, None)
            if entry is None:
                entry = memcache.get(keyhash)
                if entry is None:
                    entry = structures.BotEntry.get_by_key_name(keyhash)
                    if entry is None:
                        error_messages.append("ERROR. name/game does not exist: " + check_name + "/" + game)
                    else:
                        entry = structures.CachedBotEntry(entry)

            if entry is not None:
                name = check_name
                break
        if entry is None:
            return "\n".join(error_messages)
    else:
        return "ERROR. Bot name missing version."

    if isinstance(entry, structures.BotEntry):
        entry = structures.CachedBotEntry(entry)

    global_dict.pop(keyhash, 0)
    memcache.delete(keyhash)

    entry.Active = False

    scores = load_blob(rumble.ParticipantsScores, {})
    if not isinstance(scores, dict):
        scores = {}

    scores.pop(name, 1)
    rumble.ParticipantsScores = zlib.compress(pickle.dumps(scores, pickle.HIGHEST_PROTOCOL), 4)

    memcache.delete("home")
    global_dict.pop("home", 0)

    memcache.set(entry.key_name, entry)
    global_dict[entry.key_name] = entry
    modelBot = structures.BotEntry(key_name=entry.key_name)
    modelBot.init_from_cache(entry)
    modelBot.put()

    global_dict[game] = rumble
    memcache.set(game, rumble)
    rumble.put()

    return "OK. " + name + " retired from " + game
