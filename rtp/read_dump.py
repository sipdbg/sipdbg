import os
import sys
import tnetstring

def read_packets (filename):
    try:
        os.stat (filename)
    except OSError:
        print "No such file : %s"%filename
        sys.exit (1)
    pkts = open (filename).read ()
    pkts = tnetstring.loads (pkts, 'iso-8859-15')
    for data in pkts:
        yield data

if '__main__' == __name__:
    if not sys.argv [1:]:
        print "Usage: %s 'file'"%sys.argv [0]
        sys.exit (0)
    filename = sys.argv [1]
    for pkt in read_packets (filename):
        print "found %d's len packet"%len (pkt)
