import os
import sys
import time
import tnetstring
import redis

from utils import _redis_connect


class ServerUnknownCommand (Exception):
    pass

class CommandHandler (object):

    def __init__ (self, logger, redis = None, config = None):
        self._redis = redis
        self._redis_list = None
        self._redis_timeout = 4
        self._redis_sleep_time = 10
        self._command_handler = None
        self._logger = logger
        self._config = config
        self._runnable = True # thread
        self.config_load ()

    def config_load (self):
        self._redis_host = self._config.redis_host
        _list = self._config.redis_list
        self._redis_list = [_list] if not list == type (_list) else _list
        if not self._redis:
            self._redis = _redis_connect (self._redis_host)
        if not self._redis:
            print >> sys.stderr, "Critical: cannot connect to redis"
            sys.exit (1)
        self._redis_timeout = 4
        self._redis_sleep_time = 10

    def run (self):
        while self._runnable:
            self._raw_data = self._data = self._table = None
            self._pop ()
            if not self._runnable:
                self._logger.info ("shutdown..")
                self._shutdown ()
                break
            if not self._validate ():
                self._logger.error ("_validate error")
                continue
            if not self._parse ():
                self._logger.error ("_parse error")
                continue
            self._locals_enter ()
            _r = self._process ()
            self._locals_close ()
            if not _r:
                self._logger.error ("_process error")
                continue
            continue

    def _pop (self, timeout = 4):
        timeout = self._redis_timeout or timeout
        _list = self._redis_list
        self._raw_data = None
        while self._runnable:
            self._check_redis ()
            _data = self._redis.blpop (_list, timeout)
            if _data:
                break
        self._raw_data = _data
        return True

    def _check_redis (self):
        try:
            self._redis.ping ()
            return True
        except redis.exceptions.ConnectionError:
            self._logger.error (
                "Redis server down, reconnecting..")
        while True:
            self._redis = _redis_connect (self._redis_host)
            if not self._redis:
                self._logger.warn (
                    "Cannot reconnect, waiting %ds"%self._redis_sleep_time)
                time.sleep (self._redis_sleep_time)
            else:
                self._logger.info (
                    "Redis re-connection OK")
                return True

    def _validate (self):
        if not self._raw_data or 2 is not len (self._raw_data):
            self._logger.error (
                "Invalid data from REDIS: '%s'"%self._raw_data)
            return False
        self._table, self._data = self._raw_data
        try:
            self._data = tnetstring.loads (self._data, 'iso-8859-15')
        except ValueError, e:
            self._logger.critical (
                "Invalid tnetstring data : '%s'"%self._data)
            return False
        return True

    def __notimplemented__ (self, *args, **kwargs):
        raise NotImplemented

    _parse = _locals_enter = _process = _locals_close = __notimplemented__
    _shutdown = lambda self: True
