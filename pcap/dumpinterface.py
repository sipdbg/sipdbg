import sys, os
import tnetstring
main_path = os.path.abspath (os.path.dirname (__file__))
prev_path = main_path + "/.."
sys.path.append (prev_path)
# Ordered dictionnary
from dictorder import odict

class DumpInterface (object):
    def is_pair (i):
        if not i or not i % 2:
            return True
        return False

    def __init__ (self, sip_comm, sip_data, rtp_flow):
        for uuid, cnt in sip_comm.iteritems ():
            path = "%s/%s/"%(main_path, uuid)
            print 'Dumping SIP uuid:\'%s\' (%d packets) in %s'%(uuid, cnt, path)
            dialog, arr = sip_data [uuid]
            i = 0
            filearr = []
            try:
                os.makedirs (path)
            except OSError, e:
                # directory might already exist
                pass
            listpath = "%s/list.txt"%path
            listfd = open (listpath, "w+")
            listfd.write (
                "# This file contains the listing of %d's dumped packets\n"%cnt)
            listfd_legs = []
            for timestamp, addr, pkt, legs_n in arr:
                if not listfd_legs:
                    timestamppath = "%s/timestamp.txt"%path
                    timestampfd = open (timestamppath, "w+")
                    timestampfd.write (str (timestamp))
                    timestampfd.close ()
                    
                if legs_n in listfd_legs:
                    continue
                listfd_legs += [legs_n]
                src, dst = (addr [0], addr [1]), (addr [2], addr [3])
                listfd.write ("# legs_%d from %s to %s\n"%(legs_n,
                                                         str (src),
                                                         str (dst)))
            for timestamp, addr, pkt, legs_n in arr:
                src, dst = (addr [0], addr [1]), (addr [2], addr [3])
                dirpath = "%s/legs_%d"%(path, legs_n)
                filename = "%d.txt"%i
                filepath = "%s/%s"%(dirpath, filename)
                filearr += [tnetstring.dumps ([filepath, timestamp, 
                                               list (addr)])]
                listfd.write ("legs_%d/%d.txt\n"%(legs_n, i))
                try:
                    os.makedirs (dirpath)
                except OSError, e:
                    # directory might already exist
                    pass
                fd = open (filepath, "w+")
                fd.write (tnetstring.dumps ([timestamp, list (addr), str (pkt)],
                                            'iso-8859-15'))
                fd.close ()
                i += 1
            listfd.close ()
            controlpath = "%s/control.txt"%path
            fd = open (controlpath, "w+")
            fd.write (tnetstring.dumps (filearr,
                                        'iso-8859-15'))
            fd.close ()
            if not dialog.has_key ('traffic_rtp'):
                print "no rtp"
                return True
            rtppath = "%s/rtp.txt"%path
            rtpfd = open (rtppath, "w+")
            rtpfd.write (
                "# This file contains RTP informations of rtp_X.out\n")
            for rtp_host, rtp, legs_n in dialog ['traffic_rtp']:
                rtpfd.write (
                    "# rtp_%d.out %s : %d packets\n"%(legs_n,
                                                      str (rtp_host),
                                                      len (rtp)))
                rtpleg = open ('%s/rtp_%d.out'%(path, legs_n), 'w+')
                rtpleg.write (tnetstring.dumps (rtp,
                                                'iso-8859-15'))
                rtpleg.close ()
            rtpfd.close ()
