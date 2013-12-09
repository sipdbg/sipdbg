import os, sys, atexit
import time
import argparse, textwrap
import logging
import traceback
import readline
from termcolor import colored
from logger import ColoredLogger
from dictorder import odict
from argparse_completion import parse_completion, CompletionArgumentParser
from utils import _redis_connect
from client import ClientRedis

class Profile (object):
    def __init__ (self, _type, _dict = None):
        self._type = _type
        self._dict = _dict or {}

    def get_value (self, k):
        return self._dict [k]

    def del_value (self, k):
        if not self._dict.has_key (k):
            return False
        del (self._dict [k])
        return True

    def add_value (self, k, v):
        self._dict [k] = v
        return True

    def has_key (self, k):
        return self._dict.has_key (k)

    def toString (self):
        s = str ()
        for i, items in enumerate (self._dict.iteritems ()):
            k, v = items
            if i:
                s += ", "
            if v is not None:
                s += "%s=%s"%(k, v)
            else:
                s += "%s"%k
        return s

    get_type = lambda self: '<%s>'%str (self._type)
    get_dict = lambda self: self._dict
    __str__  = toString

### GLOBALS ###
thread_list = []
command_list = {}
profiles = {'default': Profile ('parameters'),
            'default_sip': Profile ('parameters', 
                                    {'contactuserinfo': 'mod_sipdbg',
                                     'allow': 'INVITE, ACK, CANCEL, BYE',
                                     'contact_expires': 300})}
profile_current_name = 'default'
profile_current = lambda: profiles [profile_current_name]
logger = None

from event import events_handler

def cmd_event_completion (argname, argv, text, idx):
    return [p for p in events_handler.keys () if p.startswith (text)]

def cmd_profile_completion (argname, argv, text, idx):
    return [p for p in profiles.keys () if p.startswith (text)]

def cmd_packet_completion (argname, argv, text, idx):
    return [p for p in profiles.keys () if \
                '<packet>' == profiles [p].get_type () and p.startswith (text)]

def cmd_open_proto (argname, argv, text, idx):
    _s = ['UDP', 'TCP']
    return [p for p in _s if p.startswith (text)]

def cmd_command_completion (argname, argv, text, idx):
    return [p for p in command_list.keys () if p.startswith (text)]

def profile_get_current ():
    global profile_current
    return profile_current ()

def profile_get (profile):
    global profiles
    return profiles [profile] if profiles.has_key (profile) else None

def profile_set_current (name):
    global profiles, profile_current_name
    if not profiles.has_key (name):
        return False
    profile_current_name = name
    return True

def profile_del (key):
    global profiles, profile_current_name
    if 'default' == key:
        logger.warn ("Cannot delete 'default' profile")
        return False
    if not profiles.has_key (key):
        return False
    current = True if profile_current_name == key else False
    del (profiles [key])
    if current:
        logger.warn ("New default profile is 'default'")
        profile_current_name = 'default'
    return True

def profile_create (profile_name, profile):
    global profiles
    if profiles.has_key (profile_name):
        logger.warning ("overriding profile %s"%profile_name)
    profiles [profile_name] = profile
    return True

def _profile_get (profile):
    global profile_current
    if not profile:
        profile = profile_current ()
    else:
        profile = profile_get (profile)
        if not profile:
            logger.error ("%s: No such profile"%profile)
            return False
    return profile

def profile_parameter_get (key, profile_name = None, profile = None):
    _p = profile or _profile_get (profile_name)
    if not _p:
        return False
    _r = None
    try:
        _r = _p.get_value (key)
    except KeyError:
        pass
    else:
        return _r
    return None

def profile_parameter_del (key, _profile = None):
    _p = _profile_get (_profile)
    if not _p:
        return False
    profile = _p
    if not profile.del_value (key):
        logger.error ("%s in '%s': No such value"%(key, _profile))
        return False
    return True

def profile_parameter_add (key, value = None, profile = None, force = False):
    _p = _profile_get (profile)
    if not _p:
        return False
    profile = _p
    if profile.has_key (key):
        if not force:
            logger.error ("parameter %s already exist"%key)
            return False
        logger.warning (
            "overriding parameters %s : %s -> %s"%(key,
                                                   profile.get_value (key),
                                                   value))
    profile.add_value (key, value)
    return True

