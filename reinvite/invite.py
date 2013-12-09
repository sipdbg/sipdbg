import sys, os
import time
import logging
import tnetstring
import redis
main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
from sipcore import *
from uri import *
from rand import *
from sdp import SDP
from Config import Config
from utils import _redis_connect, log_init
from client import ClientRedis
from dialog import dialog_handler

caller = "0033172756108"
callee = "0033172756108"
sid = None
_redis = None

def usage ():
    print "Usage : %s [callee] |[caller]"%sys.argv [0]
    sys.exit (0)

if "--help" in sys.argv [1:] or "-h" in sys.argv [1:]:
    usage ()

if sys.argv [1:]:
    callee = sys.argv [1]
    caller = sys.argv [2] if sys.argv [2:] else caller

config_path = main_path + "/../config"
config_file = "%s/config_invite.py"%config_path
# configuration
config = Config (config_file)
# logger
logger = log_init (__file__, config.log_level or logging.DEBUG,
                   config.log_local or "local3")
# redis
_redis = _redis_connect (config.redis_host)
if not _redis:
    print >> sys.stderr, "Cannot connect to Redis"
    sys.exit (0)

client = ClientRedis (_redis, debug = config.debug)

pkt = SIPpacket ()
# R-URI
ruri = URI ()
ruri.userinfo = callee
ruri.host = config.proxy
pkt.request.uri = ruri
pkt.request.method = "INVITE"

# Via
v = URI ()
v.host = config.local_host
vb = branch_new ()
v.query.params ['branch'] = vb
v.noscheme ()
pkt._h_via = v

# From
from_uri = NAMEADDR ()
from_uri.uri = URI ()
from_uri.uri.userinfo = config.fromuser or caller
from_uri.uri.host = config.proxy
fp = fromtag_new ()
from_uri.uri.query.params ['tag'] = fp
from_uri.uri.set_bracket (URI.bracket_pre_query)
from_uri.display_name = config.display_name
pkt._h_from = from_uri

# To
to_uri          = NAMEADDR ()
to_uri.uri      = URI ()
to_uri.uri.host = config.proxy
to_uri.uri.userinfo = callee
# to_uri.query.params ['tag'] = fromtag_new () # XXX : totag
pkt.to = to_uri

# Contacts
c = NAMEADDR ()
c.uri = URI ()
c.uri.userinfo = caller
c.uri.host = config.local_host
c.uri.port = config.local_port
c.uri.set_bracket (URI.bracket_pre_query)
contact = c
pkt._h_contact = c

# Call-Id
callid = callid_new (config.local_host)
pkt._h_callid = callid
# CSeq
pkt.cseq = "1 INVITE"
# Max-Forwards
pkt.maxforwards = 70
# User-Agent
pkt.useragent = config.useragent
# Content-Type
pkt._h_contenttype = "application/sdp"

#pkt.body.mime = "application/sdp" # XXX
sdp_data = """v=0\r
o=- 3572589446 3572589446 IN IP4 172.16.253.11\r
s=pjmedia\r
c=IN IP4 172.16.253.11\r
t=0 0\r
a=X-nat:0\r
m=audio 40004 RTP/AVP 103 102 104 117 3 0 8 101\r
a=rtcp:40001 IN IP4 172.16.253.11\r
a=rtpmap:103 speex/16000\r
a=rtpmap:102 speex/8000\r
a=rtpmap:104 speex/32000\r
a=rtpmap:117 iLBC/8000\r
a=fmtp:117 mode=20\r
a=rtpmap:3 GSM/8000\r
a=rtpmap:0 PCMU/8000\r
a=rtpmap:8 PCMA/8000\r
a=sendrecv\r
a=rtpmap:101 telephone-event/8000\r
a=fmtp:101 0-15\r
"""
data = sdp_data
pkt.contentlength = len (data)
pkt.body.data = data

session_id = dict ([('fromtag', fp), ('callid', callid), ('branch', (vb)),
                     ('contact', contact), ('ruri', ruri)])
