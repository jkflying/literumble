from functools import wraps

from flask import abort, request
from google.appengine.api import users


def require_cron(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-Appengine-Cron") != "true":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def require_task(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not request.headers.get("X-Appengine-TaskName"):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if (request.headers.get("X-Appengine-Cron") == "true"
                or request.headers.get("X-Appengine-TaskName")):
            return fn(*args, **kwargs)
        if not users.is_current_user_admin():
            abort(403)
        return fn(*args, **kwargs)
    return wrapper
