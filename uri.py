"""
nameaddr (URI)

         foo://example.com:8042/over/there?name=ferret#nose
         \_/   \______________/\_________/ \_________/ \__/
          |           |            |            |        |
       scheme     authority       path        query   fragment
          |   _____________________|__
         / \ /                        \
         urn:example:animal:ferret:nose
"""
import sys
from template import MetaTemplate, URITemplate

RFC             = frozenset ((3986, 3305))

#
# XXX : add HierPart
#
class URIHierPart (object):
    path_abempty, path_absolute, path_rootless, path_empty = range (0, 4)

    def __init__ (self):
        self.path_type = path_abempty

    path_create = lambda (self): "//" if self.path_type == path_abempty else \
        "/" if (self.path_type == self.path_absolute or \
                    self.path_type == self.path_noscheme) else \
                    "" # if self.path_type == path_empty

    __str__     = path_create
    __repr__    = path_create

#   The authority component is preceded by a double slash ("//") and is
#   terminated by the next slash ("/"), question mark ("?"), or number
#   sign ("#") character, or by the end of the URI.
class URIAuthorityPart (object):
    __metaclass__ = MetaTemplate
    # authority   = [ userinfo "@" ] host [ ":" port ]
    
    def __init__ (self):
        self.reset ()
        
    def reset (self):
        self.userinfo   = None
        self.host       = None
        self.port       = None

    def fromString (self, data):
        self.reset ()
        data = str (data)
        userinfo_idx = data.find (self.userinfo_separator)
        hostport_idx = data.find (self.hostport_separator)
        if hostport_idx > 0 and hostport_idx < userinfo_idx:
            hostport_idx = data.find (self.hostport_separator, userinfo_idx + 1)
            #raise MalcraftedURI
        if -1 != userinfo_idx:
            self.userinfo = data [:userinfo_idx]
            self.host = data [userinfo_idx:]
        if -1 != hostport_idx:
            port = data [hostport_idx + 1:]
            try:
                self.port = int(port)
            except:
                pass
        host = None
        if userinfo_idx != -1:
            if hostport_idx != -1:
                host = data [userinfo_idx + 1: hostport_idx]
            else:
                host = data [userinfo_idx + 1:]
        elif hostport_idx != -1:
            host = data [:hostport_idx]
        else:
            host = data
        self.host = host
        return
            
    def toString (self):
        s = str ()
        if self.userinfo:
            s += str(self.userinfo)
        if self.host:
            if len(s):
                s += self.userinfo_separator
            s += str(self.host)
        if self.port:
            s += self.hostport_separator
            s += str(self.port)
        return s if len (s) else None

    def strict_checking (self, force = False):
        if force:
            return
        if not self.host and self.port:
            raise "When host is not present, the port is the only value"
        if not self.host and self.user:
            raise "When host is not present, user will be taken for host part"
        if self.port:
            if type(self.port) != int:
                raise "When host is not present, user will be taken for host"\
                    "part"
            elif self.port > 0xFFFFF or self.port < 1:
                raise "Valid range port is previous 0xFFFF"
        return

    __str__     = toString
    __repr__    = toString

#
# XXX UNIMPLEMENTED
#
class URIPathPart (object):
    __metaclass__ = MetaTemplate

    def __init__ (self):
        self.reset ()

    def reset (self):
        self.paths      = []

    def fromString (self, data):
        self.reset ()
        data = str (data)
        path_idx = data.find (self.separator)
        if -1 != path_idx:
            self.paths = [ data ]
            return
        for path in data.split (self.separator):
            if len (path):
                self.paths += [ path ]
        return

    def sanitize (self):
        # every ".." eat one previous element
        pass

    def toString (self, sanity = False):
        if sanity:
            self.sanitize ()
        s = str ()
        for path in self.paths:
            s += self.separator
            s += path
        return s if len (s) else None

    def strict_checking (self, force = False):
        return

    __str__     = toString
    __repr__    = toString
    path        = property (toString)

# Ordered dictionnary
from dictorder import odict

class URIQueryPart (object):
    __metaclass__ = MetaTemplate
