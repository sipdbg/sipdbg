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
from Config import Config
from utils import _redis_connect, log_init
from client import ClientRedis
from dialog import dialog_handler

config_path = main_path + "/../config"
config_file = "%s/config_register.py"%config_path
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

def pre_handler (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    session_id ['pkt']['inbound']['last_packet'] = (time.time (), pkt)

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
    ack.contact = session_id ['contact']
    ack.callid = pkt.callid
    # Route -> Record-Route
    ack.cseq = pkt.cseq
    ack.cseq.method = "ACK"
    ack.maxforwards = 70
    ack.useragent = config.useragent
    ack.contentlength = 0
    session_id ['sending_queue'] += [str (ack)]
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
    _h_authentify.method = "REGISTER"
    _h_authentify.uri = str (ruri)
    _h_authentify.username = config.fromuser or caller
    _h_authentify.password = config.password
    lpkt._header_add (_h_authentify)
    session_id ['sending_queue'] += [str (lpkt)]
    return True

def handle_200 (client, session_id, data):
    s_id, timestamp, addr, pkt = data
    session_id ['authenticated'] = True
    return False

pkt = SIPpacket ()
# R-URI
ruri = URI ()
ruri.host = config.proxy
pkt.request.uri = ruri
pkt.request.method = "REGISTER"
# Via
v = URI ()
v.host = config.local_host
v.port = config.local_port
vb = branch_new ()
v.query.params ['rport'] = None
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
to_uri = NAMEADDR ()
to_uri.uri = URI ()
to_uri.uri.host = config.proxy
to_uri.uri.userinfo = config.fromuser or caller
#to_uri.bracket = True
# XXX : totag
#to_uri.query.params ['tag'] = fromtag_new ()
to_uri.display_name = config.display_name
to_uri.uri.set_bracket (URI.bracket_pre_query)
pkt.to = to_uri
# Contacts
c = NAMEADDR ()
c.uri = URI ()
c.uri.userinfo = config.fromuser or caller
c.uri.host = config.local_host
c.uri.port = config.local_port
c.uri.query.params ['expires'] = 3600
c.uri.set_bracket (URI.bracket_pre_query)
contact = str (c)
pkt._h_contact = contact
# Call-Id
callid = callid_new (config.local_host)
pkt._h_callid = callid
# CSeq
pkt.cseq = "930 REGISTER"
# Max-Forwards
pkt.maxforwards = 70
# User-Agent
pkt.useragent = config.useragent
# Allow
pkt._h_allow = "INVITE,ACK,BYE,CANCEL,OPTIONS,PRACK,REFER,NOTIFY,SUBSCRIBE,INFO,MESSAGE"

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
ret = client.socket_sip (port = 5063)#, proto = "TCP")
v = client.server_reply (* ret)
if not v:
    print "no server reply"
    sys.exit (1)
session_id ['server_id'] = v [0]
client.pkt_send (session_id ['server_id'], str (pkt),
                 session_id ['server_host'],
                 session_id ['server_port'])
session_id ['pkt']['outbound']['last_packet'] = (time.time (), pkt)
session_id ['authenticated'] = False

dialog_register = {
    'pre_handler'       : pre_handler,
    'post_handler'      : post_handler,
    '200'               : handle_200,
    '401 | 407'         : do_authenticate,
    '4xx'               : send_ack
    }

dialog_handler (client, session_id, dialog_register, reemission = True)
if session_id ['authenticated']:
    print "Authentication succeed"
