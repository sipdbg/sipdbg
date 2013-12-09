from xml.dom import minidom

class BLF (object):
    blf_urn = "urn:ietf:params:xml:ns:dialog-info"
    event   = "dialog"

    def __init__ (self):
        self.version    = None
        self.doc_state  = None
        self.entity     = None
        self.direction  = None
        self.state      = None

    def fromString (self, data):
        try:
            xmldoc              = minidom.parseString (data)
            dialoginfo          = xmldoc.getElementsByTagName ('dialog-info')
            if dialoginfo [0].attributes ['xmlns'].value != self.blf_urn:
                raise Exception ("URN is not %s"%self.blf_urn)
            self.version        = dialoginfo [0].attributes ['version'].value
            self.doc_state      = dialoginfo [0].attributes ['state'].value
            self.entity         = dialoginfo [0].attributes ['entity'].value
            dialoginfo          = xmldoc.getElementsByTagName ('dialog')
            self.callid         = dialoginfo [0].attributes ['id'].value
            self.direction      = dialoginfo [0].attributes ['direction'].value
            self.state          = xmldoc.getElementsByTagName (
                'state') [0].childNodes [0].nodeValue
        except:
            return False
        return True

    def toString (self):
        raise NotImplemented

if '__main__' == __name__:
    from os import stat
    import sys

    filename = sys.argv [1] if sys.argv [1:] else "doc.xml"
    stat (filename)

    document = open (filename).read ()
    blf = BLF ()
    blf.fromString (document)
    print blf.entity, blf.callid, blf.state