session_id ['data'] = {}
session_id ['data']['method'] = 'REGISTER'
session_id ['pkt'] = {}
session_id ['pkt']['inbound'] = {}
session_id ['pkt']['outbound'] = {}
session_id ['sending_queue'] = []

session_id ['server_host'] = config.proxy
session_id ['server_port'] = config.port
# redis
# _redis = _redis_connect (config.redis_host)
# if not _redis:
#     print >> sys.stderr, "Cannot connect to Redis"
#     sys.exit (0)

# client = ClientRedis (_redis, debug = config.debug)
ret = client.socket_sip (ip = config.local_host, port = config.local_port) #, proto = "TCP")
v = client.server_reply (* ret)
if not v:
    print "no server reply"
    sys.exit (1)
session_id ['server_id'] = v [0]
print v[0]

ret = client.socket_rtp (ip = config.local_host, port = 40004)
v = client.server_reply (* ret)
if not v:
    print "no server reply"
    sys.exit (1)
session_id ['server_id_rtp'] = v [0]
print "server_id_rtp : %d, server_id_sip : %d"%(session_id ['server_id_rtp'],
                                                session_id ['server_id'])

client.pkt_send (session_id ['server_id'], str (pkt),
                 session_id ['server_host'],
                 session_id ['server_port'])
session_id ['pkt']['outbound']['last_packet'] = (time.time (), pkt)
session_id ['authenticated'] = False

