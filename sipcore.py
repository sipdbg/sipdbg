import sys

from codes import sip_codes
from uri import *
from template import MetaTemplate

# Ordered dictionnary
from dictorder import odict

debug           = False

# main Exception class
class SipcoreException (Exception):
      pass

class RURIParseError (SipcoreException):
      pass
class SIPVersionParseError (SipcoreException):
      pass
class HeaderNotFound (SipcoreException):
      pass
class ElementNotFound (SipcoreException):
      pass
class InvalidCseq (SipcoreException):
      pass
class InvalidVia (SipcoreException):
      pass
class HeaderParseError (SipcoreException):
      pass
class HeaderError (SipcoreException):
      pass

# SIP/2.0/UDP
class SIPVersion (object):
      __metaclass__ = MetaTemplate

      def __init__ (self, strict_checking = False):
            self._id            = self.id
            self.sip_rev        = self.revision
            self.sip_proto      = None
            self.strict_checking = strict_checking

      # return a shallow copy
      def copy (self):
            n_version = SIPVersion ()
            n_version._id = self._id
            n_version.sip_rev = self.sip_rev
            n_version.sip_proto = self.sip_proto
            n_version.strict_checking = self.strict_checking
            return n_version

      def set_protocol (self, proto = None):
            self.sip_proto = proto or self.proto

      def fromString (self, value):
            self._id, self.sip_rev, self.sip_proto = \
                value.split (self.separator, 2)
            if self.strict_checking:
                  try:
                        self.sip_rev = float (self.sip_rev)
                        if self._id != self.id:
                              raise
                        if self.sip_rev != self.revision:
                              raise
                        if self.sip_proto and \
                                  self.sip_proto not in self.proto_list:
                              raise
                  except:
                        raise SIPVersionParseError
            return

      def toString (self):
            s = [self._id, self.sip_rev]
            if self.sip_proto:
                  s += [self.sip_proto]
            return self.separator.join (s)

      __str__ = __repr__ = toString

      version = property (lambda self: self._version, fromString)

class SIPRuri (object):
      __metaclass__ = MetaTemplate
      
      def __init__ (self):
            self.method         = None
            self.code           = None
            self._reason        = None
            self.uri		= URI ()
            self.version	= SIPVersion ()

      def _set_method (self, value):
      	  self.method	= str (value)

      def _set_code (self, value):
      	  self.code	= int (value)

      def _set_uri (self, value):
      	  self.uri	= value

      # return a shallow copy
      def copy (self):
            n_ruri = SIPRuri ()
            n_ruri.method = self.method
            n_ruri.code = self.code
            n_ruri._reason = self._reason
            n_ruri.uri = self.uri.copy ()
            n_ruri.version = self.version.copy ()
            return

      def fromString (self, value):
          method_arr = value.split (self.method_separator, 2)
          uri = None
          if not method_arr or 3 > len (method_arr):
                raise RURIParseError
          if method_arr [1].isdigit ():
                version, self.code, self.reason = method_arr
                self.code = int (self.code)
          else:
                self.method, uri, version = method_arr
          try:
                if uri:
                      u = URI ()
                      u.fromString (uri)
                      uri = u
          except:
                pass
          finally:
                self.uri = uri
          try:
                self.version = SIPVersion ()
                SIPVersion ().fromString (version)
          except:
                self.version = version
      	  return

      def get_reason (self):
            if None is self.code:
                  return None
            try:
                  return sip_codes [int (self.code)]
            except KeyError:
                  return "Unknown"
            return

      def toString_code (self):
            s = 'SIP/2.0' # XXX : Fix SipVersion
            # s = str(self.version)
            s += self.version_separator
            s += str (self.code)
            s += self.code_separator
            s += str(self.reason)
            return s

      def toString_req (self):
            s = str (self.code) if self.code else self.method
            s += self.method_separator
            s += str(self.uri)
            s += self.version_separator + str(self.version)
            return s

      def toString (self):
            return self.toString_code () if self.code else self.toString_req ()

      def set_reason (self, value):
            self._reason = value

      reason = property (lambda self:
                               self.get_reason () if not self._reason else \
                               self._reason,
                         set_reason)

      __str__ = __repr__ = toString

