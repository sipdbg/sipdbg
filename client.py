import os
import sys
import time
import redis
import tnetstring
main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
from rand import tag_new
from sipcore import SIPpacket

class ClientRedis (object):
    def __init__ (self, _redis, timeout = None, debug = False):
        self._redis = _redis
        self._timeout = timeout or 10
        self._debug = debug
        self._last_packet = {}
        return

    def set_debug (self, _debug = True):
        self._debug = _debug

    def _server_command (self, cmd, cmd_args, u):
        self._redis.lpush ('server', tnetstring.dumps ([cmd, cmd_args, u],
                                                       'iso-8859-15'))
        return True

    def socket_sip (self, port = 5060, ip = None, proto = 'UDP'):
        if proto not in ['UDP', 'TCP']:
            return None
        u = tag_new ()
        cmd = 'CREATE_SIP%s'%proto
        cmd_args = [port, ip]
        self._server_command (cmd, cmd_args, u)
        return cmd, u

    def socket_rtp (self, port, ip = None):
        try:
            port = int (port)
        except ValueError:
            return None
        if port < 1 or port > 65535:
            return None
        u = tag_new ()
        cmd = 'CREATE_RTP'
        cmd_args = [port, ip]
        self._server_command (cmd, cmd_args, u)
        return cmd, u

    def _read_pkt (self, _list, timeout = None):
        c = self._redis.blpop ([_list], timeout or 5)
        if None is c:
            return None
        return tnetstring.loads (c [1], 'iso-8859-15')

    def get_server_reply (self, u):
        c = self._read_pkt ("client_%s"%u)
        return c

    def server_reply (self, cmd, u):
        c = self.get_server_reply (u)
        if not c:
            return None
        cmd_reply = '%s_REPLY'%cmd
        if cmd_reply != c [0]:
            return None
        return c [1]

    def pkt_send (self, _id, data, host, port, rtp = False):
        if not rtp:
            self._last_packet ['_id'] = _id
            self._last_packet ['data'] = data
            self._last_packet ['host'] = host
            self._last_packet ['port'] = port
        try:
            self._redis.lpush ('send_%s'%str (_id),
                               tnetstring.dumps ([host, port, data],
                                                 'iso-8859-15'))
            if self._debug:
                print "===> sending to %s:%d at %s"%(host, int (port),
                                                     time.ctime (time.time ()))
                print str (data)
        except:
            return True
        return False

    def pkt_read (self, info, timeout = None, _list = None):
        timeout = timeout or self._timeout
        # [s_id, date, data]
        if not _list:
            _list = str (info) if str is type (info) else \
                ':'.join (info [k] for k in ['fromtag', 'callid', 'branch'])
        return self._redis.blpop ([_list], timeout)

    def pkt_read_retry (self, info, maxtry = 10, timeout = 1, sid = None):
        for i in range (maxtry):
            pkt = self.pkt_read (info, timeout, sid)
            if pkt:
                return pkt
            if not self._last_packet:
                return None
            self.pkt_send (self._last_packet ['_id'],
                           self._last_packet ['data'],
                           self._last_packet ['host'],
                           self._last_packet ['port'])
        return None

    def pkt_parse (self, raw_pkt):
        _reply = SIPpacket ()
        _reply.fromString (raw_pkt)
        return _reply

    def pkt_read_parse (self, info, timeout = None, maxtry = 10,
                        reemission = False, sid = False):
        _reply = SIPpacket ()
        _r = self.pkt_read (info, timeout, sid) if not reemission else \
            self.pkt_read_retry (info, maxtry, sid)
        if not _r:
            return None
        _a = tnetstring.loads (_r [1], 'iso-8859-15')
        s_id, timestamp, addr, pkt = _a
        if self._debug:
            print "<=== received from %s at %s"%(addr, time.ctime (timestamp))
            print str (pkt) 
        pkt = self.pkt_parse (pkt)
        return (s_id, timestamp, addr, pkt)


if '__main__' == __name__:
    _r = redis.Redis ('127.0.0.1')
    c = ClientRedis (_r)
    # ret = c.socket_sip ()
    # print ret
    # v = c.server_reply (* ret)
    # print v
    # c.pkt_send (v[0], )
    # print c.pkt_read ('INVITE')
    print "sending RTP"
    ret = c.socket_rtp (port = 40000)
    v = c.server_reply (* ret)
    print v
    c.pkt_send (v [0], "xxxyyy", "127.0.0.1", 4244)
    print "sent"
    sys.exit (0)
