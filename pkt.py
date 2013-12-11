#
# session_data = {'branch', 'totag', 'fromtag', 'callid', 'ruri', 'contact',
#                 'fromuri', 'touri', 'iscaller',
#                 'current_transaction_pkt', 'dialog_pkt',
#                 'last_recv_pkt', 'last_sent_pkt',
#                 'sending_queue' : [<pkt0>, <pkt1>, ...]}
#
# send_packet ()
# recv_packet ()
#
# dialog_INVITE         [dialog = current_transaction = new (pkt),
#                       set session_data]
# transaction_create_INVITE (Re-INVITE)
#                       [dialog = current_transaction = new (pkt),
#                       set session_data]
# dialog_SUBSCRIBE      [dialog = current_transaction = new (pkt),
#                       set session_data]
# dialog_REGISTER       [dialog = current_transaction = new (pkt),
#                       set session_data]
# transaction_authenticate   [dialog]
# transaction_ack       [session_data, transaction=None]
# _do_code              [pkt]
# reply_200             [pkt]
# reply_486             [pkt]
# transaction_CANCEL    [session_data, transaction=CANCEL]
# transaction_BYE       [session_data, transaction=BYE]
#
# mandatory_METHOD_header_list,
# e.g. mandatory_invite_header_list = ['CSeq', 'To', 'From', ...]
# cmd_packet --> cmd_packet_invite @Return a TEMPLATE pkt
# 
from sipcore import *
from rand import *
from uri import *
from event import event_pkt_add, event_exist

template = '__TEMPLATE__'
generate = '@@generate@@'

def _do_code (session_data, code, reason, useragent = None):
    pkt = session # XXX
    pkt.enable ()
    #s_id, timestamp, addr, pkt = session ['last_recv_pkt']
    packet_reply_code = SIPpacket ()
    packet_reply_code.request.code = code
    packet_reply_code.request.reason = reason
    packet_reply_code.via = str (pkt.via)
    packet_reply_code._from = pkt._from
    packet_reply_code.to = pkt.to
    packet_reply_code.to.tag = pkt.tp
    #packet_reply_code.contact = session ['contact']
    packet_reply_code.callid = pkt.callid
    # Record-Route -> Route
    if pkt.header_exist ('Record-Route'):
        packet_reply_code._h_route = pkt.recordroute
    packet_reply_code.cseq = pkt.cseq
    packet_reply_code.cseq.method = pkt.rm
    packet_reply_code.maxforwards = 70
    if useragent:
        packet_reply_code.useragent = useragent
    packet_reply_code.contentlength = 0
    session_data.send_packet (str (packet_reply_code))
    return True

# Creation of helper reply code functions
for code, reason in sip_codes.iteritems ():
    code = 'reply_%d = lambda session: _do_code'\
        '(session_data, %d, "%s")'%(code, code, reason)
    exec (code)

def transaction_ack (session_data, data, ruri = None):
    s_id, timestamp, addr, pkt = session_data.get_pkt_last_recv ()
    ruri = ruri or session_data.get_ruri ()
    ack = SIPpacket ()
    ack.request.uri = ruri or session ['ruri']
    ack.request.method = "ACK"
    ack.via = str (pkt.via)
    ack._from = pkt._from
    ack.to = pkt.to
    ack.to.tag = pkt.tp
    ack.callid = pkt.callid
    # Record-Route -> Route
    if pkt.header_exist ('Record-Route'):
        ack._h_route = pkt.recordroute
    ack.cseq = pkt.cseq
    ack.cseq.method = "ACK"
    ack.maxforwards = 70
    #ack.useragent = config.useragent
    ack.contentlength = 0
    session_data.send_packet (str (ack))
    return True