def _handle_exception (e):
    exc_type, exc_value, exc_traceback = sys.exc_info ()
    logger.error ("Exception ! %s"%str (e))
    if exc_traceback is None:
        return None
    for line in traceback.extract_tb (exc_traceback):
        logger.error ("%s:%s in %s(): %s"%(line[0].split ("/")[-1], 
                                           line[1], line[2], line[3]))
    if None != exc_traceback:
        del (exc_traceback)    
    return True

def cmd_help (command):
    for _cmd in command:
        if command_list.has_key (_cmd):
            command_list [_cmd]['parser'].print_help ()
        else:
            logger.error ("Unknown command: %s"%_cmd)
    return True

def completer_dbg (text, state):
    try:
        return completer (text, state)
    except Exception, e:
        _handle_exception (e)
    return None

def completer (text, state):
    cmd = None
    args = None
    argcnt = 0
    options = None
    # get the whole line
    line = readline.get_line_buffer ()
    # if we have a command
    if -1 != line.find (" "):
        argv = line.split ()
        cmd = argv [0]
        args = argv [1:]
    # it is possible to call completion from other than end of line
    # we do not support this
    if len (line) != readline.get_endidx ():
        return None
    if cmd:
        # no match
        if not command_list.has_key (cmd):
            return None
        _r = parse_completion (line, command_list, not not text)
        # handle parse_completion return
        if tuple == type (_r):
            argname, idx = _r
            # check if the cmd has a completion helper
            completion_helper = command_list [cmd]\
                ['parser'].completion_cache [argname]['completion']
            # if migth be callable
            if completion_helper and callable (completion_helper):
                options = completion_helper (argname,
                                             argv,
                                             text,
                                             idx)
            # or a static list
            elif list == type (completion_helper):
                options = completion_helper
            # if text is null, and no handler filled data, use the help
            # associated with this command
            if 1 == idx and not text and not options:
                s_help = command_list [cmd]\
                    ['parser'].completion_cache [argname]['help']
                if s_help:
                    s = "%s:%s"%(argname, s_help)
                    options = [s, ""]
        elif dict == type (_r):
            if _r.has_key ('missing'):
                options = [
                    "%s: missing parameter [%s]"%(cmd, str (_r['missing'])),
                    " "]
            elif _r.has_key ('invalid'):
                options = [
                    "%s: invalid parameter [%s]"%(cmd, str (_r['invalid'])),
                    " "]
        elif str == type (_r):
            #curses.curs_set (2)
            if "OK" == _r [:2]:
                options = ["%s: ready"%cmd, " "]
        elif list == type (_r):
            options = _r
    elif not cmd:
        # command completion
        options = command_list.keys ()
    options = [opt for opt in options if opt and opt.startswith (text)] if   \
        text and options else options
    try:
        options [state]
    except (IndexError, TypeError):
        return None
    return options [state]

# The input file to read command
batchfile = None
# Wether or not we shall get a prompt after batchfile consomption
batchfile_shell = False

# Used to retrieve command from batchfile
def fd_generator ():
    try:
        getattr (fd_generator, 'cache')
    except:
        try:
            # generate OSError on failure
            os.stat (batchfile)
            # generate IOError for bad permission
            fd = open (batchfile)
            # OSError is for File not found, IOError for bad permission
        except (OSError, IOError) as e:
            logger.critical (str (e))
            sys.exit (0)
        setattr (fd_generator, 'cache', fd)
    else:
        fd = fd_generator.cache
    while True:
        line = fd.readline ()
        if not line:
            raise EOFError
        # Allow for comments
        elif '#' == line [0]:
            continue
        yield line

def my_raw_input (prompt):
    global batchfile, batchfile_shell
    if not batchfile or 1 is batchfile_shell:
        # No batchfile
        return raw_input (prompt)
    try:
        # batchfile
        return fd_generator ().next ()
    except EOFError:
        # batchfile consumed, switch to no batchfile mode ?
        if not batchfile_shell:
            # ... no
            raise
        # .. yes
        batchfile_shell = 1
        return my_raw_input (prompt)
    return None

