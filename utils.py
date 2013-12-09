import os
import sys
import logging
from logging.handlers import SysLogHandler
import tnetstring
import traceback
import redis

def _redis_connect (redis_host, redis_port = 6379):
    _redis = redis.Redis (redis_host, redis_port)
    try:
        _redis.ping ()
    except:
        del (_redis)
        return False
    return _redis

def _pidfile_check (_name = None):
    filename = "/var/run/%s.pid"%(_name or sys.argv [0])
    pid = None
    try:
        fd = open (filename, "r")
        pid = fd.read ()
        fd.close ()        
    except:
        return True
    try:
        os.stat ('/proc/%d/'%pid)
    except:
        print "'%s' exist but PID %d not running, removing"% (filename, pid)
        os.remove (filename)
        return True
    return False
    
# for pid file monitoring
def _pidfile_init (_name = None):
    filename = "/var/run/%s.pid"%(_name or sys.argv [0])
    try:
        fd = open (filename, "w")
        pid = os.getpid ()
        fd.write (str (pid))
        fd.close ()
    except Exception, e:
        #self._logger.error(
        print (
            "Could not create pid file '%s' : '%s"%(filename, str(e)))
        return False
    return filename
    
def _pidfile_close (filename):
    if not filename:
        #self._logger.warning(
        print (
            "Pid file is not defined")
        return False
    try:
        os.remove (filename)
    except Exception, e:
        #self._logger.error(
        print (
            "Could not remove pid file '%s' : '%s"%(filename,
                                                    str (e)))
        return False
    return True

def log_init (name, level = logging.DEBUG, log_local = "local3"):
    logger = logging.getLogger (name)
    if not logger:
        return
    _logger = logger
    _logger.setLevel (level)
    handler = SysLogHandler ("/dev/log", log_local)
    handler.setLevel (logging.DEBUG)
    format = '%(name)-0s: %(levelname)-8s %(message)s'
    handler.setFormatter (logging.Formatter (format))
    _logger.addHandler (handler)
    return _logger

def daemonize ():
    try:
        if os.fork (): sys.exit (0)
    except OSError, e:
        print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit (1)
    os.setsid ()
    try:
        if os.fork (): sys.exit(0)
    except OSError, e:
        print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit (1)
    print "Fork ok, my pid is %s"%os.getpid ()
    sys.stdin = open ('/dev/null', 'rw')
    sys.stdout = sys.stderr = open('/var/log/server.log', 'w+')

# return filename
def dump (_data, suffix = "error"):
    global log_directory
    dir = log_directory
    if dir is None:
        #self._logger.critical (
        print (
            'cannot dump : (%s)'%_data)
        return None
    # create directory
    try:
        os.makedirs (dir)
    except Exception, e:
        # directory might already exist
        pass
    day = time.strftime ("%d_%b_%Y", time.gmtime ())
    filename = "%s/%s-%s.%s.log"%(dir, str (sys.argv [0]), day, suffix)
    try:
        fd = open (filename, "a+")
        fd.write (tnetstring.dumps (_data + "\n", 'iso-8859-15'))
        fd.close ()
    except Exception, e:
        #self._logger.error (
        print (
            "Could not dump data into '%s' : '%s"%(filename,
                                                   str (e)))
        return None
    return (filename)
