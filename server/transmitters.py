import os
import sys
import copy
import time
import signal
import random
import logging
import socket
import select
import threading
import tnetstring

main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
from utils import _redis_connect, log_init, dump
from command import *
from RedisHelper import RedisServer
from Config import Config
from sipcore import SIPpacket

config_path = main_path + "/../config"
SIPUDP, SIPTCP, RTP = range (0,3)
sock_info = {} # {s_id: {'id': (ip, port), 'sock': sock, 'type': RTP, SIP*}}
# optimizations :
sock_info_id = {} # {sock: s_id}
sock_list = [] # [sock1, sock2, ..., sockN]
# sock lock
sock_lock = threading.Lock ()
sock_lock_id = threading.Lock ()
sock_active = threading.Event ()
# threads lock
threads_command = threading.Lock ()
threads_transmitter = threading.Lock ()
# tcp sockets
tcp_sockets = {}
tcp_sockets_addr = {}
tcp_socket_queue = 10

# Server instance
class TransmitterCommand (object):

    def __init__ (self, _redis, _logger, _config):
        self._redis = _redis
        self._logger = _logger
        self._config = _config
        self.cmd_handler = {
            "CREATE_RTP_SOCK" : self.create_rtp, # [|port, |bind_ip]
            "CREATE_SIPUDP_SOCK" : self.create_sipudp, # bind_port, |bind_ip
            "CREATE_SIPTCP_SOCK" : self.create_siptcp, # bind_port, |bind_ip
            "REMOVE_RTP_SOCK" : self.remove_rtp, # port, |bind_ip
            "REMOVE_SIP_SOCK" : self.remove_sip  # bind_ip, bind_port
            }
        return

    def execute (self, cmd, ckey, args):
        if not self.cmd_handler.has_key (cmd):
            raise ServerUnknownCommand ("Command not found: %s"%cmd)
        self._logger.debug (
            "Executing '%s':%s"%(cmd, args))
        return self.cmd_handler [cmd] (ckey, *args)

    def create_rtp (self, ckey, s_id, ip = None, port = None):
        try:
            port = int (port)
        except ValueError:
            msg = '_create_rtp : invalid port \'%s\''%port
            self._logger.error (msg)
            RedisServer.server_error_reply (self._redis, ckey, msg)
            return False
        try:
            ip = str (ip)
        except UnicodeError:
            msg = '_create_rtp : invalid host \'%s\''%ip
            self._logger.error (msg)
            RedisServer.server_error_reply (self._redis, ckey, msg)
            return False
        if not self._create_socket (s_id, ip, port, RTP):
            RedisServer.server_error_reply (self._redis, ckey,
                                            "Can't bind RTP: %s:%d"%(ip, port))
            return False
        RedisServer.server_rtp_create_reply (self._redis, ckey, s_id)
        return s_id, False

    def create_sipudp (self, ckey, s_id, ip = None, port = None):
        return self.create_sip (ckey, s_id, ip, port, SIPUDP)

    def create_siptcp (self, ckey, s_id, ip = None, port = None):
        return self.create_sip (ckey, s_id, ip, port, SIPTCP)

    def create_sip (self, ckey, s_id, ip = None, port = None, transport = None):
        try:
            port = int (port)
        except ValueError:
            msg = '_create_rtp : invalid port \'%s\''%port
            self._logger.error (msg)
            RedisServer.server_error_reply (self._redis, ckey, msg)
            return False
        try:
            ip = str (ip)
        except UnicodeError:
            msg = '_create_sip : invalid host \'%s\''%ip
            self._logger.error (msg)
            RedisServer.server_error_reply (self._redis, ckey, msg)
            return False
        if not self._create_socket (s_id, ip, port, transport):
            RedisServer.server_error_reply (self._redis, ckey,
                                            "Can't bind SIP: %s:%d"%(ip, port))
            return False
        transport = "UDP" if SIPUDP == transport else "TCP"
        RedisServer.server_sip_create_reply (self._redis, ckey, s_id, transport)
        return s_id, False

    def remove_rtp (self, *args):
        raise NotImplemented
    def remove_sip (self, *args):
        raise NotImplemented

    def _create_socket (self, s_id, ip, port, _type):
        global sock_list, sock_info, sock_info_id, sock_lock, sock_lock_id
        ip = ip or self.sock_ip
        sock_type = socket.SOCK_STREAM if _type is SIPTCP else socket.SOCK_DGRAM
        sock = socket.socket (socket.AF_INET, sock_type)
        sock.setsockopt (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind ((ip, port))
        except socket.error:
            self._logger.error (
                "Cannot bind on port %s:%d"%(ip, port))
            return False
        # else:
        #     FIXME : TCP server 
        #     if _type == SIPTCP:
        #         sock.listen (tcp_socket_queue)
        self._logger.info (
            "Creating socket %s:%d"%(ip, port))
        sockid = "%s:%s"% (ip, str (port))
        sock_lock.acquire ()
        sock_info [s_id] = {'id': sockid, 'sock': sock, 'type': _type}
        sock_lock_id.acquire ()
        sock_info_id [sock] = s_id
        sock_lock_id.release ()
        if _type is not SIPTCP:
            sock_list += [sock]
        sock_lock.release ()
        if _type is not SIPTCP:
            sock_active.set ()
        return True

    def _del_socket (self, _id):
        global sock_list, sock_info, sock_info_id, sock_lock, sock_lock_id
        try:
            sock_lock.acquire ()
            _type = self_info [_id]['type']
            sock_list.remove (self_info [_id]['sock'])
            sock_lock_id.acquire ()
            sock_info_id.pop (self_info [_id]['sock'])
            sock_lock_id.release ()
            sock_info.pop (_id)
            if SIPTCP is _type:
                for k in tcp_sockets:
                    if tcp_sockets [k][s_id] == self._id:
                        tcp_sockets.pop (k)
            if not sock_list and not tcp_sockets:
                sock_active.clear ()
            sock_lock.release ()
        except KeyError: # dict
            self._logger.critical (
                "Cannot pop %s in sock_info"%_id)
        except ValueError: # list
            self._logger.critical (
                "Cannot remove %s in sock_list"%_id)
        else:
            return True
        finally:
            sock_lock.release ()
        return False

# Command, Sending packets
class Transmitter (CommandHandler, threading.Thread):
    def __init__ (self, * args, ** kwargs):
        super (Transmitter, self).__init__ (** kwargs)
        threading.Thread.__init__ (self)
        self._command_handler = TransmitterCommand (self._redis, self._logger,
                                                    self._config)
        threads_command.acquire ()
        return

    def _shutdown (self):
        self._logger.info (
            "Transmitter (command) shutdown")
        threads_command.release ()

    def _validate (self):
        if not super (Transmitter, self)._validate ():
            return False
        if 'server_' == self._table [:7]: # command
            # CMD [CMD_ARGS]
            if 3 is not len (self._data):
                self._logger.critical (
                    "len('%s') is not 3"%self._data)
                return False
            return True if list == type (self._data) else False
        elif 'send_' == self._table [:5]: # sip, rtp packets
            # [host, port, pkt]
            try:
                int (self._data [1])
            except ValueError:
                self._logger.critical (
                    "Invalid port : %s"%self._data [1])
                return False
            except TypeError:
                self._logger.critical (
                    "Internal Error %s"%str (self._data))
                return False
            return True if list is type (self._data) and \
                3 is len (self._data) else False
        return False

    def _parse (self):
        if 'server_' == self._table [:7]: # command
            self.command        = True
            r = self._data
            self.cmd        = r [0]
            self.cmd_args   = r [1]
            self.ckey       = r [2]
            return True
        elif 'send_' == self._table [:5]: # sip, rtp packets
            self.command        = False
            self.host           = self._data [0]
            self.port           = int (self._data [1])
            self.pkt            = self._data [2].encode ('iso-8859-15')
            self._id            = int (self._table [5:])
            return True
        return False

    _locals_enter = _locals_close = lambda self: True

    def _process (self):
        global sock_list, sock_info, sock_info_id, sock_lock, sock_lock_id
        if self.command:
            try:
                self._logger.info (
                    "executing %s (%s)"%(self.cmd, self.cmd_args))
                _r = self._command_handler.execute (self.cmd, self.ckey,
                                                    self.cmd_args)
                if _r and 2 == len (_r):
                    s_id, _del = _r
                    if _del:
                        try:
                            self._redis_list.remove ("send_%d"%s_id)
                        except KeyError:
                            self._logger.critical (
                                "Cannot remove from _redis_list: %s"%s_id)
                    else:
                        self._redis_list += ["send_%d"%s_id]
            except ServerUnknownCommand:
                self._logger.critical (
                    "Unknown command : %s ('%s')"%(self.cmd, self._data))
            except Exception, e:
                self._logger.exception (e)
            else:
                return True
        else:
            self._logger.debug (
                "retrieving packet")
            if not sock_info.has_key (self._id):
                self._logger.critical (
                    "%s doesn't match existing"%self._id)
                return False
            sock_lock.acquire ()
            _type = sock_info [self._id]['type']
            sock = sock_info [self._id]['sock']
            sock_lock.release ()
            self._logger.debug (
                "retrieving packet #2")
            if _type is SIPTCP:
                try:
                    sock = tcp_sockets_addr [((self.host, self.port), self._id)]
                except KeyError:
                    sock.connect ((self.host, self.port))
                    tcp_sockets_addr [((self.host, self.port), self._id)] = sock
                    tcp_sockets [sock] = {'s_id': self._id,
                                          'address': (self.host, self.port)}
                    sock_active.set ()
            sock.sendto (self.pkt, (self.host, self.port))
            # transmit packet
            return True
        return False

class TransmitterData (threading.Thread):
    def __init__ (self, _logger, _redis, _config):
        threading.Thread.__init__(self)
        self._logger = _logger
        self._redis = _redis
        self._config = _config
        self._runnable = True
        self._recv_mtu = 4096
        self._select_timeout = 2
        threads_transmitter.acquire ()

    def run (self):
        sock_data = self.recv_network () # generator
        for _r in sock_data:
            try:
                date, data, addr, s_id, _type = _r
                self._logger.debug (str(_r))
                handler = self._handle_sip if _type is not RTP else \
                    self._handle_rtp
                redis_raw = handler (date, data, addr, s_id)
                if not redis_raw:
                    self._logger.error (
                        "Cannot handle packet '%s' from %s"%(data, addr))
                    continue
                self._redis.lpush (*redis_raw)
            except Exception, e:
                self._logger.exception (e)
                self._logger.error (
                    "Unable to process data '%s'"%str (_r))
                continue
        self._logger.info (
            "Transmitter (data) shutdown")
        threads_transmitter.release ()
        return True

    def _handle_rtp (self, date, data, addr, s_id):
        return ("recv_%.02d"%s_id, tnetstring.dumps ([date, list (addr), data],
                                                     'iso-8859-15'))

    def _handle_sip (self, date, data, addr, s_id):
        try:
            sip_pkt = SIPpacket ()
            sip_pkt.fromString (data)
            self._logger.debug (
                "%s: received SIP message (%d bytes)"% (addr, len (data)))
            redis_data = tnetstring.dumps ([s_id, date, list (addr), data],
                                           'iso-8859-15')
            valid = True
            try:
                # This is the SIP parser routine
                # There is no totag and it is a request : push in 'method's list
                # or compute session_id : 'fromtag:callid:branch'
                # when method is BYE 'fromtag' from 'To' and branch from 'CSeq'
                sip_pkt.to.enable ()
                tp = sip_pkt.tp
                if not tp and None is not sip_pkt.rm:
                    return [sip_pkt.rm, redis_data]
                if "BYE" == sip_pkt.rm:
                    sip_pkt.to.enable ()
                    fp = sip_pkt.tp
                    branch = sip_pkt.cseq.seq
                else:
                    sip_pkt._from.enable ()
                    fp = sip_pkt.fp
                    sip_pkt.via.enable ()
                    branch = sip_pkt.vb
                callid = sip_pkt.callid
                sess_id = "%s:%s:%s"% (fp, callid, branch)
                return [sess_id, redis_data]
            except KeyError, h:
                self._logger.warn (
                    "Missing header '%s', droping packet"%str (h))
        except Exception, e:
            self._logger.exception (e)
            self._logger.error (
                "Unable to parse SIP request, dumping")
            self._dump (data, suffix = "error")
        return False

    def recv_network (self):
        global sock_list, sock_info, sock_info_id, sock_lock, sock_lock_id
        while self._runnable:
            # block until at least one sockets be opened
            sock_active.wait (float (self._select_timeout))
            if not sock_active.is_set ():
                continue
            sock_lock.acquire ()
            rlist = copy.copy (sock_list)
            sock_lock.release ()
            if tcp_sockets:
                rlist += tcp_sockets.keys ()
                self._logger.debug ("Adding socket " + str (tcp_sockets))
            rlist, wlist, xlist = select.select (rlist, (), (),
                                                 self._select_timeout)
            if not rlist:
                continue
            for sck in rlist:
                self._logger.debug ("Found " + str (sck))
                is_tcp = sck in tcp_sockets.keys ()
                if not is_tcp:
                    sock_lock_id.acquire ()
                    s_id = sock_info_id [sck]
                    sock_lock_id.release ()
                    sock_lock.acquire ()
                    try:
                        _type = sock_info [s_id]['type']
                    except KeyError:
                        self._logger.warn (
                            "race condition when socket found readable, closed")
                        continue
                    sock_lock.release ()
                    # FIXME : TCP server mode
                    # if _type is SIPTCP:
                    #     sck, address = sck.accept ()
                    #     tcp_sockets [sck] = {'s_id': s_id, 'address': address}
                    #     tcp_sockets_addr [(address, s_id)] = sck
                else:
                    _type = SIPTCP
                    s_id = tcp_sockets [sck]['s_id']
                data, addr = sck.recvfrom (self._recv_mtu)
                if not addr:
                    addr = tcp_sockets [sck]['address']
                if _type is SIPTCP and not len (data):
                    tcp_sockets.pop (sck)
                    tcp_sockets_addr.pop (address)
                    sck.close ()
                    del (sck)
                    if not sock_list and not tcp_sockets:
                        sock_active.clear ()
                    continue
                date = time.time ()
                yield date, data, addr, s_id, _type

    _dump = dump

def _shutdown (signo = None, frame = None):
    global threads_sem
    for _t in threading.enumerate ():
        _t._runnable = 0
    threads_command.acquire ()
    threads_transmitter.acquire ()
    sys.exit (0)

if '__main__' == __name__:
    instance_cnt = 1
    if sys.argv [1:]:
        instance_cnt = sys.argv [1]
    try:
        instance_cnt = int (instance_cnt)
    except ValueError:
        print >> sys.stderr, "Invalid instance count number : %s"%instance_cnt
        sys.exit (0)
    config_file = "%s/config_transmitters_%.02d.py"%(config_path, instance_cnt)
    config = Config (config_file)
    logger = log_init (__file__, config.log_level or logging.DEBUG,
                       config.log_local or "local3")
    redis = _redis_connect (config.redis_host)
    logger.info (
        "Starting transmitter command")
    c = Transmitter (logger = logger, redis = redis, config = config)
    logger.info (
        "Starting transmitter receiver/sender")
    rs = TransmitterData (logger, redis, config)
    c.start ()
    rs.start ()
    logger.info (
        "started")
    signal.signal (signal.SIGTERM, _shutdown)
    try:
        signal.pause ()
    except KeyboardInterrupt:
        logger.info (
            "Hit ^C Exiting")
    _shutdown ()