def do_loop ():
    # parts from http://docs.python.org/release/2.6.1/library/readline.html
    histfile = os.path.join (os.path.expanduser ("~"), ".pyhist")
    try:
        readline.read_history_file (histfile)
    except IOError:
        pass
    atexit.register (readline.write_history_file, histfile)
    del (histfile)
    prompt = colored('sipdbg', 'blue', attrs=['bold'])+"> "
    readline.parse_and_bind ("tab: complete")
    readline.set_completer (completer_dbg)
    completer._cache = {"test": True} # XXX
    readline.insert_text ('>')
    readline.set_completer_delims (' \n')
    while 1:
        try:
            a = my_raw_input (prompt)
        except:
            print >> sys.stderr, "exiting"
            break
        argv = a.split ()
        if not argv:
            continue
        logger.debug ("Executing '%s'"%a)
        cmd = argv [0]
        # exception
        if cmd in ['help', '?'] and not argv [1:]:
            command_list [cmd]['parser'].print_help ()
            continue
        # exception
        if '#' == a [0]:
            continue
        if not command_list.has_key (cmd):
            logger.error ("%s: command not found"%cmd)
            continue
        r = command_list [cmd]['parser'].parse_args (argv [1:])
        if r is None:
            continue
        # Merge parameters from current profil
        _profile_current = profile_get_current ()
        func_var = command_list [cmd]['handler'].func_code.co_varnames \
            [:command_list [cmd]['handler'].func_code.co_argcount]
        newdict = {}
        profile_dict = _profile_current.get_dict ()
        for k in func_var if profile_dict else list ():
            _k = k.replace ('_', '-')
            # XXX: We assume a no-argument parameter is store_true but it migth
            # be store_false
            if profile_dict.has_key (_k):
                newdict [k] = profile_dict [_k] if \
                    profile_dict [_k] is not None else True
            elif profile_dict.has_key ('--%s'%_k):
                newdict [k] = profile_dict ["--%s"%_k] if \
                    profile_dict ["--%s"%_k] is not None else True
            else:
                continue
            logger.error (
                "# ADDED %s = %s"%(k, newdict [k]))
        # parameters from command line have priority over profile
        for k, v in vars (r).iteritems ():
            if newdict.has_key (k):
                if v in [None, False]:
                    continue
            newdict [k] = v
        _r = command_list [cmd]['handler'] (**newdict)
        if tuple == type (_r) and 3 == len (_r):
            _p = Profile (_r [1], _r [2])
            profile_create (_r [0], _p)
            logger.info (
                "Created profile '%s': type `%s`"%(_r [0], _r [1]))

def dummy_command_handler (_args):
    logger.info ("dummy command handler")
    return True

open_cnt = 0
def cmd_open (redis_host, host, port = 5060,
              redis_port = 6379,
              proto = 'UDP', name = None):
    global open_cnt
    try:
        int (redis_port)
        int (port)
    except ValueError, e:
        logger.error ("Invalid port range (%s)"%str (e))
        return False        
    _redis = _redis_connect (redis_host, int (redis_port))
    if not _redis:
        logger.error ("Cannot connect to Redis")
        return False
    client = ClientRedis (_redis)
    #ret = client.socket_sip (ip = host, port = port, proto = proto) XXX
    ret = client.socket_sip (port = 5064)
    v = client.server_reply (* ret)
    if not v:
        logger.error ("no server reply")
        return False
    if not name:
        open_cnt += 1
    name = name or "sip%d"%open_cnt
    _dict = { 'client': client,
        'redis_client': _redis,
        'server_id': v [0],
        'local_ip': host, 'local_port': port}
    return (name, 'interface', _dict)

from pkt import *

