"""Tolerate Py2-pickled values left in the shared memcache.

Some entries in App Engine memcache were written by the old python27
service and ``pickle.loads`` them under Py3 raises ``UnicodeDecodeError``.
``memcache.get`` / ``get_multi`` are wrapped to return a cache miss in
that case rather than 500ing the request. The stale entry is left in
place; the next ``set`` of that key overwrites it with a Py3 pickle.
"""
from google.appengine.api import memcache as _mc

_orig_get = _mc.get
_orig_get_multi = _mc.get_multi


def _safe_get(*args, **kwargs):
    try:
        return _orig_get(*args, **kwargs)
    except UnicodeDecodeError:
        return None


def _safe_get_multi(*args, **kwargs):
    try:
        return _orig_get_multi(*args, **kwargs)
    except UnicodeDecodeError:
        return {}


_mc.get = _safe_get
_mc.get_multi = _safe_get_multi
