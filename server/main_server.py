import os
import sys
import random
import logging
import signal

main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
from utils import _redis_connect, log_init
from command import *
from RedisHelper import RedisServer
from Config import Config
from sipcore import SIPpacket

config_path = main_path + "/../config"

# Main Server
class MainServerCommand (object):

    def __init__ (self, _redis, _logger, _config):
        self.s_id       = 0   # Identifier for RTP/SIP service
        self.rr         = 1   # round robin (server id)
        self.instance_cnt = 1 # server count
        self.rtp        = {}  # rtp instance
        self.sip        = {}  # sip instance
        self._redis = _redis
        self._logger = _logger
        self._config = _config
        self.load_config ()
        self.cmd_handler = {
            "CREATE_RTP" : self.create_rtp, # ckey, [|port, |bind_ip]
            "CREATE_SIPTCP" : self.create_siptcp, # ckey, bind_port, |bind_ip
            "CREATE_SIPUDP" : self.create_sipudp, # ckey, bind_port, |bind_ip
            "REMOVE_RTP" : self.remove_rtp, # ckey, port, |bind_ip
            "REMOVE_SIP" : self.remove_sip  # ckey, bind_ip, bind_port
            }
        return

    def load_config (self):
        self._rtp_port_range_start = self._config.rtp_port_range_start
        self._rtp_port_range_end = self._config.rtp_port_range_end
        self._local_host = self._config.local_host
        return

    inc_rr = lambda self: 1 if self.rr == self.instance_cnt else self.rr + 1

    def execute (self, cmd, ckey, args):
        if not self.cmd_handler.has_key (cmd):
            raise ServerUnknownCommand ("Command not found: %s"%cmd)
        self._logger.debug ("Executing '%s':%s"%(cmd, args))
        return self.cmd_handler [cmd] (ckey, *args)

    def create_rtp (self, ckey, port = None, bind_ip = None):
        bind_ip = bind_ip or self._local_host
        if self.rtp.has_key ((bind_ip, port)):
            _id = self.rtp [(bind_ip, port)][0]
            return RedisServer.server_rtp_create_reply (self._redis, ckey, _id)
        while True if not port else False:
            port = random.randrange (self.rtp_port_range_start,
                                     self.rtp_port_range_end)
            if not self.rtp.has_key ((bind_ip, port)):
                break
        RedisServer.server_rtp_create (self._redis, ckey, self.s_id, port,
                                       bind_ip, self.rr)
        self.rtp [(bind_ip, port)] = (self.s_id, self.rr)
        self.s_id += 1
        self.rr = self.inc_rr ()
        return

    def create_sipudp (self, ckey, bind_port, bind_ip = None):
        return self.create_sip (ckey, bind_port, bind_ip, "UDP")

    def create_siptcp (self, ckey, bind_port, bind_ip = None):
        return self.create_sip (ckey, bind_port, bind_ip, "TCP")

    def create_sip (self, ckey, bind_port, bind_ip = None, proto = None):
        bind_ip = bind_ip or self._local_host
        if self.sip.has_key ((bind_ip, bind_port, proto)):
            _id = self.sip [(bind_ip, bind_port, proto)][0]
            self._logger.warn (
                "CreateSIP: %s:%d: Already exist"%(bind_ip, bind_port))
            return RedisServer.server_sip_create_reply (self._redis, ckey, _id,
                                                        proto)
        RedisServer.server_sip_create (self._redis, ckey, self.s_id,
                                       bind_ip, bind_port, self.rr, proto)
        self._logger.debug (
            "Contacting transmitter %d"%self.rr)
        self.sip [(bind_ip, bind_port, proto)] = (self.s_id, self.rr)
        self.s_id += 1
        self.rr = self.inc_rr ()
        self._logger.info (
            "Create SIP executed (%s:%d)"%(bind_ip, bind_port))
        return

    def remove_rtp (self, ckey, port, bind_ip = None):
        bind_ip = bind_ip or self._local_host
        if not self.rtp.has_key ((bind_ip, port)):
            RedisServer.server_error_reply (ckey, "RTP not existing")
            return
        RedisServer.server_rtp_remove (self._redis,
                                       ckey,
                                       self.rtp [(bind_ip, port)][1])
        self.rtp.pop ((bind_ip, bind_port))
        RedisServer.server_success_reply (self._redis, ckey)
        return

    def remove_sip (self, ckey, bind_ip, bind_port):
        if not self.sip.has_key ((bind_ip, port, proto)):
            RedisServer.server_error_reply (ckey, "SIP not existing")
            return
        RedisServer.server_sip_remove (self._redis, ckey,
                                       self.sip[(bind_ip, bind_port, proto)][1])
        self.sip.pop ((bind_ip, bind_port, proto))
        RedisServer.server_success_reply (self._redis, ckey)
        return

class Server (CommandHandler):
    def __init__ (self, * args, ** kwargs):
        super (Server, self).__init__ (** kwargs)
        self._command_handler = MainServerCommand (self._redis, self._logger,
                                                   self._config)
        return

    def _validate (self):
        if not super (Server, self)._validate ():
            return False
        return True if 3 is len (self._data) else False

    def _parse (self):
        r = self._data
        self.cmd        = r [0]
        self.cmd_args   = r [1]
        self.ckey       = r [2]
        return True

    _locals_enter = _locals_close = lambda self: True

    def _process (self):
        try:
            self._command_handler.execute (self.cmd, self.ckey, self.cmd_args)
        except ServerUnknownCommand:
            self._logger.error (
                "Unknown command : %s ('%s')"%(self.cmd, self._data))
        except Exception, e:
            self._logger.exception (e)
        else:
            return True
        return False

def _shutdown (signo = None, frame = None):
    sys.exit (0)

if '__main__' == __name__:
    config_file = "%s/config_server.py"%config_path
    config = Config (config_file)
    logger = log_init (__file__, config.log_level or logging.DEBUG,
                       config.log_local or "local3")
    redis = _redis_connect (config.redis_host)
    s = Server (logger = logger, redis = redis, config = config)
    signal.signal (signal.SIGTERM, _shutdown)
    logger.info ("Starting server")
    try:
        s.run ()
    except KeyboardInterrupt:
        logger.info (
            "Hit ^C Exiting")
    logger.info ("Stopping server")
    del (s)
    sys.exit (0)