class SIPBody (object):
      __metaclass__ = MetaTemplate

      def __init__ (self):
            self._data	= str ()
            self.len	= False
            self.mime	= None

      # return a shallow copy
      def copy (self):
            s_body = SIPBody ()
            s_body._data = self._data
            s_body.len = self.len
            s_body.mime = self.mime
            return s_body

      def toString (self):
            return str (self.data)

      def set_body (self, value):
            self._data = value
            self.len = len (self._data)

      __len__ = lambda self: len (self._data)

      __str__ = __repr__ = toString

      data = property (lambda self: self._data, set_body)

class SIPBodyXML (SIPBody):
      pass

class SIPHeader (object):
      __metaclass__ = MetaTemplate

      sep               = None
      # Header types
      __reserved__      = ['Int', 'URI']

      def __init__ (self, key = None, value = None):
            self.mapping        = []
            n = self._get_name ()
            self.key = n if len (n) else str (key) if key else None
            self.value = str (value) if value else None
            self.unparsed_value = None
            if debug:
                  print "key = [%s], value = [%s]"%(self.key, self.value)

      def fromString (self, data):
            if data.find (self.value_separator) == -1:
                  return False
            self.key, self.value = data.split (self.value_separator, 1)
            while len (self.value) and self.value [0] in self.prefix_value:
                  self.value = self.value [1:]
            return

      def toString (self):
            s = str ()
            s += str (self.value)
            return s

      def _get_name (self, name = None, sep = None):
            """
            header name render
            """
            if not name:
                  name = self.__class__.__name__ [9:]
            if not sep:
                  sep = self.sep
            _n = name
            if _n in self.__reserved__:
                  return str ()
            for i, c in enumerate (_n) if sep else list ():
                  if i and c.isupper () and (_n [i - 1].islower () or
                                             _n [i + 1].islower ()):
                        return _n [:i] + sep + _n [i:]
            return _n

      # 
      @staticmethod
      def get_header_name (header_name):
            header_name = header_name[0].upper () + header_name [1:]
            header_name = header_name.replace ('-', '')
            return header_name

      @staticmethod
      def py_header_name (header_name):
            header_name = header_name.replace ('-', '_')
            header_name = header_name.lower ()
            return header_name

      def set_value (self, value):
            self.value = value

      enable = lambda self: None
      # default function
      map = lambda self: None
      def parse (self, data):
            self.value = data

      __str__ = __repr__ = toString

class SIPHeaderInt (SIPHeader):
      __trunc__ = lambda self: int (self.value)

      def parse (self, data):
            self.value = int (self.value)

class SIPHeaderURI (SIPHeader):
      def parse (self, data):
            nameaddr = NAMEADDR ()
            nameaddr.fromString (data)
            self.value = nameaddr
      # FIXME : add mapcomplex__ to map :
      # return [("uri", self.value,         "uri"),
      #         ("userinfo", self.value.uri,"userinfo"),
      #         ("host", self.value.uri,    "host"),
      #         ("port", self.value.uri,    "port")]

      # FIXME
      # def __setattr__ (self, name, value):
      #       if value in ['value']:
      #             return object.__setattr__ (self, value)
      #       print "__setattr : name:%s, value:%s"% (name, value)
      #       return object.__setattr__ (self.value.query.params [name], value)

"""
SipCore
"""
class SipCoreRURI (object):
      ruri = property (lambda self: self.request.uri, lambda self,
                       value: self.request._set_uri (value))
      method = property (lambda self: self.method, lambda self,
                         value: self.method._set_method (value))

