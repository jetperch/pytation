# Copyright 2022 Jetperch LLC


import json
import re


__all__ = ['load', 'loads', 'dump', 'dumps']

load = json.load
loads = json.loads
_re_dump = re.compile(r'\[[^\[\]\{\}]+\]')
_re_replace = re.compile(r'\s*\n\s*')


def _json_default(obj):
    return '__pyobject__'


def _replace(matchobj):
    s = matchobj.group(0)
    return _re_replace.sub(' ', s)


def dump(obj, f, *args, **kwargs):
    s = dumps(obj, *args, **kwargs)
    f.write(s)


def dumps(*args, **kwargs):
    kwargs.setdefault('indent', 2)
    kwargs.setdefault('default', _json_default)
    s = json.dumps(*args, **kwargs)
    return _re_dump.sub(_replace, s)