def transaction_authenticate (session_data, data,
                              transaction = None, ruri = None,
                              authuser = None,
                              fromuser = None, 
                              password = None):
    if (not authuser and not fromuser) or not password:
        return False
    ruri = ruri or session_data.get_ruri ()
    transaction_ack (session_data, data, ruri)
    s_id, timestamp, addr, pkt = data
    pkt.enable ()
    #pkt.to.enable ()
    code = pkt.rs
    #session ['totag']   = pkt.tp
    lpkt                = session_data.get_current_transaction_pkt ()
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
    lpkt.enable ()
    _h_authentify.method = lpkt.rm
    _h_authentify.uri = str (ruri)
    _h_authentify.username = authuser or fromuser
    _h_authentify.password = password
    if lpkt.header_exist ("Content-Length"):
        lpkt.header_del ("Content-Length")
    lpkt._header_add (_h_authentify)
    # Update branch because it is a new transaction
    lpkt.via.uri.query.params ['branch'] = branch_new ()
    session_data.set_branch (lpkt.vb)
    # update current transaction
    session_data.transaction_init (lpkt)
    # send packet
    session_data.send_packet (str (lpkt))
    return True

def set_template (pkt, var, template = template):
    try:
        pkt.template_list.index (var)
    except ValueError:
        pkt.template_list += [var]
    return template

def create_header_via (pkt, local_ip = None, local_port = None):
    v = URI ()
    render_header_via (pkt, data = v)
    v.noscheme ()
    pkt._h_via = v
    return

def render_header_via (pkt, local_ip = None, local_port = None, data = None,
                       rport = False, branch = None):
    vial = data or pkt._h_via.uri
    vial.query.params ['rport'] = None if not rport else True
    vb = branch or set_template (pkt, 'Via:branch')
    if generate == vb:
        vb = branch_new ()
    vial.query.params ['branch'] = vb
    vial.host = local_ip or set_template (pkt, 'Via:local_ip')
    vial.port = local_port or set_template (pkt, 'Via:local_port')
    return

def create_header_to (pkt, dest_ip = None,
                      touser = None, todisplayname = None, totag = None):
    to_uri = NAMEADDR ()
    to_uri.uri = URI ()
    to_uri.uri.set_bracket (URI.bracket_pre_query)
    render_header_to (pkt, dest_ip, touser, todisplayname, totag, data = to_uri)
    pkt.to = to_uri
    return

def render_header_to (pkt, dest_ip = None,
                      touser = None, todisplayname = None, totag = None,
                      data = None):
    to_uri = data or pkt._h_to.value
    to_uri.uri.userinfo = touser or set_template (pkt, 'To:touser')
    to_uri.uri.host = dest_ip or set_template (pkt, 'To:dest_ip')
    if todisplayname:
        to_uri.display_name = todisplayname
    if totag:
        to_uri.uri.query.params ['tag'] = totag
    return

def create_header_from (pkt, fromuser = None, fromdisplayname = None,
                        local_ip = None):
    from_uri = NAMEADDR ()
    from_uri.uri = URI ()
    from_uri.uri.set_bracket (URI.bracket_pre_query)
    render_header_from (pkt, fromuser, fromdisplayname, local_ip,
                        data = from_uri)
    pkt._h_from = from_uri
    return

def render_header_from (pkt,
                        fromuser = None, fromdisplayname = None,
                        local_ip = None, fromtag = None, data = None):
    from_uri = data or pkt._h_from.value
    fp = fromtag or set_template (pkt, 'From:fromtag')
    if generate == fp:
        fp = fromtag_new ()
    from_uri.uri.query.params ['tag'] = fp
    from_uri.uri.host = local_ip or set_template (pkt, 'From:local_ip')
    from_uri.uri.userinfo = fromuser or set_template (pkt, 'From:fromuser')
    if fromdisplayname:
        from_uri.display_name = fromdisplayname
    return

def create_header_contact (pkt, contactuserinfo = None, fromuser = None,
                           local_ip = None, local_port = None,
                           expires = None):
    contact_uri = NAMEADDR ()
    contact_uri.uri = URI ()
    contact_uri.uri.set_bracket (URI.bracket_pre_query)
    render_header_contact (pkt,
                           contactuserinfo, local_ip, local_port,
                           expires, data = contact_uri)
    pkt._h_contact = contact_uri
    return