#
# XXX : bug with multiple "???" and "?a=b&c&&&d=e"
#
    def __init__ (self):
        self.reset ()

    def reset (self):
        self.params     = odict (default_none = True)
        self.raw_query  = None

    def fromString (self, data):
        self.reset ()
        data = str (data)
        self.raw_query = data
        query_idx = data.find (self.indicator)
        if -1 == query_idx:
            return
        if query_idx != 0:
            return
        for param in data [1:].split (self.separator):
            if len (param):
                param_separator_idx = param.find (self.assertion)
                if param_separator_idx == -1:
                    self.params [param] = None
                else:
                    self.params [param [:param_separator_idx]] = \
                        param [param_separator_idx + 1:]
        return

    def toString (self):
        s = str ()
        if len (self.params):
            s = self.indicator
        else:
            return s
        i = 0
        for param in self.params.keys ():
            if i:
                s += self.separator
            i += 1
            s += param
            if self.params [param]:
                s += self.assertion
                s += str (self.params [param])
        return s if len (s) else None

    def set_tag (self, value):
        if not self.params.has_key ('tag'):
            raise URITagNotFound
        self.params ['tag'] = value

    def strict_checking (self, force = False):
        raise NotImplemented

    __str__     = toString
    __repr__    = toString
    path        = property (toString)
    # FIXME: allow any self.param map self.params['param'] (__setattr__, etc)
    tag         = property (lambda self: self.params ['tag'], set_tag)

class URISchemePart (object):
    __metaclass__ = MetaTemplate

    allowed_protocol = ["sip", "sips"]

    def __init__ (self):
        self.reset ()

    def reset (self):
        self.protocol   = 'sip'
        self.hier_part  = ':'

    def fromString (self, data, strict_check = True):
        self.reset ()
        data    = str (data)
        sep_idx = data.find (self.separator)
        indicator_idx = None
        indicator_len = None
        for ind in self.indicator:
            indicator_idx = data.find (ind)
            if -1 != indicator_idx:
                indicator_len = len (ind)
                break
        if -1 != indicator_idx and -1 != sep_idx:
            if indicator_idx < sep_idx:
                indicator_idx = -1
            else:
                if indicator_idx != sep_idx + 1:
                    raise SchemeError
        if -1 != sep_idx:
            self.protocol = data [:sep_idx]
            if -1 != indicator_idx:
                self.hier_part = data [sep_idx:indicator_idx + indicator_len]
            else:
                self.hier_part = self.separator
        else:
            return 0
        end = 0
        if self.protocol:
            end += len (self.protocol)
        if self.hier_part:
            end += len (self.hier_part)
        if strict_check:
            try:
                self.strict_checking ()
            except:
                self.hier_part = self.protocol = None
                return 0
        return end

    def toString (self):
        s = str ()
        if self.protocol:
            s += self.protocol
        if self.hier_part:
            s += self.hier_part
        return s

    def strict_checking (self, force = False):
        if self.protocol and self.protocol not in self.allowed_protocol:
            raise NotImplemented
        return

    __str__     = toString
    __repr__    = toString

