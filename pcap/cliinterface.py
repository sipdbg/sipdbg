import sys, os
main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
# Ordered dictionnary
from dictorder import odict

class CLIInterface (object):

    def __init__ (self, sip_comm, sip_data, rtp_flow):
        sip_modules_read_cli = odict ( [('rtp',         self.print_rtp),
                                        ('request',     self.print_request),
                                        ('credentials', self.print_credentials),
                                        ('body',        self.print_body) ] )

        print '\033[1;41m SIP CONNECTIONS \033[1;m'
        for uuid, cnt in sip_comm.iteritems ():
            print '\033[1;41m SIP uuid:\'%s\' (%d packets)\033[1;m'%(uuid, cnt)
            dialog, arr = sip_data [uuid]
            src, dst = None, None
            last_timestamp = None
            for timestamp, addr, pkt, legs_n in arr:
                pad = str ()
                if not src:
                    print "%s:%d\t\t%s:%d"%(addr [0], addr [1],
                                            addr [2], addr [3])
                    src, dst = (addr [0], addr [1]), (addr [2], addr [3])
                elif src != (addr [0], addr [1]):
                    pad = " " * len (src [0]) + \
                        " " * len (str (src [1]))+ " \t\t"
                info = pkt.get_data ()
                for _k, handler in sip_modules_read_cli.iteritems ():
                    s = handler (dialog, addr, pkt, legs_n, info, timestamp)
                    if s:
                        print "%s %s"%(pad, s)
                dialog ['last_timestamp'] = timestamp

        print '\033[1;41m RTP STREAMS \033[1;m'
        for _rtp, cnt in rtp_flow.iteritems ():
            print "RTP: %s: %d packets"%(_rtp, len (cnt))

    @staticmethod
    def print_credentials (dialog, addr, pkt, legs_n, info, timestamp):
        s = str ()
        if info ['credentials']:
            s += "with credentials"
        return s

    @staticmethod
    def print_body (dialog, addr, pkt, legs_n, info, timestamp): 
        s = str ()
        if info ['body']:
            mime, _len, data = info ['body']
            s += "%s (%d) : %s"%(mime, _len, data)
        return s

    @staticmethod
    def print_request (dialog, addr, pkt, legs_n, info, timestamp):
        s = str ()
        if info ['request'][0] == 'REQUEST':
            if 'INVITE' == info ['request'][1][0]:
                tt, _from = info ['request'][1][1]
                if _from:
                    pkt._from.enable ()
                s += "%sINVITE (%s)"%('RE' if tt else str (), pkt.fU)
            else:
                s += "%s: %s"%(info ['request'][1][0],
                               info ['request'][1][1] or str ())
        else:
            s += "(reply) %s: %s"%(info ['request'][1][0],
                                   info ['request'][1][1])
        return s

    @staticmethod
    def print_rtp (dialog, addr, pkt, legs_n, info, timestamp):
        s = str ()
        if not dialog.has_key ('traffic_rtp') or \
                not dialog.has_key ('last_timestamp'):
            return s
        cnt = 0
        l_timestamp = dialog ['last_timestamp']
        rtp_data = {}
        for addr, rtpdata, legs_n in dialog ['traffic_rtp']:
            for r_timestamp, u in rtpdata:
                r_timestamp = rtpdata [0]
                print l_timestamp, r_timestamp, timestamp
                break
                if r_timestamp > timestamp:
                    break
                if l_timestamp <= r_timestamp <= timestamp:
                    if rtp_data.has_key (addr):
                        rtp_data [addr] += 1
                    else:
                        rtp_data [addr] = 1
        for addr, cnt in rtp_data.iteritems ():
            s += "RTP: %s: %d packets"%(str (k), cnt)
        return s

def traffic_parse (dialog):
    if not dialog.has_key ('traffic_graph'):
        return None
    graph_ip = dialog ['traffic_graph']
    print "Link between"
    for src, dst in graph_ip.iteritems ():
        src = ':'.join (str (b) for b in src)
        interconnection = False
        if tuple == type (dst):
            dst = dst [0]
            interconnection = True
        dst = ':'.join (str (b) for b in src)
        link = "<-->" if interconnection else "-->"
        print "%s %s %s"% (src, link, dst)
        # Check if dst is connected with another and that another is connected
        # with src
    return True