class SipCoreHeader (object):

      header_name_render = lambda self, key: key.replace ('_', '-')

      # XXX : add in odict multiple 'key' feature (sort)
      def _header_add (self, h, overwrite = True, mapping = None):
            if mapping:
                  mapping = SIPHeader.py_header_name (mapping)
            if self.hdr.has_key (h.key):
                  if overwrite:
                        self.header_del (h.key, True)
                        self.hdr [h.key] = []
                  elif debug:
                        print "multiple %s"%h.key
            else:
                  self.hdr [h.key] = []
            self.hdr [h.key] += [h]
            if mapping:
                  h.mapping += [ mapping ]
                  object.__setattr__ (self, mapping, h)
            return

      def header_add (self, key, value, overwrite = True):
            header_name_like = SIPHeader.get_header_name (key)
            header_name_like = self.header_name_render (header_name_like)
            hclass = SIPHeaderInt if int == type (value) else SIPHeader
            h = hclass (header_name_like, value)
            self._header_add (h, overwrite, mapping = header_name_like)
            return h

      # FIXME : rewrite mapping rewrite in _del method
      def _header_del (self, h):
            k = h.key
            m = h.mapping
            self.hdr [h.key].remove (h)
            if not len (self.hdr [h.key]):
                  del (self.hdr [h.key])
                  # mapping
                  for mname in m:
                        delattr (self, mname)
            else:
                  for mname in m:
                        delattr (self, mname)
                        if mname in self.hdr [h.key][0].mapping:
                              setattr (self, mname, self.hdr [h.key][0])

      def header_del (self, key, overwrite = True, idx = None):
            if not self.hdr.has_key (key):
                  raise HeaderNotFound
            if idx is None:
                  if not overwrite:
                        # delete mapping
                        for mname in self.hdr [key][i].mapping:
                              delattr (self, mname)
                        del (self.hdr [key])
                  else:
                        # delete mapping
                        m = self.hdr [key][0].mapping
                        self.hdr [key].pop (0)
                        # rewrite mapping
                        for mname in m:
                              delattr (self, mname)
                              if len (self.hdr [key]) and mname in \
                                        self.hdr [key][0].mapping:
                                    setattr (self, mname, self.hdr [key][0])
                        if not len (self.hdr [key]): # FIXME ????
                              del (self.hdr [key])
                  return True
            elif len (self.hdr [key]) <= idx:
                  self.hdr [key].pop (idx)
                  # FIXME : write mapping deletion / rewrite
                  return True
            return False
            
      def header_fromString (self, data, overwrite = True):
            h = SIPHeader ()
            h.fromString (data)
            self._header_add (h, overwrite)
            return

      def header_toString (self, key = None):
            s = str ()
            for _h in self.hdr [key] if key else self.hdr:
                  for h in self.hdr [_h]:
                        _header_name = self._get_header_classname (h.key)
                        hclass = self._is_header (h.key) or SIPHeader
                        if _header_name:
                              _header_name = h._get_name (_header_name [9:],
                                                          hclass.sep)
                        else:
                              _header_name = h.key
                        s += _header_name
                        s += h.value_separator + h.prefix_value
                        try:
                              s += str (h)
                        # NOTE : every error in toString() should be derived
                        # from SipcoreException
                        #except (SipcoreException), e:
                        except (Exception, SipcoreException), e:
                              if None is not h.unparsed_value:
                                    s += h.unparsed_value
                              else:
                                    raise e
                        s += self.line_ending
            return s

      def header_get (self, key):
            return self.hdr [key] if self.hdr.has_key (key) else None

      header_exist = lambda self, key: self.hdr.has_key (key)

class SipCoreBody (object):
      def set_body (self, value, mime = None):
            self.body.len = len (value)
            self.body.data = str (value)
            if mime:
                  self.body.mime = mime
            return