def pre_handler (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    session_id ['pkt']['inbound']['last_packet'] = (time.time (), pkt)

def stream_rtp (pkt = None):
    # SDP
    body = pkt.body
    sdp = SDP (str (body))
    rtp_address = sdp.conndata.address
    rtp_port = sdp.mediadata.port
    print "sending RTP _to_ %s:%d"%(str(rtp_address), int (rtp_port))
    sys.stdout.flush ()
    # RTP
    rtp_pkt = open ('../rtp/rtp.out.g711.py').read ()
    rtp_pkt = tnetstring.loads (rtp_pkt, 'iso-8859-15')
    try:
        for data_rtp in rtp_pkt:
            print type (data_rtp)
            client.pkt_send (session_id ['server_id_rtp'], data_rtp,
                             rtp_address, int (rtp_port))
            time.sleep (config.rtp_framing)
            print ".",
            sys.stdout.flush ()
    except KeyboardInterrupt:
        print "Stop sending RTP... waiting for BYE"
    session_id ['stream'] = False
    return

def stream_post_handler (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    for _pkt in session_id ['sending_queue']:
        client.pkt_send (session_id ['server_id'], str (_pkt),
                         session_id ['server_host'],
                         session_id ['server_port'])
        session_id ['pkt']['outbound']['last_packet'] = (time.time (), _pkt)
    session_id ['sending_queue'] = []
    if not session_id ['stream']:
        return
    #stream_rtp (pkt)
    return

def post_handler (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    for _pkt in session_id ['sending_queue']:
        client.pkt_send (session_id ['server_id'], str (_pkt),
                         session_id ['server_host'], session_id ['server_port'])
        session_id ['pkt']['outbound']['last_packet'] = (time.time (), _pkt)
    session_id ['sending_queue'] = []

def send_ack (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    pkt = session_id ['pkt']['inbound']['last_packet'][1]
    ack = SIPpacket ()
    ack.request.uri = session_id ['ruri']
    ack.request.method = "ACK"
    ack.via = str (pkt.via)
    ack._from = pkt._from
    ack.to = pkt.to
    ack.to.tag = pkt.tp
    #ack.contact = session_id ['contact']
    ack.callid = pkt.callid
    # Record-Route -> Route
    if pkt.header_exist ('Record-Route'):
        ack._h_route = pkt.recordroute
    ack.cseq = pkt.cseq
    session_id ['pkt']['seq'] = pkt.cseq.seq
    ack.cseq.method = "ACK"
    ack.maxforwards = 70
    ack.useragent = config.useragent
    ack.contentlength = 0
    session_id ['sending_queue'] += [str (ack)]
    return False

def send_200 (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    pkt = session_id ['pkt']['inbound']['last_packet'][1]
    _200 = SIPpacket ()
    _200.request.code = 200
    _200.request.reason = "Ok"
    _200.via = str (pkt.via)
    _200._from = pkt._from
    _200.to = pkt.to
    _200.to.tag = pkt.tp
    #_200.contact = session_id ['contact']
    _200.callid = pkt.callid
    # Record-Route -> Route
    if pkt.header_exist ('Record-Route'):
        _200._h_route = pkt.recordroute
    _200.cseq = pkt.cseq
    _200.cseq.method = pkt.rm
    _200.maxforwards = 70
    _200.useragent = config.useragent
    _200.contentlength = 0
    session_id ['sending_queue'] += [str (_200)]
    return False

def do_authenticate (client, session_id, data):
    print "authenticating"
    s_id, timestamp, addr, pkt = data
    code = pkt.rs
    send_ack (client, session_id, data)
    session_id ['totag'] = pkt.tp
    lpkt                = session_id ['pkt']['outbound']['last_packet'][1]
    lpkt.cseq.seq       += 1
    realm               = None
    nonce               = None
    _h_authentify       = None
    if 401 == code:
        if pkt.header_exist ("WWW-Authenticate"):
            pkt.wwwauthenticate.enable ()
            realm, nonce = pkt.wwwauthenticate.realm, pkt.wwwauthenticate.nonce
            # build header
            _h_authentify = SIPHeaderAuthorization ()
        else:
            print "401 miss WWW-Authenticate"
            return False
    elif code == 407:
        if pkt.header_exist ("Proxy-Authenticate"):
            pkt.proxyauthenticate.enable ()
            realm, nonce = pkt.proxyauthenticate.realm, \
                pkt.proxyauthenticate.nonce
            _h_authentify = SIPHeaderProxyAuthorization ()
        else:
            print "407 miss Proxy-Authenticate"
            return False
    _h_authentify.realm = realm
    _h_authentify.nonce = nonce
    lpkt.enable ()
    _h_authentify.method = lpkt.rm
    _h_authentify.uri = str (ruri)
    _h_authentify.username = config.fromuser or caller
    _h_authentify.password = config.password
    lpkt.header_del ("Content-Length")
    lpkt._header_add (_h_authentify)
    print str (lpkt)
    session_id ['sending_queue'] += [str (lpkt)]
    return True

def handle_200 (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    send_ack (client, session_id, data)
    print "CALL ESTABLISHED"
    pkt.to.enable ()
    totag = pkt.tp
    session_id ['totag'] = totag
    session_id ['stream'] = True
    session_id ['stream'] = False
    _sid  = "%s:%s:%s"%(session_id ['fromtag'], session_id ['callid'],
                        session_id ['pkt']['seq'] + 1)
    print "waiting on %s"%_sid
    return [dialog_call_established, 3600, False, _sid]

def handle_trying (client, session_id, data):
    print "Got 100 Trying..."
    print session_id ['sending_queue']
    session_id ['sending_queue'] = []
    return [dialog_invite, 3600, False] # FIXME

def handle_ringing (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    print "ringing %d"%pkt.rs
    return True

def handle_reinvite (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    print "REINVITE !!!"
    return True

def handle_bye (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    print "Call terminated, sending 200OK"
    send_200 (client, session_id, data)
    return True

def failure_call (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    send_ack (client, session_id, data)
    print "CALL FAILURE : %s"%pkt.rr

dialog_invite = {
    'pre_handler'       : pre_handler,
    'post_handler'      : post_handler,
    '100'               : handle_trying,
    '18x'               : handle_ringing,
    '200'               : handle_200,
    '401 | 407'         : do_authenticate,
    '4xx'               : failure_call
    }

dialog_call_established = {
    'pre_handler'       : pre_handler,
    'post_handler'      : stream_post_handler,
    'INVITE'            : handle_reinvite,
    'BYE'               : handle_bye # send 200 OK
}

dialog_handler (client, session_id, dialog_invite, reemission = True)