pkt_idx = 0
def cmd_packet (method,
                profile = None,
                body = None,
                outname = None,
                name = None,
                render = None,
                event = None,
                interface = None):
    global pkt_idx
    if render and not name:
        logger.error ("--render: specify a packet to dry rendering with --name")
        return False
    if not render:
        if not method:
            logger.error ("Specify a method with --method")
            return False
        elif method not in ['INVITE', 'REGISTER', 'SUBSCRIBE', 'BYE', 'CANCEL']:
            logger.error ("method unsupported at this time")
            return False
    else:
        pkt = profile_get (name)
        if not pkt:
            logger.error ("No such packet '%s'"%name)
            return False
        if '<packet>' != pkt.get_type ():
            logger.error (
                "Invalid profile %s, type '%s' not '<packet>'"%(name,
                                                                pkt.get_type()))
            return False
        s_pkt = profile_parameter_get ('pkt', profile = pkt)
        if not s_pkt:
            logger.error (
                "Internal error: 'pkt' not present in %s"%name)
            return False
        args = dict (**profile_current ().get_dict ())
        args.update (pkt.get_dict ())
        _r = packet_render (**args)
        if list is type (_r):
            logger.warn (
                "Rendering missing mandatory parameters : %s"%', '.join (
                    set (r.split (':')[1] for r in _r)))
            return False
        if outname:
            return (outname, 'packet', {'pkt': _r})
        return True
    pkt = None
    _dict = {}
    # DIALOG creation
    _dict_sip = profile_get ('default_sip')
    if _dict_sip:
        _dict.update (_dict_sip.get_dict ())
    _dict ['local_port'] = "__TEMPLATE__"
    _dict ['local_ip'] = "__TEMPLATE__"
    if method in ['INVITE', 'REGISTER', 'SUBSCRIBE']:
        _dict ['branch'] = "@@generate@@"
        _dict ['fromtag'] = "@@generate@@"
        _dict ['method'] = method
        _dict ['cseqnum'] = 1
    if 'INVITE' == method:
        pkt = dialog_invite (**profile_current ().get_dict ())
    elif 'REGISTER' == method:
        pkt = dialog_register (**profile_current ().get_dict ())
    elif 'SUBSCRIBE' == method:
        if not event:
            logger.error (
                "SUBSCRIBE method require --event")
            return False
        _d = dict (**profile_current ().get_dict ())
        _d ['event'] = event
        _dict ['expire'] = 60
        pkt = dialog_subscribe (**_d)
    elif 'CANCEL' == method:
        pkt = transaction_cancel (**profile_current ().get_dict ())
    elif 'BYE' == method:
        pkt = transaction_bye (**profile_current ().get_dict ())
    if not name:
        name = "pkt%d"%pkt_idx
        pkt_idx += 1
    _dict ['pkt'] = pkt
    return (name, 'packet', _dict)

def cmd_body (t, host, port = 5060, proto = 'UDP', name = None):
    global open_cnt
    _redis = _redis_connect (redis_host)
    if not _redis:
        logger.error ("Cannot connect to Redis")
        return False
    client = ClientRedis (_redis)
    ret = client.socket_sip (ip = host, port = port, proto = proto)
    v = client.server_reply (* ret)
    if not v:
        logger.error ("no server reply")
        return False
    if not name:
        open_cnt += 1
    name = name or "sip%d"%open_cnt
    return (name, 'body', {'server_id': v [0]})

def cmd_info (element, d = None):
    global profiles, profile_current_name
    if element not in ['profile', 'dialog']:
        return False
    if 'profile' == element:
        profile = d
        profile_name = None
        if profile:
            _profile = profile_get (profile)
            if not _profile:
                logger.error ("Profile '%s' not found"%profile)
                return False
            profile_name = profile
            profile = _profile
        else:
            profile = profile_get_current ()
            profile_name = profile_current_name
        if profile:
            logger.info (
                "Dumping profile '%s' (type '%s')"%(profile_name,
                                                     profile.get_type ()))
            d = profile.get_dict ()
            if not d:
                logger.warn (d or "empty profile")
                return True
            for k, v in d.iteritems ():
                logger.info ("%s%s"%(k, "=%s"%v if v is not None else ""))
            return True
        for k in profiles.key ():
            logger.info ("%s\ttype %s"%(k, profiles [k].get_type ()))
    elif 'dialog' == element:
        logger.error ('dialog here....')
    else:
        logger.error ('not implemented')
    return True

def cmd_profile (profile = None, current = None, info = None, show_log = None,
                 save_into_file = None, load_from_file = None, create = False,
                 delete = False,
                 name = None, list = None, force = False):
    global profile_current_name
    if profile:
        _profile = profile_get (profile)
        if create:
            if _profile and not force:
                logger.error ("profile %s exist, use --force to create"%profile)
                return False
        elif not _profile:
            logger.error ("Profile %s does not exist"%profile)
            return False
        profile_name = profile
    else:
        if create:
            logger.error ("--create requires --profile")
            return False
        _r = profile_get_current ()
        profile_name = profile_current_name
    if current:
        if not profile:
            logger.error ('You MUST specify a profile with --profile')
            return False
        if not profile_set_current (profile):
            logger.error ("Profile %s does not exist"%profile)
            return False
    elif show_log:
        logger.error ("show log not implemeted")
        return False
    elif info:
        return cmd_info ('profile', profile)
    elif save_into_file:
        _d = _profile.get_dict ()
        for k, v in _d.iteritems ():
            save_into_file.write ("%s=%s\n"%(k, v))
    elif load_from_file:
        i = 0
        while True:
            line = load_from_file.readline ().strip ()
            if not line:
                break
            k, v = line.split ('=', 1)
            if _profile.has_key (k) and not force:
                logger.warn (
                    "Ignoring key '%s' (existing), use --force to ovverride"%k)
                continue
            _profile.add_value (k, v)
            i += 1
        logger.info ("Loaded %d parameters into profile %s"%(i, profile_name))
    elif create:
        profile_create (profile, Profile ('parameters'))
        # XXX: add type ?
        logger.info ("profile '%s' created (type <parameters>)"%profile)
    elif list:
        logger.info ("List of profile:")
        for _p in profiles.keys ():
            logger.info ("%s\ttype: '%s'"%(_p, profiles [_p].get_type ()))
    elif delete:
        if not force:
            logger.warn (
                "Use --force to delete existing profile %s"%profile_name)
            return False
        logger.info (
            "Deleting profile '%s' (%d values)"%(profile_name,
                                                 len (_profile.get_dict ())))
        profile_del (profile_name)
    return True