class SIPpacket (SipCoreRURI, SipCoreHeader, SipCoreBody):
      __metaclass__ = MetaTemplate

      def __init__ (self, data = None):
            self.mapcomplex__   = {}
            self.hdr_list__     = {}
            self.hdr            = odict ()
            self.request	= SIPRuri ()
            self.body           = SIPBody ()
            self.autoadd_clen   = True
            self._data          = None
            if data:
                  self.fromString (data)
            return

      # return a shallow copy
      def copy (self):
            raise NotImplemented
            n_pkt = SIPpacket ()
            # XXX : (shallow copy elements)
            n_pkt.hdr = self.hdr.copy () # XXX 
            n_pkt.hdr_list__ = self.hdr_list__.copy () # XXX
            n_pkt.request = self.request.copy ()
            n_pkt.body = self.body.copy ()
            n_pkt.autoadd_clen = self.autoadd_clen
            n_pkt._data = self._data
            if self.mapcomplex__:
                  n_pkt.enable ()
            return n_pkt

      # user data
      def set_data (self, data):
            self._data = data
      get_data = lambda self: self._data

      def map_packet_element (self):
            self._map_packet_element = [
                  ('ru', self.request, 'uri'),
                  ('rm', self.request, 'method'),
                  ('rr', self.request, 'reason'),
                  ('rs', self.request, 'code'),
                  ('uuid', self.hdr, 'Call-ID', 0),
                  ('callid', self.hdr, 'Call-ID', 0) ]
            if self.request:
                  _ruri = [('rd', self.request.uri, 'host'),
                           ('rp', self.request.uri, 'port'),
                           ('rU', self.request.uri, 'userinfo')]
                  self._map_packet_element.extend (_ruri)
            for mkey in self._map_packet_element:
                  self._mapcomplex (*mkey)
            return

      def enable (self, headers = True):
            self.map_packet_element ()
            if not headers:
                  return
            # TODO : FIXME : parse all headers

      def toURI (self, header_name):
            header_name_like = SIPHeader.get_header_name (header_name)
            if not self.hdr.has_key (header_name_like):
                  return None
            header = self.hdr [header_name_like][0]
            h = SIPHeaderURI ()
            h.key = header.key
            h.parse (header.value)
            self._header_del (header)
            self._header_add (h, mapping = header_name)
            mapkey = h.map ()
            for mkey in mapkey if mapkey else list ():
                  self._mapcomplex (*mkey)
            return h
      
      def __getattribute__ (self, name):
            # exception
            if "__" in [name[:2], name [-2:]] or "hdr" == name:
                  return object.__getattribute__ (self, name)
            # FreeSwitch-like's _h_ headers mapping
            if name [:3] == "_h_":
                  name = name [3:]
                  return self.__getattribute__ (name)
            # exception : python reserved word
            if name == "_from":
                  name = "from"
            if name in self.mapcomplex__.keys ():
                  try:
                        c = getattr (self,
                                     'mapcomplex__')[name][0].__getattribute__ (
                              self.mapcomplex__ [name][1])
                  except KeyError, e:
                        raise ElementNotFound (e)
                  return c if not int == type (self.mapcomplex__[name][2]) else\
                      c [self.mapcomplex__ [name][2]]
            if debug:
                  print "entering [%s]"%name
            try:
                  return object.__getattribute__ (self, name)
            except:
                  pass
            # header
            hdrlikename = SIPHeader.get_header_name (name)
            if self.__dict__.has_key (hdrlikename):
                  print "existing %s"%hdrlikename
                  # existing
                  return object.__getattribute__ (self, hdrlikename)
            found = False
            for k in self.hdr.keys ():
                  krw = k.lower ()
                  krw = krw.replace ('-', '')
                  if krw == hdrlikename.lower ():
                        found = True
                        hdrlikename = self.hdr [k][0].key
                        break
            #hdrlikename = SIPHeader.get_header_name (hdrlikename)
            if not found:
                  raise KeyError, name
            oldhdr = self.hdr [hdrlikename][0]
            data = oldhdr.value
            # Header handler : allocated __when_accessed__
            hclass = self._is_header (SIPHeader.get_header_name (
                        hdrlikename))
            if hclass:
                  if debug:
                        print "Adding header on read %s:%s"%(name, hclass)
                  # instanciate the existing header
                  h = hclass ()
                  # parse it's value
                  h.parse (data)
                  # create the mapping
                  mapkey = h.map ()
                  for mkey in mapkey if mapkey else list ():
                        self._mapcomplex (*mkey)
                  # add it internally
                  self._header_add (h, mapping = name)
                  return h
            raise
      
      def __init_header__ (self):
            """
            This function will build an exhaustive list of supported headers
            """
            if self.hdr_list__:
                  return
            self.hdr_list__ = {}
            for h in sys.modules [__name__].__dict__.keys (): # XXX
                  if len (h) > 9 and 'SIPHeader' == h [0:9]:
                        if issubclass (getattr (sys.modules [__name__], h),
                                       SIPHeader):
                              self.hdr_list__ [h [9:].lower ()] = \
                                  getattr (sys.modules [__name__], h)
            return

      def _get_header_classname (self, name):
            """
            Get a name and return the header object classname (if any)
            Exemple : ContentLength -> contentlength -> SIPHeaderContentLength
            """
            h = self._is_header (name)
            return h.__name__ if h else None

      def _is_header (self, name):
            """
            Return SIPHeader instance for given name, if any
            """
            name = name.lower ()
            if not self.hdr_list__:
                  self.__init_header__ ()
            return self.hdr_list__ [name] if self.hdr_list__.has_key (name) \
                else None

      def __setattr__ (self, name, value):
            # exception : python reserved word
            if name == "_from":
                  name = "from"
                  self.__setattr__ (name, value)
            # exceptions
            # XXX: working on __dict__ to avoid __getattribute__
            if self.__dict__.has_key (name):
                  X = self.__dict__ [name]
                  if isinstance (X, SIPHeader):
                        return object.__setattr__ (X, 'value', value)
            if "__" == name [-2:]:
                  return object.__setattr__ (self, name, value)
            # headers
            if name [:3] == "_h_" or self._is_header (name):
                  name = name [3:] if name [:3] == "_h_" else name
                  name = name.lower ()
                  hdrlikename = name [0].upper () + name [1:].lower ()
                  if self.hdr.has_key (hdrlikename):
                        h = self.hdr [hdrlikename][0]
                        h.value = value
                        try:
                              h.parse (str (value))
                        except SipcoreException, e:
                              h.unparsed_value = str (value)
                        # create the mapping
                        mapkey = h.map ()
                        for mkey in mapkey if mapkey else list ():
                              self._mapcomplex (*mkey)
                        return True
                  hclass = self._is_header (name)
                  # create header
                  if hclass:
                        h = hclass ()
                        data = h._get_name ()
                        data += h.value_separator + h.prefix_value
                        data += str (value)
                        # fromString : work on the header line
                        h.fromString (data)
                        # parse : process the header's value
                        try:
                              h.parse (str (value))
                        #except SipcoreException, e:
                        except (Exception, SipcoreException), e:
                              h.unparsed_value = str (value)
                        # create the mapping
                        mapkey = h.map ()
                        for mkey in mapkey if mapkey else list ():
                              self._mapcomplex (*mkey)
                        self._header_add (h, mapping = name)
                  else:
                        h = self.header_add (hdrlikename, value)
                  return None
            # complex element mapping
            elif name in object.__getattribute__ (self, 'mapcomplex__').keys ():
                  try:
                        return getattr (self, 'mapcomplex__')[name][0].\
                            __setattr__ (self.mapcomplex__ [name][1], value)
                  except:
                        return getattr (self, 'mapcomplex__')[name][0].\
                            __setitem__ (self.mapcomplex__ [name][1], value)
            return object.__setattr__ (self, name, value)

      def _mapcomplex (self, key, objinst, truekey, idx = None):
            """
            Map local variable with within-object variable
            """
            self.mapcomplex__ [key] = [objinst, truekey, idx]
          
      def _map (self, key, val):
            """
            Add a map's name to an object
            """
            if type (val) is not object:
                  raise
            setattr (self, key, val)

      def toString (self):
            s = str ()
            # add RURI
            s += str (self.request) + self.line_ending
            # body (needed previous to header because it deal with them)
            if self.body.len is not False:
                  if not self.hdr.has_key ("Content-Length") \
                            and self.body.len:
                        self.header_add ("Content-Length", self.body.len)
                  if not self.hdr.has_key ("Content-Type") \
                            and self.body.mime:
                        self.header_add ("Content-Type", self.body.mime)
            elif self.autoadd_clen and not self.hdr.has_key ("Content-Length"):
                  self.header_add ("Content-Length", str (0))
            # add header
            if len (self.hdr):
                  s += self.header_toString ()
            # add body if any
            if self.body.len is not False:
                  s += "\r\n"
                  s += str (self.body)
            else:
                  s += self.body_separator
            return s

      def fromString (self, data, debug = False):
            # parse packet
            # line ending separator ? permissive
            if not debug:
                  line_ending = self.line_ending
                  body_separator = self.body_separator
            else:
                  line_ending = '\n' if \
                      -1 == data.find (self.line_ending) else self.line_ending
                  # body ?
                  body_separator = '\n\n' if '\n' == line_ending else \
                      self.body_separator
            body_idx = data.rfind (body_separator)
            lines = data.split (line_ending) if body_idx is -1 else \
                data [:body_idx].split (line_ending)
            if not len (lines):
                  return None
            # RURI parsing
            self.request.fromString (lines [0])
            # headers parsing
            for line in lines [1:]:
                  if len (line):
                        self.header_fromString (line, False)
            # body parsing
            if -1 != body_idx:
                  self.body.data = data [body_idx + len (body_separator):]
                  self.body.len = len (self.body.data)
                  if self.hdr.has_key ("Content-Type"):
                        if len (self.hdr ["Content-Type"]) != 1:
                              return
                        self.body.mime = self.hdr ["Content-Type"][0].value
            # binding
            self.map_packet_element ()
            return

      __str__ = toString
