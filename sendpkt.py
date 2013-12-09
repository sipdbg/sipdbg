import socket

def send_pkt (ip, port, data, port_src = None):
    sock = socket.socket (socket.AF_INET,        # Internet
                          socket.SOCK_DGRAM,
                          socket.IPPROTO_UDP)    # UDP
    #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #if port_src:
    #    sock.bind(('127.0.0.1', port_src))
    sock.sendto (data, (ip, port))
