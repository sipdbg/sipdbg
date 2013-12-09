from sipcore import SIPBody
from dictorder import odict

class SDPParseError (Exception):
    pass

class ConnectionData ():
    """
    <nettype> <addrtype> <connection-address>
    """
    def __init__ (self, data = None):
        self.separator  = ' '
        self.nettype    = None
        self.addrtype   = None
        self.address    = None
        if data:
            self.fromString (data)
        return

    def fromString (self, data):
        self.nettype, self.addrtype, self.address = \
            data.split (self.separator)

    def toString (self):
        return self.separator.join ([self.nettype,
                                     self.addrtype,
                                     self.address])
    
    __str__ = __repr__ = toString

class MediaData ():
    """
    <media> <port> <proto> <fmt> ...
    """
    def __init__ (self, data = None):
        self.separator  = ' '
        self.media      = None
        self.port       = None
        self.proto      = None
        self.fmt        = None
        if data:
            self.fromString (data)
        return

    def fromString (self, data):
        self.media, self.port, self.proto, self.fmt = \
            data.split (self.separator, 3)
        self.port = int (self.port)
        return

    def toString (self):
        return self.separator.join (map (str, [self.media,
                                               self.port,
                                               self.proto,
                                               self.fmt]))
    
    __str__ = __repr__ = toString

class SDP (object):
    sdp_elements = odict ([
            # Session description
            ('v', 'version'),
            ('o', 'originator'),
            ('s', 'session_name'),
            ('i', 'session_title'),
            ('u', 'uri'),
            ('e', 'email'),
            ('p', 'phone'),
            ('z', 'timezone'),
            # Time description
            ('t', 'time'),
            ('r', 'repeat'),
            # Media description
            ('c', 'conndata'),
            ('m', 'mediadata'),
            ('i', 'media_title'),
            ('b', 'bandwitch'),
            ('a', 'attributes'),
            ('k', 'encryption')
            ])
    
    def __init__ (self, data = None):
        self.line_separator     = '\n'
        self.line_ending        = '\r'
        self.map_separator      = '='
        self.reset ()
        if data:
            self.fromString (data)
        return

    def reset (self):
        self.elem = dict () # FIXME : odict ??
        # Session description
        self.version            = None
        self.originator         = None
        self.session_name       = None
        self.session_title      = None
        self.uri                = None
        self.email              = None
        self.phone              = None
        self.timezone           = None
        # Time description
        self.time               = None
        self.repeat             = None
        # Media description
        self.mediadata          = None
        self.media_title        = None
        self.conndata           = None
        self.bandwidth          = None
        self.encryption         = None
        self.attributes         = None
        return

    def fromString (self, data):
        self.reset ()
        lines = data.split (self.line_separator)
        for line in lines:
            line = line.strip (self.line_ending)
            if not len(line):
                break
            e, v = line.split (self.map_separator, 1)
            if self.elem.has_key (e):
                if not list == type (self.elem [e]):
                    self.elem [e] = [self.elem [e]]
                self.elem [e] += [v]
            else:
                self.elem [e] = v
        for k, v in self.elem.items ():
            if SDP.sdp_elements.has_key (k):
                self._set_item (k, v)
        self.parse ()
        return

    _map_object = {'conndata': ConnectionData,
                   'mediadata': MediaData}
    def parse (self, key = None):
        if key and key not in self._map_object.keys ():
            return False
        for k in self._map_object.keys () if not key else [key]:
            if getattr (self, k):
                data = self._map_object [k] ()
                try:
                    data.fromString (getattr (self, k))
                    setattr (self, k, data)
                except:
                    raise SDPParseError ("Warning: cannot parse '%s'"%k)
        return True

    def _set_item (self, k, v):
        if SDP.sdp_elements.has_key (k):
            if getattr (self, SDP.sdp_elements [k], None):
                pass
            setattr (self, SDP.sdp_elements [k], v)
            self.parse (k)
        else:
            self.elem [k] = v
        return

    __setitem__ = lambda self, k, v: self._set_item (k, v)

    def toString (self):
        s = str ()
        for k in SDP.sdp_elements.keys ():
            if self.elem.has_key (k):
                for v in getattr (self, SDP.sdp_elements [k]) if \
                        list == type (getattr (self, SDP.sdp_elements [k])) \
                        else [getattr (self, SDP.sdp_elements [k])]:
                    s += k
                    s += self.map_separator
                    s += str (v)
                    s += self.line_separator
        for k in self.elem.keys ():
            if not SDP.sdp_elements.has_key (k):
                for v in self.elem [k] if list == type (self.elem [k]) else \
                        [self.elem [k]]:
                    s += k
                    s += self.map_separator
                    s += str (v)
                    s += self.line_separator
        return s

    __str__ = __repr__ = toString
    __len__ = lambda self: len (str (self))

if "__main__" == __name__:
    c = """v=0
o=root 117837546 117837546 IN IP4 127.0.0.1
s=Asterisk PBX 1.6.2.9-2+squeeze10
c=IN IP4 127.0.0.1
t=0 0
m=audio 11340 RTP/AVP 8 97
a=rtpmap:8 PCMA/8000
a=rtpmap:97 telephone-event/8000
a=fmtp:97 0-16
a=ptime:20
a=sendrecv"""
    a = SDP ()
    a.fromString (c)
    # print a.conndata.address
    # print a.mediadata.port
    print str(a)