def cmd_set (parameter, value = None, p = None, f = False, d = False):
    # deletion
    if d:
        return profile_parameter_del (parameter, p)
    # add
    profile_parameter_add (parameter, value, p, f)
    logger.debug (
        "profile '%s' added '%s'"%(p, parameter))
    return True

python_execution_context  = {}
dialog_dialplan_context   = {}

import pkt

def cmd_python (packet = None, profile = None, dialog = None, dialplan = None,
                custom = None, debug = False):
    reserved_keyword = ['for ', 'while ', 'for\t', 'while\t',
                        'if ', 'elif ', 'if\t', 'elif\t',
                        'else:', 'else ', 'else\t',
                        'except ', 'except:', 'except\t',
                        'try ', 'try:', 'try\t',
                        'def ', 'def\t', 'def:']
    # XXX : Always provide a "profile" variable with current/specified profile
    # E.G. :
    # pkt._h_X_custom = '{"key":"%s"}'%profile ['custom_header']
    try:
        getattr (pkt, 'logger')
    except:
        setattr (pkt, 'logger', logger)
        python_execution_context ['logger'] = logger
    namespace = None
    if custom or profile or packet:
        namespace = python_execution_context
    elif dialog or dialplan:
        namespace = pkt.__dict__
    else:
        logger.error ("No python namespace provided")
        return
    if debug:
        logger.debug ("Printing namespace")
        logger.debug (str (namespace))
    readline.parse_and_bind ("tab: self-insert")
    if profile:
        _p = profile_get (profile)
        if not _p:
            logger.error ("%s: No such profile"%profile)
            return False
        logger.info ("Profile %s loaded in variable `profile`"%profile)
        exec ("profile=_p.get_dict ()") in namespace
        cmd_example = "profile [key]=value"
        print >> sys.stderr, cmd_example
        readline.insert_text("profile [key]=value")
    elif dialog:
        cmd_example = "You can add a custom dialog handler"
        print >> sys.stderr, cmd_example        
    elif dialplan:
        cmd_example = "You can add a custom dialplan handler"
        print >> sys.stderr, cmd_example        
    elif packet:
        raise NotImplemented (
            "Load the packet '%s' in variable 'packet'"%packet)
        # _packet = profile_get (profile)
        # if not _p:
        #     logger.error ("%s: No such profile"%profile)
        #     return False
        # logger.info ("Profile %s loaded in variable `profile`"%profile)
        # exec ("profile=_p.get_dict ()") in namespace
        # cmd_example = "profile [key]=value"
        # print >> sys.stderr, cmd_example
        # readline.insert_text("profile [key]=value")
    cmd = str ()
    prompt = ">>> "
    stop = 0
    while True:
        append = False
        try:
            _s = my_raw_input (prompt)
        except (EOFError, KeyboardInterrupt):
            print >> sys.stderr
            break
        if not _s:
            stop += 1
            if 2 == stop:
                break
            try:
                if cmd:
                    exec (cmd) in namespace
            except SyntaxError as e:
                logger.warn ("SyntaxError: %s"%str (e))
            except Exception as e:
                logger.warn ("Exception: %s"%str (e))
            cmd = str ()
            prompt = ">>> "
            continue
        elif "EOF" == _s.strip ():
            print >> sys.stderr
            break
        stop = 0
        for _k in reserved_keyword:
            if _s [:len (_k)] == _k:
                append = True
        if _s [0] in ['\t', ' ']:
            append = True
        if not append:
            try:
                compile (_s, '', 'exec')
            except:
                append = True
        if not append:
            try:
                if cmd:
                    exec (cmd) in namespace
                exec (_s) in namespace
            except SyntaxError as e:
                logger.warn ("SyntaxError: %s"%str (e))
            except Exception as e:
                logger.warn ("Exception: %s"%str (e))
            cmd = str ()
            prompt = ">>> "
            continue
        cmd += "%s\n"%_s
        prompt = "... "
    try:
        if cmd:
            exec (cmd) in namespace
    except SyntaxError as e:
        logger.warn ("SyntaxError: %s"%str (e))
    except Exception as e:
        logger.warn ("Exception: %s"%str (e))
    readline.parse_and_bind ("tab: complete")
    return

