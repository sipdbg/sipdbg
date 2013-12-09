# -- coding: utf-8 --
import pcapy
import impacket.ImpactDecoder as Decoders
import impacket.ImpactPacket as Packets
import sys
import tnetstring

filename        = "mydata.pcap"
outfile         = "rtp.out.py"
bpffilter       = None
if sys.argv [1:]:
    filename = sys.argv [1]
    if sys.argv [2:]:
        outfile = sys.argv [2]
    if sys.argv [3:]:
        bpffilter = sys.argv [3]
else:
    print "Usage: %s [pcap] [outfile] |[bpf filter]"%sys.argv [0]
    sys.exit (0)

reader = pcapy.open_offline (filename)
if bpffilter:
    print "Using filter [%s]"%bpffilter
    reader.setfilter (bpffilter)
eth_decoder = Decoders.EthDecoder ()
ip_decoder = Decoders.IPDecoder ()
udp_decoder = Decoders.UDPDecoder ()

pkt_list = []

i = 0
while True:
    try:
        (header, payload) = reader.next ()
        if not header and not payload:
            break
        i += 1
        ethernet = eth_decoder.decode (payload)
        if ethernet.get_ether_type () == Packets.IP.ethertype:
            ip = ip_decoder.decode (payload[ethernet.get_header_size ():])
            if ip.get_ip_p () == Packets.UDP.protocol: 
                udp = udp_decoder.decode (
                    payload[ethernet.get_header_size ()+ip.get_header_size ():])
                # print "IPv4 UDP packet %s:%d->%s:%d" % (ip.get_ip_src (),
                #                                         udp.get_uh_sport (),
                #                                         ip.get_ip_dst (),
                #                                         udp.get_uh_dport ()),
                udph_length = 8
                udp_data = payload [ ethernet.get_header_size () + 
                                     ip.get_header_size () + udph_length:]
                # print len (udp_data)
                pkt_list += [udp_data]
    except pcapy.PcapError:
        break
    except KeyboardInterrupt:
        print "dumping now"
        break
if not i:
    print "No packet match"
    sys.exit (1)
fd = open (outfile, "w+")
fd.write (tnetstring.dumps (pkt_list, 'iso-8859-15'))
fd.close ()
print "dumped %d's packets"%i
