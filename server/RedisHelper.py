import tnetstring

redis_server_command    = 'server'
redis_server_inst       = 'server_%.02d'
redis_send_id           = 'send_%.02d'
redis_client_reply      = 'client_%s'

class ServerUnknownCommand (Exception):
    pass

class RedisClient (object):
    # 
    # RTP / SIP packets
    #
    @staticmethod
    def server_send_pkt (_redis, s_id, pkt):
        _redis.lpush (redis_send_id%s_id,
                      tnetstring.dumps (pkt,
                                        'iso-8859-15'))
        return
    #
    # commands
    # 
    @staticmethod
    def server_create_sip (_redis, ckey, bind_ip, port):
        _redis.lpush (redis_server_command,
                      tnetstring.dumps (['CREATE_SIPUDP', [port, bind_ip],ckey],
                                        'iso-8859-15'))

    @staticmethod
    def server_create_sip_tcp (_redis, ckey, bind_ip, port):
        _redis.lpush (redis_server_command,
                      tnetstring.dumps (['CREATE_SIPTCP', [port, bind_ip],ckey],
                                        'iso-8859-15'))

    @staticmethod
    def server_create_rtp (_redis, ckey, bind_ip, port):
        _redis.lpush (redis_server_command,
                      tnetstring.dumps (['CREATE_RTP', [port, bind_ip], ckey],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_remove_sip (_redis, ckey, bind_ip, port):
        _redis.lpush (redis_server_command,
                      tnetstring.dumps (['REMOVE_RTP', [bind_ip, port], ckey],
                                        'iso-8859-15'))
        return
        

    @staticmethod
    def server_remove_sip (_redis, ckey, bind_ip, port):
        _redis.lpush (redis_server_command,
                      tnetstring.dumps (['REMOVE_SIP', [bind_ip, port], ckey],
                                        'iso-8859-15'))
        return
        

class RedisServer (object):
    # ckey -> client uuid
    # s_id -> identifier RTP/SIP
    # port -> RTP/SIP port
    # bind_ip -> RTP/SIP ip
    # rr -> server id
    @staticmethod
    def server_rtp_create (_redis, ckey, s_id, port, bind_ip, rr):
        _redis.lpush (redis_server_inst%rr,
                      tnetstring.dumps (["CREATE_RTP_SOCK",
                                         [s_id,
                                          bind_ip, port], ckey],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_rtp_create_reply (_redis, ckey, s_id):
        _redis.lpush (redis_client_reply%ckey,
                      tnetstring.dumps (["CREATE_RTP_REPLY",
                                         [s_id]],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_sip_create (_redis, ckey, s_id, bind_ip, port, rr, transport):
        _redis.lpush (redis_server_inst%rr,
                      tnetstring.dumps (["CREATE_SIP%s_SOCK"%transport,
                                         [s_id,
                                          bind_ip, port], ckey],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_sip_create_reply (_redis, ckey, s_id, transport):
        _redis.lpush (redis_client_reply%ckey,
                      tnetstring.dumps (["CREATE_SIP%s_REPLY"%transport,
                                         [s_id]],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_sip_remove (_redis, ckey, rr):
        _redis.lpush (redis_server_inst%rr,
                      tnetstring.dumps (["REMOVE_SIP_SOCK",
                                         [s_id, bind_ip, port], ckey],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_rtp_remove (_redis, ckey, rr):
        _redis.lpush (redis_server_inst%rr,
                      tnetstring.dumps (["REMOVE_RTP_SOCK",
                                         [s_id], ckey],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_success_reply (_redis, ckey, key):
        _redis.lpush (redis_client_reply%ckey,
                      tnetstring.dumps (["OK"],
                                        'iso-8859-15'))
        return

    @staticmethod
    def server_error_reply (_redis, ckey, key = None):
        _redis.lpush (redis_client_reply%ckey,
                      tnetstring.dumps (["ERROR",
                                         key],
                                        'iso-8859-15'))
        return

