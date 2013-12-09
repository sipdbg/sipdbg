import sys
import imp


class Config (object):
	def __init__(self, filename):
		self._confmod   = None
                self._module    = filename
                if ".py" != filename [-3:]:
                        raise ImportError (
                                'Config: File not python extension\n')
                if not self.load ():
                        raise ImportError (
                                'Config: Cannot load \'%s\''%filename)
                return

        def has_key (self, option):
                if '__' == option [:2] == option [-2:]:
                        return False
                return getattr (self._confmod, option, None)

	def __getattr__ (self, option):
                try:
                        return self._confmod.__getattribute__ (option)
                except AttributeError:
                        pass
		return None

	def load (self):
                try:
                        self._confmod = imp.load_source (
                                self.__class__.__name__,
                                self._module)
                except IOError:
                        pass
                else:
                        return True
                return False
        reload = load