def render_header_contact (pkt, contactuserinfo = None,
                           local_ip = None, local_port = None,
                           contact_expires = None, data = None):
    contact_uri = data or pkt._h_contact.value
    contact_uri.uri.userinfo = contactuserinfo or \
        set_template (pkt, 'Contact:contactuserinfo')
    contact_uri.uri.host = local_ip or set_template (pkt,
                                                     'Contact:local_ip')
    contact_uri.uri.port = local_port or set_template (pkt, 
                                                       'Contact:local_port')
    if contact_expires:
        contact_uri.uri.query.params ['expires'] = contact_expires
    elif 'REGISTER' == pkt.request.method:
        set_template (pkt, 'Contact:contact_expires')
    return

def create_header_callid (pkt, local_ip = None, callid = None):
    if pkt.request.method in ['CANCEL', 'BYE']:
        callid = callid or set_template (pkt, 'Call-ID:callid')
    else:
        callid = callid or callid_new (
            local_ip or set_template (pkt, 'Call-ID:local_ip'))
    pkt._h_callid = callid
    return

def render_header_callid (pkt, local_ip = None, callid = None):
    if not local_ip and not callid:
        return
    if callid:
        pkt._h_callid = callid
        return
    callid = str (pkt._h_callid)
    pkt._h_callid = callid.replace (template, local_ip)
    return

def create_header_cseq (pkt, method = None, cseqnum = None, cseqmethod = None):
    render_header_cseq (pkt, method, cseqnum)
    return

cseqnum_idx = 1
def render_header_cseq (pkt, method = None, cseqnum = None):
    if not method:
        set_template (pkt, 'CSeq:method')
        set_template (pkt, 'CSeq:cseqnum')
        pkt._h_cseq = str ()
        return
    if not cseqnum:
        global cseqnum_idx
        cseqnum = cseqnum_idx
        cseqnum_idx += 1
    pkt._h_cseq = "%s %s"%(str (cseqnum), method)
    return

def create_header_maxforwards (pkt, maxforwards = None):
    pkt.maxforwards = maxforwards or 70
    return

def render_header_maxforwards (pkt):
    pass

def create_header_useragent (pkt, useragent = None):
    return render_header_useragent (pkt, useragent)

def render_header_useragent (pkt, useragent = None):
    if useragent:
        pkt.useragent = useragent
    return

def create_header_allow (pkt, allow = None):
    render_header_allow (pkt, allow)
    return
                         
def render_header_allow (pkt, allow = None):
    pkt._h_allow = allow or set_template (pkt, 'Allow:allow')
    return

def create_header_expires (pkt, expire = None):
    render_header_expires (pkt, expire)
    return
                         
def render_header_expires (pkt, expire = None):
    pkt._h_expires = expire or set_template (pkt, 'Expires:expire')
    return

def render_ruri (pkt, method, touser = None, dest_ip = None,
                 contactbleg = None):
    if template == pkt.request.uri:
        pkt.request.uri = URI ()
    if contactbleg:
        if str is type (contactbleg):
            pkt.request.uri.fromString (contactbleg)
        else:
            pkt.request.uri = contactbleg
        return True
    if touser and 'REGISTER' != method:
        pkt.request.uri.userinfo = touser
    if dest_ip:
        pkt.request.uri.host = dest_ip
    return

hdr_list = {}
def __init_header__ ():
    """
    This function will build an exhaustive list of supported header's function
    """
    global hdr_list
    if hdr_list:
        return
    hdr_list = {}
    for h in sys.modules [__name__].__dict__.keys ():
        if len (h) > 14 and 'create_header_' == h [:14]:
            hdr_list [h [14:].lower ()]= (getattr (sys.modules [__name__], h),
                                          getattr (sys.modules [__name__],
                                                   'render_header_' + h [14:]))
    return

