import random
import uuid

class NoUUIDHost (Exception):
    pass

def get_alphanum_random (_len = 16):
    return ''.join(random.choice('0123456789ABCDEFabcdef') for i in range(_len))

def tag_new ():
    return get_alphanum_random (12)

fromtag_new = totag_new = tag_new

def callid_new (host = None):
    if not host:
       raise NoUUIDHost (host)
    return str (uuid.uuid4 ()) + "@" + str (host)

def branch_new ():
    magic_cookie = "z9hG4bK"
    return '%s%s'%(magic_cookie, get_alphanum_random ())

def cseq_new ():
    return random.randrange (1, 10000)

"""
Via
Max-Forwards
From
To
Call-ID
Cseq
Contact
User-Agent: ?
Content-Length
"""
