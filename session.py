from client import ClientRedis

class SIPSession (dict):
    session_field = ['branch', 'totag', 'fromtag', 'callid', 'ruri', 'contact',
                     'fromuri', 'touri', 'iscaller',
                     'current_transaction_pkt', 'dialog_pkt',
                     'pkt_last_recv', 'pkt_last_sent',
                     'dest_ip', 'dest_port',
                     'client', 'server_id',
                     'sending_queue']

    def __create_function_set (self, key):
        def _function (value):
            self [key] = value
            return True
        return _function

    def __create_function_get (self, key):
        def _function ():
            return self [key]
        return _function

    def __init__ (self):
        for _k in SIPSession.session_field:
            # set default value to None
            self [_k] = None
            # initialize setters
            setattr (self, "set_%s"%_k, self.create_function_set (_k))
            # initialize getters
            setattr (self, "get_%s"%_k, self.create_function_get (_k))
        return

    def client_init (self, client):
        if not isinstance (client, ClientRedis):
            raise TypeError (
                "client must be instance of ClientRedis not type "      +
                "'%s'"%type (client))
        self ['client'] = client
        return True

    def dialog_init (self, pkt):
        # XXX : get a shallow copy ?
        # pkt = pkt.copy ()
        self ['dialog_pkt'] = pkt
        # first packet of a dialog is first transaction
        self.transaction_init (pkt)
        return True

    def transaction_init (self, pkt):
        self ['current_transaction_pkt'] = pkt
        return True

    def send_packet (self, pkt):
        if None is self ['sending_queue']:
            self ['sending_queue'] = []
        self ['sending_queue'] += [pkt]
        return True

if '__main__' == __name__:
    c = SIPSession ()
    c.set_totag (True)
    print c.get_totag ()