#
# headers
#
class SIPHeaderCallID (SIPHeader):
      sep = '-'
      uuid = property (lambda self: self.value, lambda self,
                     value : self.set_value(value))
      def map (self):
            return [("callid", self,        "uuid")]

class SIPHeaderUserAgent (SIPHeader):
      sep = '-'
      ua = property (lambda self: self.value, lambda self,
                     value : self.set_value(value))
      def map (self):
            return [("ua", self,        "ua")]

class SIPHeaderMaxForwards (SIPHeaderInt):
      sep = '-'
      hop = property (lambda self: self.value, lambda self,
                      value : self.set_value(value))
      
class SIPHeaderContentLength (SIPHeaderInt): # FIXME
      sep = '-'

class SIPHeaderContentType (SIPHeader):
      sep = '-'

class SIPHeaderRecordRoute (SIPHeader):
      sep = '-'

class SIPHeaderCSeq (SIPHeader):

      def __init__ (self, key = 'cseq', value = None):
            super (SIPHeaderCSeq, self).__init__ (key, value)
            self.method_separator = ' '
            self.seq    = None
            self.data   = None
            if value:
                  self.parse (self.value)

      def parse (self, data):
            self.seq, self.method = data.split (self.method_separator, 1)
            self.seq = int(self.seq)

      def toString (self):
            if None is self.seq or not self.method:
                  raise InvalidCseq
            s = str ()
            s += str(self.seq)
            s += self.method_separator
            s += str (self.method)
            return s

      def map (self):
            return [("cs", self, "seq")]

      seq = property (lambda self: self.value, lambda self,
                      value : self.set_value(value))

      __str__ = __repr__ = toString