from dialog import dialog_handler
import threading

from session import SIPSession

def cmd_interface (interface, start = False, 
                   bind = None, packet = None,
                   dest_ip = None, dest_port = None):
    global thread_list
    _p = profile_get (interface)
    if not _p:
        logger.error ("%s: No such profile"%interface)
        return False
    _d = _p.get_dict ()
    if '<interface>' != _p.get_type ():
        logger.error (
            "%s: profile is not of type 'interface' (%s)"%(interface,
                                                           _d.get_type ()))
        return False
    dialplan = None
    if bind: # dialplan
        try:
            dialplan = getattr (pkt, bind)
        except AttributeError:
            logger.error ("%s: no such dialplan"%bind)
            return False
        _d ['dialplan'] = dialplan
    if not _d.has_key ('dialplan'):
        logger.error ("%s: no dialplan binded to this interface"%interface)
        return False
    _pkt = profile_get (packet)
    if not _pkt:
        logger.error ("No such packet '%s'"%packet)
        return False
    if '<packet>' != _pkt.get_type ():
        logger.error (
            "Invalid profile %s, type '%s' not '<packet>'"%(name,
                                                            _pkt.get_type ()))
        return False
    s_pkt = profile_parameter_get ('pkt', profile = _pkt)
    if not s_pkt:
        logger.error (
            "Internal error: 'pkt' not present in %s"%packet)
        return False
    # Put current profile value
    args = dict (**profile_current ().get_dict ())
    # And packet-related value
    args.update (_pkt.get_dict ())
    # And interface value (local_ip, local_port)
    args.update (_d)
    _r = packet_render (**args)
    if list is type (_r):
        logger.warn (
            "Rendering missing mandatory parameters : %s"%', '.join (
                set (r.split (':')[1] for r in _r)))
        return False
    server_id = _d ['server_id']
    mypkt = _r
    mypkt.enable ()
    mypkt._from.enable ()
    client = _d ['client']
    # Initialize session
    session_id = SIPSession ()
    # set client
    session_id.client_init (client)
    session_id.set_server_id (server_id)
    # intialize dialog
    session_id.dialog_init (mypkt)
    # set initial packet informations
    session_id.set_fromtag (mypkt.fp)
    session_id.set_callid (str (mypkt.callid))
    session_id.set_branch (mypkt.vb)
    session_id.set_contact (mypkt.contact)
    session_id.set_ruri (mypkt.ruri)
    # set routing information
    session_id.set_dest_port (dest_port)
    session_id.set_dest_ip (dest_ip)
    if start:
        if not dest_ip:
            logger.warn ("Specify destination with --dest-ip")
            return False
        logger.info ("Sending packet .. (%s)"%id (client))
        logger.info ("%s (%s:%s)"%(server_id, dest_ip, dest_port))
        client.pkt_send (server_id, str (mypkt), dest_ip, dest_port)
    if bind:
        logger.info ("starting interface")
        _t = threading.Thread (target = dialog_handler, args = (session_id,
                                                                dialplan, args))
        thread_list += [_t]
        _t.deamon = True
        _t.start ()
    return

