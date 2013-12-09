class URITemplate (object):
    nameaddr_opening_bracket    = '<'
    nameaddr_closing_bracket    = '>'
    authority_userinfo_separator= '@'
    authority_hostport_separator= ':'
    uri_bracket                 = ["<", ">"]
    hier_path_absolute          = '/'
    hier_path_abempty           = "//"
    path_separator              = '/'
    query_indicator             = ';'
    query_separator             = ';'
    query_assertion             = '='
    scheme_separator            = ':'
    scheme_indicator            = ["//", "/"]

class SIPTemplate (object):
    version_separator           = '/'
    version_id                  = "SIP"
    version_revision            = "2.0"
    version_proto               = "UDP"
    version_proto_list          = frozenset (("UDP", "TCP"))
    ruri_method_separator       = ' '
    ruri_code_separator         = ' '
    ruri_version_separator      = ' '
    header_prefix_value         = ' '
    header_value_separator      = ':'
    packet_body_separator       = "\r\n\r\n"
    packet_line_ending          = "\r\n"

class MetaTemplate (type):
      def __new__ (cls, name, bases, dct):
          inst = type.__new__ (cls, name, bases, dct)
          # inst is type 'type', thus adding template elements on the metaclass
          if getattr (inst, '__initialized__', None):
              return inst
          uri = name [:3] == "URI"
          if (uri or "SIP" == name [:3]) and len (name) > 3:
              name = name [3:]
              for i, c in enumerate (name):
                  if i and c.isupper ():
                      name = name [:i]
                      break
          name = name.lower ()
          name_len = len (name)
          _vars = vars (SIPTemplate) if not uri else vars (URITemplate)
          for i in _vars:
              if len (i) > (name_len + 2) and i[:name_len] == name:
                  setattr (inst, i[name_len + 1:], _vars [i])
                  setattr (inst, '__initialized__', True)
          return inst

if "__main__" == __name__:
    class SIPRuri (object):
        __metaclass__ = MetaTemplate
        def __init__ (self, a):
            print a
            return
    c = SIPRuri ("ok")
    print vars (SIPRuri)