def _get_helper_header (hdr):
    if not hdr_list:
        __init_header__ ()
    hdr = hdr.lower ()
    hdr = hdr.replace ('-', '')
    return hdr_list [hdr] if hdr_list.has_key (hdr) else None

def get_create_header (hdr):
    hdr = hdr.lower ()
    helper_fptr = _get_helper_header (hdr)
    return helper_fptr [0] if helper_fptr else None

def get_render_header (hdr):
    hdr = hdr.lower ()
    helper_fptr = _get_helper_header (hdr)
    return helper_fptr [1] if helper_fptr else None

def dialog_invite (*args, **kwargs):
    method = 'INVITE'
    dest_ip = kwargs ['dest_ip'] if kwargs.has_key ('dest_ip') else None
    touser = kwargs ['touser'] if kwargs.has_key ('touser') else None
    pkt = SIPpacket ()
    pkt.template_list = []
    # R-URI
    ruri = URI ()
    ruri.userinfo = touser or set_template (pkt, 'ruri:touser')
    ruri.host = dest_ip or set_template (pkt, 'ruri:dest_ip')
    pkt.request.uri = ruri
    pkt.request.method = method
    mandatory_invite_header_list = kwargs ['mandatory_invite_header_list'] if \
        kwargs.has_key ('mandatory_invite_header_list') else \
        ['Via', 'From', 'To', 'Contact', 'Call-ID', 'CSeq', 'Max-Forwards',
         'User-Agent', 'Allow']
    for _h in mandatory_invite_header_list:
        hfptr = get_create_header (_h)
        func_var = hfptr.func_code.co_varnames [:hfptr.func_code.co_argcount]
        newdict = {}
        for k in func_var if kwargs else list ():
            _k = k.replace ('_', '-')
            if kwargs.has_key (_k):
                newdict [k] = kwargs [_k]
                print ("ADDED %s = %s"%(k, newdict [k]))
        hfptr (pkt, **newdict)
    return pkt

def dialog_register (*args, **kwargs):
    method = 'REGISTER'
    dest_ip = kwargs ['dest_ip'] if kwargs.has_key ('dest_ip') else None
    touser = kwargs ['touser'] if kwargs.has_key ('touser') else None
    pkt = SIPpacket ()
    pkt.template_list = []
    # R-URI
    ruri = URI ()
    ruri.host = dest_ip or set_template (pkt, 'ruri:dest_ip')
    pkt.request.uri = ruri
    pkt.request.method = method
    mandatory_invite_header_list = [
        'Via', 'From', 'To', 'Contact', 'Call-ID', 'CSeq', 'Max-Forwards',
        'User-Agent', 'Allow' ]
    for _h in mandatory_invite_header_list:
        hfptr = get_create_header (_h)
        func_var = hfptr.func_code.co_varnames [:hfptr.func_code.co_argcount]
        newdict = {}
        for k in func_var if kwargs else list ():
            _k = k.replace ('_', '-')
            if kwargs.has_key (_k):
                newdict [k] = kwargs [_k]
                print ("ADDED %s = %s"%(k, newdict [k]))
        hfptr (pkt, **newdict)
    return pkt

