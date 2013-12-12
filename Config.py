import imp
import sys

def Config (name, _exit = True):
    _name = name
    _i = name.rfind ('/')
    if -1 != _i:
        pathname, name = name.rsplit ('/', 1)
        pathname = [pathname]
    else:
        pathname = sys.path
    if ".py" == name [-3:]:
        name = name [:-3]
    try:
        fp, pathname, description = imp.find_module (name, pathname)
    except ImportError, e:
        if _exit:
            print "No such configuration file : '%s'"%_name
            sys.exit (-1)
        return None
    try:
        return imp.load_module (name, fp, pathname, description)
    finally:
        # Since we may exit via an exception, close fp explicitly.
        if fp:
            fp.close ()
    return None

if '__main__' == __name__:
    print __import__ ('c')
