#
# dialog handle is a dictionnary on the form :
# 2xx : handle 200 <= codes < 300
# 'METHOD': handle method 'METHOD'
# 401 : handle code 401
# 401|2xx : handle code 401 or code 2xx
# 
# 202 has priority over 2xx
#
# if 'default' is provided it handle unmatched packet
# if a 'pre_handler' is provided it execute before the handler
# if a 'post_handler' is provided it execute before the handler
# if a 'clean_handler' is provided it execute when last reference is deleted
#
# The value is the handler to be executed on reception of the SIP's code or
# method.
# If the value is a tuple, second parameter is the new dialog routing rules
#
# If the handler return a dialog routing rules, this is the new routing
# rules to be used. It has priority over tuple's second parameter routing rules.
# If it return True, the current dialog rules is kept.
# If it return False, the routing dialog stop its execution.
# If it return a list, second parameter is the new timeout
#
# An handler take the following parameter : session_id, pkt
# @client       : the Client instance
# @session_id   : session_id element which hold data
# @pkt          : received packet
# @pkt          : received packet
#
# session_id MUST BE an instance
#
# Exception.ReadTimeout will be raised of no data is received
# Exception.NoHandler will be raised if no handler is found
# 
# Main routine is 
# dialog_handler (client, session_data, dialog_handle, timeout = 10,
# @client a Client() instance
# @session_data an object to store session data (user's defined)
# @dialog_handle a dialog_handle dictionnary
# @timeout the redis timeout
# @maxtry if reemission is set to True the number of reemission before stopping
# @reemission boolean
#


# Example dialog routing rules follow
established_call_ack = end_call_ack = _4xx_handler_ack = do_authenticate = incoming_call = handle_notify = generate_500 = lambda: True

dialog_handle_cancel = {
    '4xx'       : _4xx_handler_ack,
    '5xx'       : lambda: None,
    }

dialog_handle_default = {
    'pre_handler': lambda pkt: None,
    'post_handler': lambda pkt: None,
    '100'       : lambda: None,
    '2xx | 200' : (established_call_ack, dialog_handle_cancel),
    'BYE'       : end_call_ack,
    '4xx'       : _4xx_handler_ack,
    '401 | 407' : do_authenticate,
    '5xx'       : lambda: None,
    'INVITE'    : incoming_call,
    'NOTIFY'    : handle_notify,
    'default'   : generate_500
    }

class NoHandler (Exception):
    pass

class ReadTimeout (Exception):
    pass

def handler_initialize (dialog_handle):
    handler = {}
    for k, v in ((e [0].split ('|'), e [1]) for e in dialog_handle.items ()):
        for _k in k:
            _k = _k.strip ()
            if _k.isdigit ():
                # codes
                handler [str (_k)] = v
            elif _k[0].isdigit () and "xx" == _k [-2:]:
                # generic codes
                handler [str (_k)] = v
            elif "default" == _k:
                # default
                handler [str (_k)] = v
            else:
                # methods
                handler [str (_k)] = v
    #for k, v in handler.iteritems ():
    #    print "'%s': %s,"%(k, v)
    return handler

def _handler_execute (handler, session_data, data, args = None):
    handler = handler [0] if tuple == type (handler) else handler
    func_var = handler.func_code.co_varnames [:
        handler.func_code.co_argcount]
    newdict = {'session_data': session_data, 'data': data}
    if args:
        for k in func_var:
            _k = k.replace ('_', '-')
            # XXX: We assume a no-argument parameter is store_true but it migth
            # be store_false
            if args.has_key (_k):
                newdict [k] = args [_k] if args [_k] is not None else True
            elif args.has_key ('--%s'%_k):
                newdict [k] = args ["--%s"%_k] if args ["--%s"%_k] is not \
                    None else True
    else:
        # No CLI mode
        pass
    return handler (**newdict)

def handler_execute (handler, session_data, data, args = None):
    s_id, timestamp, addr, pkt = data
    # Pre-handler
    if handler.has_key ('pre_handler'):
        handler ['pre_handler'] (session_data, data)
    # Find handler
    key = None
    if None is not pkt.rs:
        ht = str (pkt.rs / 100) + 'xx'
        hd = str (pkt.rs / 10) + 'x'
        if handler.has_key (str (pkt.rs)):
            key = str (pkt.rs)
        elif handler.has_key (ht):
            key = ht
        elif handler.has_key (hd):
            key = hd
    elif pkt.rm and handler.has_key (pkt.rm):
        key = pkt.rm
    elif handler.has_key ('default'):
        key = 'default'
    if not key:
        raise NoHandler (pkt)
    # Execute handler
    ret = _handler_execute (handler [key], session_data, data, args)
    if tuple == type (handler [key]):
        # priority over provided dialplan in case True is received
        ret = (ret and ret not in [True, False]) or handler [key][1]
    # Execute returned post_handler
    if ret:
        _handler = ret [0] if list == type (ret) else ret
        if dict == type (_handler) and _handler.has_key ('post_handler'):
            handler = _handler
    # Post handler
    if handler.has_key ('post_handler'):
        _handler_execute (handler ['post_handler'], session_data, data,
                          args)
    return ret or False

import time
def pre_handler (session_data, data):
    session_data.set_pkt_last_recv (data)
    return True

# Handle 'sending_queue'
# XXX TODO: Handle 'sending_timer_queue'
def post_handler (session_data, data):
    s_id, timestamp, addr, pkt = data
    client = session_data.get_client ()
    server_id = session_data.get_server_id ()
    for _pkt in session_data ['sending_queue'] if \
            session_data ['sending_queue'] else list ():
        client.pkt_send (server_id, str (_pkt),
                         session_data.get_dest_ip (),
                         session_data.get_dest_port ())
        session_data.set_pkt_last_sent ((time.time (), _pkt))
    session_data.set_sending_queue ([])
    return True

def dialog_handler (session_data, dialog_handle, args = None,
                    timeout = 10, maxtry = 10, reemission = False):
    client = session_data.get_client ()
    last_dialog_handle = None
    sid = None
    while True:
        if last_dialog_handle is not dialog_handle:
            # Initialize handler
            handler = handler_initialize (dialog_handle)
        last_dialog_handle = dialog_handle
        ret = True
        data = client.pkt_read_parse (session_data, timeout, maxtry, reemission,
                                      sid)
        if not data:
            raise ReadTimeout (timeout)
        key = None
        # pre-handler
        pre_handler (session_data, data)
        # Call handler
        _r = handler_execute (handler, session_data, data, args)
        # post-handler
        post_handler (session_data, data)
        if not _r:
            return data
        if not True is _r:
            if list == type (_r):
                if len (_r) is 4:
                    dialog_handle, timeout, reemission, sid = _r
                else:
                    dialog_handle, timeout, reemission = _r
            else:
                dialog_handle = _r
    raise

if '__main__' == __name__:
    pass