def dialog_subscribe (*args, **kwargs):
    method = 'SUBSCRIBE'
    dest_ip = kwargs ['dest_ip'] if kwargs.has_key ('dest_ip') else None
    touser = kwargs ['touser'] if kwargs.has_key ('touser') else None
    event = kwargs ['event'] if kwargs.has_key ('event') else None
    if not event:
        #logger.error (
        print (
            "SUBSCRIBE requires --event")
        return False
    elif not event_exist (event):
        #logger.error (
        print (
            "event '%s' is not supported"%event)
        return False
    pkt = SIPpacket ()
    pkt.template_list = []
    # R-URI
    ruri = URI ()
    ruri.userinfo = touser or set_template (pkt, 'ruri:touser')
    ruri.host = dest_ip or set_template (pkt, 'ruri:dest_ip')
    pkt.request.uri = ruri
    pkt.request.method = method
    mandatory_invite_header_list = [
        'Via', 'From', 'To', 'Contact', 'Call-ID', 'CSeq', 'Max-Forwards',
        'User-Agent', 'Allow', 'Expires' ]
    for _h in mandatory_invite_header_list:
        hfptr = get_create_header (_h)
        func_var = hfptr.func_code.co_varnames [:hfptr.func_code.co_argcount]
        newdict = {}
        for k in func_var if kwargs else list ():
            _k = k.replace ('_', '-')
            if kwargs.has_key (_k):
                newdict [k] = kwargs [_k]
                print ("ADDED %s = %s"%(k, newdict [k]))
        hfptr (pkt, **newdict)
    event_pkt_add (pkt, event)
    return pkt

def transaction_new (*args, **kwargs):
    method = kwargs ['method']
    header_list = kwargs ['header_list']
    del (kwargs ['method'])
    del (kwargs ['header_list'])
    if method not in ['INVITE', 'CANCEL', 'BYE', 'UPDATE', 'INFO']:
        return False
    if not header_list:
        return False
    contactbleg = kwargs ['contactbleg'] if \
        kwargs.has_key ('contactbleg') else None
    pkt = SIPpacket ()
    pkt.template_list = []
    # R-URI
    pkt.request.uri = contactbleg or set_template (pkt, 'ruri:contactbleg')
    pkt.request.method = method
    for _h in header_list:
        hfptr = get_create_header (_h)
        func_var = hfptr.func_code.co_varnames [:hfptr.func_code.co_argcount]
        newdict = {}
        for k in func_var if kwargs else list ():
            _k = k.replace ('_', '-')
            if kwargs.has_key (_k):
                newdict [k] = kwargs [_k]
                print ("ADDED %s = %s"%(k, newdict [k]))
        hfptr (pkt, **newdict)
    # XXX
    #session ['sending_queue'] += [str (packet_reply_code)]
    return True

def transaction_bye (*args, **kwargs):
    method = 'BYE'
    mandatory_bye_header_list = [
        'Via', 'From', 'To', 'Call-ID', 'CSeq', 'Max-Forwards', 'User-Agent' ]
    kwargs ['method'] = method
    kwargs ['header_list'] = mandatory_bye_header_list
    return transaction_new (**kwargs)

def transaction_cancel (*args, **kwargs):
    method = 'CANCEL'
    mandatory_cancel_header_list = [
        'Via', 'From', 'To', 'Call-ID', 'CSeq', 'Max-Forwards' ]
    kwargs ['method'] = method
    kwargs ['header_list'] = mandatory_cancel_header_list
    return transaction_new (**kwargs)

# Re-INVITE (with totag)
def transaction_invite (*args, **kwargs):
    method = 'INVITE'
    mandatory_invite_header_list = [
        'Via', 'From', 'To', 'Call-ID', 'CSeq', 'Max-Forwards' ]
    kwargs ['method'] = method
    kwargs ['header_list'] = mandatory_invite_header_list
    return transaction_new (**kwargs)