class SIPHeaderVia (SIPHeader):
      
      def __init__ (self, key = 'via', value = None):
            super (SIPHeaderVia, self).__init__ (key, value)
            self.version_separator = ' '
            self.version        = SIPVersion ()
            self.version.set_protocol ()
            self.uri            = None
            if value:
                  self.parse (self.value)

      def parse (self, data):
            try:
                  version,self.uri = data.split (self.version_separator, 1)
                  self.version.fromString (version)
            except:
                  self.uri = data
            uri = URI ()
            uri.fromString (self.uri)
            self.uri = uri

      def toString (self):
            if not self.version or not self.uri:
                  raise InvalidVia
            s = str ()
            s += str(self.version)
            s += self.version_separator
            s += str (self.uri)
            return s

      def map (self):
            return [("vb", self.uri.query.params, "branch")]

      __str__ = __repr__ = toString

class SIPHeaderAllow (SIPHeader):
      
      def __init__ (self, key = 'via', value = None):
            super (SIPHeaderAllow, self).__init__ (key, value)
            self.methods_separator      = [', ', ',']
            self.method_separator       = None
            self.methods                = []
            if value:
                  self.parse (self.value)

      def parse (self, data):
            for method_separator in self.methods_separator:
                  if -1 is not data.find (method_separator):
                        self.method_separator = method_separator
            if not self.method_separator:
                  raise HeaderParseError # FIXME : Exception.HeaderParseError
            self.methods = data.split (self.method_separator)
            return

      def toString (self):
            return self.method_separator.join (self.methods)

      __str__ = __repr__ = toString

class SIPHeaderFrom (SIPHeaderURI):
      def map (self):
            return [("fU", self.value.uri,      "userinfo"),
                    ("fd", self.value.uri,      "host"),
                    ("fn", self.value,          "display_name"),
                    ("ft", self.value.uri.query,"params"),
                    ("fp", self.value.uri.query.params, "tag"),
                    ("fu", self.value,          "uri"),
                    ]

class SIPHeaderTo (SIPHeaderURI):
      def map (self):
            return [("tU", self.value.uri,      "userinfo"),
                    ("td", self.value.uri,      "host"),
                    ("tn", self.value,          "display_name"),
                    ("tt", self.value.uri.query,"params"),
                    ("tp", self.value.uri.query.params, "tag"),
                    ("tu", self.value,          "uri"),
                    ]
      def _set_tag (self, value = None):
            self.value.uri.query.params ['tag'] = value
      tag = property(lambda self: self.value.uri.query.params ['tag'], _set_tag)

class SIPHeaderContact (SIPHeaderURI):
      pass

class SIPHeaderExpires (SIPHeaderInt):
      pass

