events_handler = {}

def register_events_handler (_event, mimetype, _class):
    global events_handler
    if events_handler.has_key (_event):
        print (
            "Event %s already registered"%_event)
        return False
    events_handler [_event] = {'mimetype': mimetype, 'class': _class}
    return True

# Busy Lamp Field RFC4235 support over (SIP)-Specific Event Notification RFC326
import blf_xml
blf_events_handler = {
    'event'     : 'dialog',
    'mime'      : 'application/dialog-info+xml',
    'class'     : blf_xml.BLF }

register_events_handler (blf_events_handler ['event'],
                          blf_events_handler ['mime'],
                          blf_events_handler ['class'])

def event_exist (_event):
    return events_handler.has_key (_event)

"""
SUBSCRIBE sip:1103@172.16.171.21;user=phone SIP/2.0
Event: dialog
Accept: application/dialog-info+xml
Expires: 3600
To: <sip:1103@172.16.171.21;user=phone>
"""
def _event_pkt_add (pkt, _event = None, mimetype = None):
    pkt.header_add ("Event", _event)
    pkt.header_add ("Accept", mimetype)
    return True

def event_pkt_add (pkt, _event):
    if not events_handler.has_key (_event):
        return False
    _event_pkt_add (pkt, _event = _event,
                    mimetype = events_handler [_event]['mimetype'])
    return True

def event_pkt_read (pkt):
    event_class = None
    try:
        pkt.event.enable ()
        pkt.hdr ['Content-Type']
    except KeyError, e:
        return False
    else:
        if not events_handler.has_key (pkt.event):
            print ("Event not supported")
            return False
        for _event_h in events_handler:
            mimetype, _class = _event_h
            if pkt ['Content-Type'] == mimetype:
                event_class = _class
                break
        if not event_class:
            print ("Event found but Content-Type mismatch")
            return False
    eclass = event_class ()
    eclass.fromString (pkt.body)
    return eclass