def register_commands (command_list = None):
    command_list = command_list if not command_list == None else {}
    # 'python' command
    cmd = 'python'
    parser = CompletionArgumentParser (cmd,
                                       description = 'Integrate python code',
                                       add_help = False)
    group = parser.add_mutually_exclusive_group ()
    group.add_argument ('--profile',
                        help="Provide a profile for manipulation")
    group.add_argument ('--packet', action='store_true', default=False,
                        help="packet manipulation context")
    group.add_argument ('--dialog', '--dialplan',
                        action='store_true', default=False,
                        help="dialog/dialplan manipulation context")
    group.add_argument ('--custom', action='store_true', default=False,
                        help="Provide a custom namespace (default)")
    command_list [cmd] = {'parser': parser}
    command_list [cmd] ['handler'] = cmd_python
    # 'set' command
    cmd = 'set'
    parser = CompletionArgumentParser (cmd,
                                       prefix_chars='+',
                                       description =
                                       'Use to set a parameter. Use bset to ' +
                                       'set a no-value parameter or delete a' +
                                       'key',
                                       add_help = False)
    parser.add_argument ('+p', metavar='profile',
                         completion = cmd_profile_completion,
                         help="Destination profile (otherwise current)")
    parser.add_argument ('+f', action='store_true',
                        help="Override if parameter exist (default: False)")
    parser.add_argument ('parameter', help="Parameter's name")
    parser.add_argument ('value', help="Parameter's value")
    command_list [cmd] = {'parser': parser}
    command_list [cmd] ['handler'] = cmd_set
    # 'bset' (bool set) command
    cmd = 'bset'
    parser = CompletionArgumentParser (cmd,
                                       prefix_chars='+',
                                       description = 
                                       'Single set and deletion of parameters.'+
                                       'Use set command to set a key-value '   +
                                       'parameter.',
                                       add_help = False)
    parser.add_argument ('+p', completion=cmd_profile_completion,
                         help="Destination profile (otherwise current)")
    parser.add_argument ('parameter', help="Parameter's name")
    parser.add_argument ('+d', action='store_true',
                         help="Delete")
    command_list [cmd] = {'parser': parser}
    command_list [cmd] ['handler'] = cmd_set
    # 'info' command
    cmd = 'info'
    parser = CompletionArgumentParser (cmd,
                                       description = 'Information on object',
                                       add_help = False)
    parser.add_argument ('element', choices=['profile', 'dialog', 'body'],
                         help="Specify which you want to manipulate")
    parser.add_argument ('-d', metavar='destination',
                         help="Specify the element destination")
    command_list [cmd] = {'parser': parser}
    command_list [cmd] ['handler'] = cmd_info
    # 'profile' command
    cmd = 'profile'
    parser = CompletionArgumentParser (cmd,
                                       description = 'Manage profile',
                                       add_help = False)
    group = parser.add_mutually_exclusive_group ()
    group.add_argument ('--current', help = "Make PROFILE the current profile",
                        action = 'store_true')
    group.add_argument ('--create', action='store_true',
                        help = "Create PROFILE")
    group.add_argument ('--delete', action='store_true',
                        help = "delete PROFILE")
    parser.add_argument ('--force', action='store_true',
                        help = "force creation")
    group.add_argument ('--list', help = "List profiles",
                        action = 'store_true')
    group.add_argument ('--info', help = "Provide informations",
                        action = 'store_true')
    group.add_argument ('--show-log', help = "Output profile's log",
                        action = 'store_true')
    group.add_argument ('--save-into-file', help = "Save profile into FILENAME",
                        metavar = 'FILENAME',
                        type=argparse.FileType ('w', 0))
    group.add_argument ('--load-from-file', help = "Load profile from FILENAME",
                        metavar = 'FILENAME',
                        type=argparse.FileType ('r', 0))
    parser.add_argument ('--profile', completion = cmd_profile_completion,
                         help = 
                         "Specify the profile, current profile otherwise")
                         
    command_list [cmd] = {'parser': parser}
    command_list [cmd]['handler'] = cmd_profile
    # PARENT REDIS
    parent_parser = CompletionArgumentParser (add_help = False)
    parent_parser.add_argument('redis_host',
                               help=
                               "redis DB hostname")
    parent_parser.add_argument('--redis-port', metavar='PORT', default=6379,
                               help=
                               "redis DB port (default: 6379)")
    # 'open' command
    cmd = 'open'
    parser = CompletionArgumentParser (
        cmd,
        parents=[parent_parser])
    parser.add_argument ('host',
                         help="hostname to connect to")
    parser.add_argument ('--port', '-p', default=5060,
                         help="SIP port to connect to (default: 5060)")
    parser.add_argument ('--proto', default='UDP', choices = ['TCP', 'UDP'],
                         completion = cmd_open_proto,
                         help="SIP signalisation protocol (default: UDP)")
    #parser.add_argument ('--debug', action='store_true',
    #                     help="debug mode")
    command_list [cmd] = {'parser': parser}
    command_list [cmd]['handler'] = cmd_open
    # 'body' command
    cmd = 'body'
    parser = CompletionArgumentParser (
        cmd,
        description = 'BODY creation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog = textwrap.dedent(
            'Example: body presence --help\nExample: body --create presence ' +
            '--name presence_xml_body1 presence --id joebar --status '        +
            'Unavailable'''),
        add_help = False)
    parser.add_argument ('--create', metavar='BODY_TYPE',
                         choices = ['sdp', 'presence'],
                         help="Create a body of type BODY_TYPE")
    parser.add_argument ('--name', 
                         help="Body name")
    subparsers = parser.add_subparsers (
        help='type the sub-command followed by --help for precisions')
    parser_blf = subparsers.add_parser ('presence',
                                        help="BLF\'s body argument")
    parser_blf.add_argument ('--id',
                             help="Presence's identity")
    parser_blf.add_argument ('--status',
                             help="Presence's status")
    parser_sdp = subparsers.add_parser ('sdp',
                                        help="SDP\'s body argument")
    parser_sdp.add_argument ('--port', type=int,
                             help="SDP port")
    parser_sdp.add_argument ('--ip', type=int,
                             help="SDP IP")
    # XXX : body not implemented
    #command_list [cmd] = {'parser': parser}
    #command_list [cmd]['handler'] = cmd_body
    # 'packet' command
    cmd = 'packet'
    PORT_SIP    = 5060
    parser = CompletionArgumentParser (
        cmd,
        description = 'SIP packet creation',
        epilog = 
        'Use --interface in order to retrieve the pair of local IP:PORT used '+
        'in the packet. All ommited parameter generates a template packet'    +
        'processed upon emission.',
        add_help = False)
    parser.add_argument ('--name',
                         help="packet's name")
    parser.add_argument ('--interface',
                        help = "retreive LOCAL_IP and LOCAL_PORT from that " +
                         "interface")
    parser.add_argument ('--profile', completion = cmd_profile_completion,
                        help = "use PROFILE as input argument (or current)")
    parser.add_argument ('--body',
                         help="Add a body object *NOT IMPLEMENTED*")
    parser.add_argument ('--event', completion = cmd_event_completion,
                        help = "method SUBSCRIBE requires --event")
    parser.add_argument ('--outname',
                        help = "with --render will generate an output packet")
    group = parser.add_mutually_exclusive_group ()
    group.add_argument ('--render', action='store_true',
                         help="DRY rendering, specify packet with --name")
    group.add_argument ('--method',
                         help="SIP method")
    command_list [cmd] = {'parser': parser}
    command_list [cmd] ['handler'] = cmd_packet
    # 'interface' command
    cmd = 'interface'
    PORT_SIP    = 5060
    parser = CompletionArgumentParser (
        cmd,
        description = 'SIP interface management',
        add_help = False)
    parser.add_argument ('interface', 
                         help = "interface's name")
    parser.add_argument ('--start', action='store_true', default=False,
                         help = "start the interface in a new thread")
    parser.add_argument ('--bind',
                         help = "Bind a dialplan to this interface")
    parser.add_argument ('--packet', completion = cmd_packet_completion,
                         help = "If specified, packet will be sent upon start")
    parser.add_argument ('--dest-ip',
                         help = "Destination host")
    parser.add_argument ('--dest-port', default=5060,
                         help = "Destination port (default: 5060)")
    command_list [cmd] = {'parser': parser}
    command_list [cmd] ['handler'] = cmd_interface
    # 'help' command
    cmd = 'help'
    help_command_list = command_list.keys ()
    help_command_list.sort ()
    help_command_list = 'List of command : ' + ' '.join (help_command_list)
    parser = CompletionArgumentParser (cmd, add_help = False,
                                       description = help_command_list)
    parser.add_argument ('command', nargs="+",
                         completion = cmd_command_completion,
                         help="get help on commands")
    command_list [cmd] = {'parser': parser}
    command_list [cmd]['handler'] = cmd_help
    cmd_alias = '?'
    command_list [cmd_alias] = {'parser': parser}
    command_list [cmd_alias]['handler'] = cmd_help
    return command_list

def exit_wait_thread ():
    for _t in thread_list:
        if not _t.is_alive ():
            continue
        thread.join ()

import atexit

if '__main__' == __name__:
    # Initialize logger
    logging.setLoggerClass (ColoredLogger)
    logger = ColoredLogger (sys.argv [0])
    # register command
    register_commands (command_list)
    if sys.argv [1:]:
        print >> sys.stderr, "Using batchfile %s"%sys.argv [1]
        batchfile = sys.argv [1]
    atexit.register (exit_wait_thread)
    do_loop ()