class SIPHeaderProxyAuthenticate (SIPHeader):
      sep               = '-'
      
      def __init__ (self, key = 'proxyauthenticate', value = None):
            super (SIPHeaderProxyAuthenticate, self).__init__ (key, value)
            self.version_separator = ' '
            self.scheme         = None
            self._param         = None
            self.realm          = None
            self.nonce          = None
            if value:
                  self.parse (self.value)

      def parse (self, data):
            # XXX : use self.separator, etc
          auth_scheme, params = data.split (' ', 1)
          params = params.split (',')
          obj = odict ()
          for param in params:
              param = param.strip (' ')
              if -1 == param.find ('='):
                  print "Invalid param :'%s'"%param
                  continue
              name, value = param.split ('=', 1)
              name = name.rstrip (' ')
              value = value.strip (' ')
              if value[0] == value [-1] and value [0] in ['"', "'"]:
                  value = value [1:-1]
              obj [name.lower ()] = value
          self.scheme = auth_scheme
          self._params = obj
          self.realm = self._params ['realm']
          self.nonce = self._params ['nonce']
          return

      def toString (self):
            s = str ()
            s += "%s"%self.scheme
            for i, kv in enumerate (self._params.iteritems ()):
                  _k, v = kv
                  if not i:
                        s += " %s=%s"%(_k, v)
                  else:
                        s += ",%s=%s"%(_k, v)
            return s

      __str__ = __repr__ = toString

class SIPHeaderWWWAuthenticate (SIPHeaderProxyAuthenticate):
      sep = '-'

import hashlib
class SIPHeaderAuthorization (SIPHeader):
      sep               = '-'
      version_separator = ' '

      def __init__ (self, key = 'authorization', value = None):
            super (SIPHeaderAuthorization, self).__init__ (key, value)
            self.username       = None
            self.password       = None
            self.realm          = None
            self.nonce          = None
            self.uri            = None
            self.response       = None
            self.algorithm      = 'MD5'
            self.scheme         = 'Digest'
            self.method         = 'INVITE' # REGISTER ?
            self.params         = {}
            if value:
                  self.parse (self.value)

      def parse (self, data):
            if not data:
                  return
            scheme, params = data.split (' ', 1)
            params = params.split (',')
            obj = odict (default_none = True)
            for param in params:
                  param = param.strip (' ')
                  if -1 == param.find ('='):
                        print "Invalid param :'%s'"%param
                        continue
                  name, value = param.split ('=', 1)
                  name = name.rstrip (' ')
                  value = value.strip (' ')
                  if value[0] == value [-1] and value [0] in ['"', "'"]:
                        value = value [1:-1]
                  obj [name.lower ()] = value
            self.scheme = scheme
            self.params = obj
            self.realm = self._params ['realm']
            self.nonce = self._params ['nonce']
            # XXX: add remote timestamp detection from nonce (work on opensips)
            # self._timestamp = time.time (self.nonce [:9])
            self.username = self._params ['username']
            self.uri = self._params ['uri']
            self.response = self._params ['response']
            self.algorithm = self._params ['algorithm']
            return

      def toString (self):
            if not self.username or not self.uri or not self.password or not \
                      self.realm or not self.nonce:
                  raise HeaderError
            s = str ()
            m = hashlib.md5()
            m.update ('%s:%s:%s'% (self.username, self.realm, self.password))
            A1 = m.hexdigest()
            m2 = hashlib.md5 ()
            m2.update ("%s:%s"% (self.method, self.uri))
            A2 = m2.hexdigest ()
            final = hashlib.md5 ()
            final.update (A1 + ":" + self.nonce + ":" + A2)
            params = odict ()
            params ['username'] = self.username
            params ['realm'] = self.realm
            params ['nonce'] = self.nonce
            params ['uri'] = self.uri
            params ['response'] = final.hexdigest ()
            s += '%s '%self.scheme + ','.join ('%s="%s"'%(k, v) for k,v in \
                                                     params.items ())
            s += ',algorithm=%s'%self.algorithm
            return s

      def map (self):
            return [("au", self, "username")]

      __str__ = __repr__ = toString

class SIPHeaderProxyAuthorization (SIPHeaderAuthorization):
      sep = '-'

      def __init__ (self, key = 'proxyauthorization', value = None):
            super (SIPHeaderProxyAuthorization, self).__init__ (key, value)
