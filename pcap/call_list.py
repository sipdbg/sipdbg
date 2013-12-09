# -- coding: utf-8 --
import sys, os
import pcapy
import impacket.ImpactDecoder as Decoders
import impacket.ImpactPacket as Packets
import tnetstring
from ipaddr import IPv4Address
main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
from sipcore import *
from sdp import *
from uri import *

filename        = "mydata.pcap"
outfile         = "rtp.out.py"
bpffilter       = None
if sys.argv [1:]:
    filename = sys.argv [1]
    if sys.argv [2:]:
        bpffilter = sys.argv [2]
else:
    print "Usage: %s [pcap] |[bpf filter]"%sys.argv [0]
    sys.exit (0)

reader = pcapy.open_offline (filename)
if bpffilter:
    print "Using filter [%s]"%bpffilter
    reader.setfilter (bpffilter)
eth_decoder = Decoders.EthDecoder ()
ip_decoder = Decoders.IPDecoder ()
udp_decoder = Decoders.UDPDecoder ()

rtp_flow = {}
sip_comm = {}
sip_data = {}
pkt_list = []

packets = {}

i = 0
progressbar = "|/-\\"
pblen = len (progressbar)
while True:
    try:
        print "INFO: Processing packets... %s\r"%progressbar[i % pblen],
        sys.stdout.flush ()
        (header, payload) = reader.next ()
        if not header and not payload:
            break 
        datalink = reader.datalink ()
        if pcapy.DLT_EN10MB == datalink:
            eth_decoder = Decoders.EthDecoder ()
        elif pcapy.DLT_LINUX_SLL == datalink:
            eth_decoder = Decoders.LinuxSLLDecoder ()
        else:
            raise Exception ("Datalink type not supported: "%datalink)
        ethernet = eth_decoder.decode (payload)
        try:
            ip = ip_decoder.decode (payload[ethernet.get_header_size ():])
        except Packets.ImpactPacketException:
            continue
        if ip.get_ip_p () != Packets.UDP.protocol:
            continue
        sys.stdout.flush ()
        udp = udp_decoder.decode (
            payload[ethernet.get_header_size () + ip.get_header_size ():])
        # data
        udph_length = 8
        udp_data = payload [ ethernet.get_header_size () + 
                             ip.get_header_size () + udph_length:]
        timestamp = header.getts () [0]
        _k = (ip.get_ip_src (), udp.get_uh_sport (), ip.get_ip_dst (),
              udp.get_uh_dport ())
        packets [i] = (timestamp, _k, udp_data)
        i += 1
        continue
    except pcapy.PcapError:
        break
print "INFO: Processing packets : done \n"

if not packets:
    print "No packet match"
    sys.exit (1)

for i, v in packets.iteritems ():
    timestamp, _k, udp_data = v
    a = SIPpacket ()
    uuid = None
    try:
        a.fromString (udp_data, debug = True)
        uuid = str (a.uuid)
    except SipcoreException, e:
        if udp_data [0].isalpha (): # XXX
            print "false positive ?"
            print udp_data
        rtp = True
        if rtp_flow.has_key (_k):
            rtp_flow [_k] += [[timestamp, udp_data]]
        else:
            rtp_flow [_k] = [[timestamp, udp_data]]
        rtp = False
    else:
        if sip_comm.has_key (uuid):
            sip_comm [uuid] += 1
            sip_data [uuid] += [(timestamp, _k, a)]
        else:
            sip_comm [uuid] = 1
            sip_data [uuid] = [(timestamp, _k, a)]
        rtp = False
    continue

class BodyUnknown (Exception):
    pass

def parse_credentials (dialog, pkt, addr):
    return pkt.header_exist ('WWW-Challenge') or pkt.header_exist (
        'Proxy-Authorization')

def parse_request (dialog, pkt, addr):
    if None is pkt.rr:
        pkt.to.enable ()
        pkt._from.enable ()
        tp = pkt.tp
        method = str (pkt.rm)
        info = None
        if "ACK" == method:
            info = pkt.cseq.method
        elif "INVITE" == method:
            info = (tp, pkt._from)
        return 'REQUEST', (method, info)
    else:
        return 'REPLY', (pkt.rs, pkt.rr)

def parse_sdp (body):
    sdp = None
    try:
        sdp = SDP (str (body))
    except SDPParseError:
        return None
    # return codecs, framing, dtmf
    return sdp.conndata.address, sdp.mediadata.port

def parse_body (dialog, pkt, addr):
    body_modules_parse = {'application/sdp'     : parse_sdp,
                          'default'             : parse_sdp}
    body = pkt.body
    mime = pkt.header_get ('Content-Type')[0] if pkt.header_exist (
        'Content-Type') else None
    _len = 0

    if pkt.header_exist ('Content-Length'):
        try:
            _len = int (str (pkt.header_get ('Content-Length')[0]))
        except ValueError:
            print "WARNING : bad Content-Length received (not int) : %s"%(
                pkt.header_get ('Content-Length')[0])
        else:
           if _len != len (body):
               print "WARNING : Content-Length size differs with body: %d,%d"%(
                   _len, len (body))
    if not body:
        if mime:
            print "WARNING : Content-Type without body (%s)"%mime
        return False
    try:
        if mime and not body_modules_parse.has_key (mime):
            _mime = "default"
        else:
            _mime = mime
        if mime:
            data = body_modules_parse [_mime] (body)
    except Exception, e:
        print "WARNING : error parsing body of type '%s'"%mime
        data = None
    except BodyUnknown:
        data = None
    return (mime, len (body), data)