def packet_render (*args, **kwargs):
    pkt = kwargs ['pkt']
    _kwargs = {}
    # XXX FIXUP
    for k, v in kwargs.iteritems ():
        _kwargs [k.replace ('_', '-')] = v
    kwargs = _kwargs
    # XXX FIXUP
    if not pkt.template_list:
        return pkt
    # create a shallow copy
    template_list = list (pkt.template_list)
    for _k in pkt.template_list:
        _h = None
        kb = _k
        if -1 == _k.find (':'):
            print "Malformed template %s"%_k
            continue
        _h, _key = _k.split (':', 1)
        # exception RURI
        if 'ruri' == _h:
            hfptr = render_ruri
        else:
            hfptr = get_render_header (_h)
        func_var = hfptr.func_code.co_varnames [:hfptr.func_code.co_argcount]
        newdict = {}
        for k in func_var if kwargs else list ():
            if 'data' == k:
                continue
            _kn = k.replace ('_', '-')
            if kwargs.has_key (_kn):
                newdict [k] = kwargs [_kn] if \
                    kwargs [_kn] is not None else True
            elif kwargs.has_key ('--%s'%_kn):
                newdict [k] = kwargs ["--%s"%_kn] if \
                    kwargs ["--%s"%_k] is not None else True
        if newdict.has_key (_key):
            template_list.remove (_k)
        hfptr (**newdict)
    # If the template_list is non-empty
    if template_list:
        # and there is template's information inside, trigger an error
        if -1 != str (pkt).find (template):
            return template_list
            #return pkt.template_list
        # otherwise they are optional
        pass
    # pkt.template_list = []
    pkt._from.enable ()
    # session_id = dict ([('fromtag', pkt.fp), ('callid', pkt.callid),
    #                     ('branch', pkt.vb),
    #                     ('contact', str (pkt._h_contact)),
    #                     ('ruri', str (pkt.request.uri))])
    return pkt

if '__main__' == __name__:
    #pkt = packet_forge_invite (**{'dest_ip':'172.16.2.27'})
    pkt = dialog_subscribe (**{'dest_ip':'172.16.2.27','event':'dialog'})
    print pkt,
    pkt = packet_render (pkt = pkt, local_ip = "127.0.0.1", local_port = 5062,
                         fromuser = 'myfromuser', touser = 'mytouser',
                         dest_ip = '172.16.171.60', 
                         allow = 'INVITE, ACK, BYE',
                         method = 'SUBSCRIBE',
                         cseqnum = 2600, contactuserinfo = 'sofia', expire=400,
                         totag="mytotag3",
                         branch = generate, fromtag = generate)
    print pkt
    if False is not pkt:
        print pkt,
    pkt_needauth = reply_401 (pkt)
    pkt_needauth._h_wwwauthenticate = 'Digest realm="myrealm", nonce="4cc0339486b3e109de8f5e64f1c1a7c777ed4bc6", stale=true'
    print pkt_needauth
    print transaction_ack (pkt_needauth, "sip:sdf@1.2")
    c = transaction_authenticate (pkt_needauth, pkt, str (pkt.request.uri),
                                    authuser = "sipdbg", password = "secret")
    print c
    print reply_200 (c)
    # print packet_render (pkt = pkt_ok, contactbleg = "sip:sofia_contact@1.2",
    #                      local_ip = "127.0.0.1", local_port = 5062,
    #                      fromuser = 'myfromuser', touser = 'mytouser',
    #                      dest_ip = '172.16.171.60', callid="sdklfjsklfdj",
    #                      cseqnum = 1, method = "BYE",
    #                      branch = 'mylocalbranch',
    #                      fromtag = "myfromtag", totag="mytotag")
    '''
    BYE __bleg_contact_uri__ SIP/2.0
    Via: SIP/2.0/UDP __mylocalvia__
    From: __myfromnameaddr__
    To: __remotenameaddr__
    Call-ID: 3c364d8fdbba-9jj6lucv7jst@snom360-00041329047B
    CSeq: X BYE
    Max-Forwards: 70
    '''
    bpkt = transaction_bye ({})
    print bpkt
    pkt = packet_render (pkt = bpkt, contactbleg = "sip:sofia_contact@1.2",
                         local_ip = "127.0.0.1", local_port = 5062,
                         fromuser = 'myfromuser', touser = 'mytouser',
                         dest_ip = '172.16.171.60', callid="sdklfjsklfdj",
                         cseqnum = 1, method = "BYE", branch = 'mylocalbranch',
                         fromtag = "myfromtag", totag="mytotag")
    print pkt
