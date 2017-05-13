#!/usr/bin/env python

import re
import itertools as it


def bencode(obj):
    if isinstance(obj, int):
        # int -> bytestring, i***e
        return b"i" + str(obj).encode() + b"e"
    elif isinstance(obj, bytes):
        # bytes -> len:***
        return str(len(obj)).encode() + b":" + obj
    elif isinstance(obj, str):
        # str -> bytes and call bencode
        return bencode(obj.encode("utf-8"))
    elif isinstance(obj, list):
        # list -> bencode each item, l***e
        return b"l" + b"".join(map(bencode, obj)) + b"e"
    elif isinstance(obj, dict):
        # dict -> bencode each item, d***e
        if all(isinstance(i, bytes) for i in obj.keys()):
            items = list(obj.items())
            items.sort()
            return b"d" + b"".join(map(bencode, it.chain(*items))) + b"e"
        else:
            raise ValueError("dict keys should be bytes")
    raise ValueError("Allowed types: int, bytes, list, dict; not %s", type(obj))


def bdecode(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    if isinstance(s, bytes):
        ret, extra = _decode_component(s)
        return ret
    else:
        raise ValueError("Input must be of type (bytes), not {}".format(type(s)))


def _decode_component(s):
    # if you see an i, grab everything between i and e, convert it to an int, and return it plus the rest of the input
    if s.startswith(b"i"):
        match = re.match(b"i(-?\\d+)e", s)
        return int(match.group(1)), s[match.span()[1]:]
    # lists or dicts get processed piece by piece
    elif s.startswith(b"l") or s.startswith(b"d"):
        l = []
        rest = s[1:]
        while not rest.startswith(b"e"):
            elem, rest = _decode_component(rest)
            l.append(elem)
        rest = rest[1:]
        if s.startswith(b"l"):
            return l, rest
        else:
            return {i: j for i, j in zip(l[::2], l[1::2])}, rest
    elif s[0] in b"1234567890":
        match = re.match(b"(\\d+):", s)
        string_length = int(match.group(1))
        start = match.span()[1]
        end = start + string_length
        return s[start:end], s[end:]
    else:
        raise ValueError("Malformed input: {} did not match any identifier".format(s[0]))