# parse_traffic : detect involved IPs and inter-relationals connections
def parse_session_traffic_graph (uuid):
    graph_ip = {}
    for i, _data in enumerate (sip_data [uuid][1]):
        timestamp, addr, pkt, legs_n = _data
        src_ip, src_port, dst_ip, dst_port = addr
        src = (src_ip, src_port)
        dst = (dst_ip, dst_port)
        if graph_ip.has_key (src):
            if tuple == type (graph_ip [src]):
                continue
            graph_ip [src] += [i, dst]
        else:
            graph_ip [src] = [i, dst]
        if graph_ip.has_key (dst):
            _i = graph_ip [src][0]
            graph_ip [src].remove (dst)
            graph_ip [src] += [(_i, dst, True)]
    # in case A, B and C and A has no link with C but B has with A,C we need
    # to set A/C value 1 or 3 and B value 2
    return graph_ip

# Check if there is multiple address involved (private and public)
# If yes, RTP detection checks are tolerabler (others usage eventually)
def session_nat_detection (uuid):
    return None
    # XXX : check for each legs if there is NAT
    nat_legs = {}
    for _data in sip_data [uuid][1]:
        timestamp, addr, pkt, legs_n = _data
        # Check 'Contact'
        ipcontact = IPv4Address (pkt.contact)
        if ipcontact.is_private:
            nat_legs [legs_n] = True
            continue
        # Check 'From'
        ipfrom = IPv4Address (pkt._from.host)
        if ipfrom.is_private:
            nat_legs [legs_n] = True
        # Check 'To'
        ipto = IPv4Address (pkt.to.host)
        if ipto.is_private:
            nat_legs [legs_n] = True 
       # check in SDP
        if pkt.body:
            sdp = parse_sdp (pkt.body)
            if sdp:
                ipsdp = IPv4Address (sdp [0])
                if ipsdp.is_private:
                    nat_legs [legs_n] = True
        nat_legs [legs_n] = False
    return nat_legs

# Rtp association module (detect with NAT IP from port and SDP changes)
# actually every stream is considered RTP plus they match if present within
# dialog
# sanity check : RTP arrives after an SDP
# XXX : Dump RTCP information
def parse_session_traffic_rtp (uuid):
    global rtp_flow
    if not rtp_flow:
        return False
    nonat = False # XXX
    rtp_streams = []
    rtp_match = []
    last = None
    for _data in sip_data [uuid][1]:
        timestamp, addr, pkt, legs_n = _data
        last = timestamp
        # if no SDP
        if not pkt.body:
            continue
        sdp = parse_sdp (pkt.body)
        if not sdp:
            # not sdp ?
            continue
        try:
            rtp_streams.index (sdp)
        except ValueError:
            rtp_streams += [(timestamp, legs_n, sdp)]
    if not rtp_streams:
        return None
    rtp_flow_keys = rtp_flow.keys ()
    for rtp in rtp_streams:
        timestamp, legs_n, sdp = rtp
        rtp_ip, rtp_port = sdp
        for rtp_host in rtp_flow_keys:
            try:
                rtp_match.index ((rtp_host, rtp_flow [rtp_host], legs_n))
            except ValueError:
                pass
            else:
                continue
            src_ip, src_port, dst_ip, dst_port = rtp_host
            if rtp_flow [rtp_host][0][0] < rtp [0] or \
                    rtp_flow [rtp_host][-1][0] > last and False:
                print "WARNING: RTP stream out of SIP dialog"
                continue
            if dst_port != rtp_port:
                continue
            elif dst_port == rtp_port:
                if dst_ip == rtp_ip:
                    # complete match
                    print "DEBUG: rtp complete match (leg %d)"%legs_n
                else:
                    if nonat:
                        continue
                    print "DEBUG: rtp IP differs (leg %d) s : %s"%(legs_n,
                                                                   dst_ip,
                                                                   rtp_ip)
            rtp_match += [(rtp_host, rtp_flow [rtp_host], legs_n)]
    return rtp_match or None

# in case A, B and C and A has no link with C but B has with A,C we need
# to set A/C value 1 or 3 and B value 2, actually it is incremental
def parse_legs (uuid):
    legs = {}
    i = 0
    # First pass -- attribute legs
    for _data in sip_data [uuid][1]:
        timestamp, addr, pkt = _data
        if not legs.has_key (addr):
            legs [addr] = i
            i += 1
    # Second pass -- assign them
    sip_data_new = []
    for _data in sip_data [uuid][1]:
        timestamp, addr, pkt = _data
        sip_data_new += [(timestamp, addr, pkt, legs [addr])]
    dialog = sip_data [uuid][0]
    sip_data [uuid] = (dialog, sip_data_new)
    return

sip_modules_parse = odict ( [('credentials',    parse_credentials),
                             ('body',           parse_body),
                             ('request',        parse_request) ] )

sip_session_parse = odict ( [('legs',           parse_legs),
                             ('nat',            session_nat_detection),
                             ('traffic_graph',  parse_session_traffic_graph),
                             ('traffic_rtp',    parse_session_traffic_rtp) ] )

for uuid, _data in sip_data.iteritems ():
    dialog = {}
    elem = []
    for timestamp, addr, pkt in _data:
        pkt_data = {}
        for _k, handler in sip_modules_parse.iteritems ():
            data = handler (dialog, pkt, addr)
            pkt_data [_k] = data
        pkt.set_data (pkt_data)
        elem += [[timestamp, addr, pkt]]
    sip_data [uuid] = (dialog, elem)
    for _k, handler in sip_session_parse.iteritems ():
        data = handler (uuid)
        if data:
            dialog [_k] = data

from cliinterface import CLIInterface
CLIInterface (sip_comm, sip_data, rtp_flow)

#from dumpinterface import DumpInterface
#DumpInterface (sip_comm, sip_data, rtp_flow)