class URI (object):
    __metaclass__ = MetaTemplate
    bracket_pre_query, bracket_post_query = range (1, 3)
    function_list = ['reset', '__getattribute__', '__setattr__', 'noscheme',
                     'fromString', 'toString', 'strict_checking',
                     'setusername']
    uri_objects_list = {"userinfo"      : ("authority", URIAuthorityPart),
                        "host"          : ("authority", URIAuthorityPart),
                        "port"          : ("authority", URIAuthorityPart),
                        "protocol"      : ("scheme", URISchemePart),
                        "hier_part"     : ("scheme", URISchemePart),
                        }

    def __init__ (self):
        self.reset ()

    def reset (self):
        self.scheme             = URISchemePart ()
        self.authority          = None
        #self.path              = None
        self.query              = URIQueryPart ()
        #self.fragment          = None
        #self.nose              = None
        self.bracket_type       = None
        return

    # return a shallow copy
    def copy (self):
        n_uri = URI ()
        # XXX : toString -> fromString SHOULD match, but do proper copying
        n_uri.fromString (str (self))
        return n_uri

    def __getattribute__ (self, name):
        if name in ['__dict__', 'query'] or name in URI.function_list:
            return object.__getattribute__ (self, name)
        uri_objects_list = URI.uri_objects_list
        if uri_objects_list.has_key (name):
            ret = object.__getattribute__ (self, uri_objects_list [name][0])
            if not ret:
                return None
            return getattr (ret, name)
        else:
            try:
                query = object.__getattribute__ (self, 'query')
                return query.params [name]
            except:
                pass
        return object.__getattribute__ (self, name)
      
    def __setattr__ (self, name, value):
        uri_objects_list = object.__getattribute__ (self, 'uri_objects_list')
        if uri_objects_list.has_key (name):
            if not getattr (self, uri_objects_list [name][0]):
                setattr (self, uri_objects_list [name][0],
                         uri_objects_list [name][1] ())
            map_obj = object.__getattribute__ (self, uri_objects_list [name][0])
            return object.__setattr__ (map_obj, name, value)
        return object.__setattr__ (self, name, value)

    def set_bracket (self, bracket_type = None):
        self.bracket_type = bracket_type
        return

    def noscheme (self):
        self.scheme = None

    def fromString (self, data):
        bracket = None
        if data [0] == self.bracket [0]:
            bracket = URI.bracket_post_query if \
                data [-1] == self.bracket [1] else URI.bracket_pre_query
            data = data [1:]
        end = self.scheme.fromString (data) if self.scheme else 0
        if not end:
            self.noscheme ()
        authority = data [end:]
        query = None
        end = authority.find (URITemplate.query_separator)
        if -1 != end:
            query = authority [end:]
            authority = authority [:end]
        if authority [-1] == self.bracket [1]:
            authority = authority [:-1]
            # secure check
            bracket = URI.bracket_pre_query
        self.authority = URIAuthorityPart ()
        end = self.authority.fromString (authority)
        if query:
            if query [-1] == self.bracket [1]:
                query = query [:-1]
                # secure check
                bracket = URI.bracket_post_query
            self.query.fromString (query)
        if None is not bracket:
            self.set_bracket (bracket)
        return

    def toString (self):
        s = str ()
        if None is not self.bracket_type:
            s += self.bracket [0]
        if self.scheme:
            s += str (self.scheme)
        if self.authority:
            s += str (self.authority)
        if self.bracket_pre_query == self.bracket_type:
            s += self.bracket [1]
        if self.query:
            s += str (self.query)
        if self.bracket_post_query == self.bracket_type:
            s += self.bracket [1]
        return s if len (s) else None

    def strict_checking (self, force = False):
        if force:
            return
        if not self.authority and self.scheme and \
                -1 != self.scheme.hier_part.find ("//"):
            raise "When authority is not present, the path cannot begin with "\
                "two slash characters (\"//\")."

    def setusername (self, username):
        if not self.authority:
            self.authority = URIAuthorityPart ()
        self.authority.userinfo = username

    __str__     = toString
    __repr__    = toString

"""
Via: SIP/2.0/UDP XX.YY.ZZZ.157;rport=5060;branch=z9hG4bKmHjragXB2e0me
From: "WIRELESS CALLER" <sip:+18885350800@XX.YY.ZZZ.157>;tag=eBBtFQy4cpaHr
To: <sip:17168461469@XX.YY.ZZZ.154>;tag=385H5Np6y8g8e
Contact: <sip:17168461469@XX.YY.ZZZ.154:5060;transport=udp>
"""
class NAMEADDR (object):
    def __init__ (self):
        self.reset ()

    def reset (self):
        self.display_name       = None
        self.uri                = None
        return

    # return a shallow copy
    def copy (self):
        n_nameaddr = NAMEADDR ()
        n_nameaddr.display_name = self.display_name
        n_nameaddr.uri = self.uri.copy ()
        return n_nameaddr

    def fromString (self, data):
        end_display = None
        if data [0] == "\"":
            j = 1
            while True:
                end_display = data[j:].find ('"')
                if -1 == end_display:
                    break
                end_display += j
                if '\\' == data [end_display - 1]:
                    j = end_display + 2
                    continue
                break
        if end_display:
            self.display_name = data [1:end_display]
            uri = data [end_display + 1:]
            uri = uri.strip (' ')
        else:
            uri = data
        self.uri = URI ()
        self.uri.fromString (uri)
        return

    def toString (self):
        s = str ()
        if self.display_name:
            s += '"' # XXX : from template
            s += self.display_name
            s += '" ' # XXX : from template
        if self.uri:
            s += str (self.uri)
        return s

    __str__     = toString
    __repr__    = toString
