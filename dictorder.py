"""
python ordered dictionnary
Copyright (C) 2012 sipdbg@member.fsf.org

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "sipdbg@member.fsf.org"

class odict (object):
    function_list = ['clear', 'copy', 'get', 'has_key', 'items', 'keys',
                     'pop', 'popitem', 'setdefault', 'update', 'values',
                     'iteritems', '__getattribute__']

    def __init__ (self, kw = None, default_none = False):
        self._default_none = default_none
        self.__okeys = []
        self.__dict = dict ()
        for k, v in kw if kw and type(kw) == list else list ():
            setattr (self, k, v)
            self [k] = v
        return

    def __delitem__ (self, key):
        if key not in self.__okeys:
            if int is type (key) and len (self.__okeys) >= key:
                self.__dict.__delitem__(self.__okeys [key])
                del (self.__okeys [key])
                return
            else:
                raise KeyError, key
        self.__dict.__delitem__ (key)
        self.__okeys.remove (key)
        return

    def __setitem__ (self, key, item):
        self.__dict.__setitem__(key, item)
        if key not in self.__okeys:
            self.__okeys.append (key)
        return

    def __getitem__ (self, key):
        if key not in self.__okeys:
            # You also can retrieve odict () member by index
            if int is type (key):
                if len (self.__okeys) > key:
                    return self.__okeys [key], self.__dict [self.__okeys [key]]
                raise KeyError ("index too large")
        return self.__dict.__getitem__(key)

    def __iter__ (self):
        for key in self.__okeys:
            yield key
        #    yield key, self.__dict [key]

    def __getattribute__ (self, key):
        if key [0:8] == '_odict__' or key in odict.function_list:
            return object.__getattribute__ (self, key)
        if not self.__dict.has_key (key):
            if object.__getattribute__ (self, '_default_none'):
                return None
            raise KeyError, key
        return self.__dict [key] 

    def __len__ (self):
        return len (self.__dict)

    def toString (self):
        s = "{"
        for key in self.__okeys:
            if "{" != s:
                s += ", "
            s += "'%s': "%str (key)
            s += "%s"%str (self.__dict [key])
        s += "}"
        return s
    __repr__ = __str__ = toString

    def clear (self):
        self.__dict.clear ()
        self.__okeys = []
        return

    def copy (self):
        scopy = odict ()
        for k, v in self.iteritems ():
            scopy [k] = v
        return scopy

    def get (self, key, d = None):
        return self.__dict [key] or d

    def has_key (self, key):
        return key in self.__okeys

    def items (self):
        return zip (self.__okeys, map (self.__dict.get, self.__okeys))

    def keys (self):
        return self.__okeys

    def pop (self, k, d = None):
        if k in self.__okeys:
            r = self.__dict [k]
            self.__okeys.remove (k)
            del (self.__dict [k])
            return r
        if not d:
            raise KeyError, 'pop(): ordered dictionary is empty'
        return d

    def popitem (self):
        try:
            key = self.__okeys.pop ()
        except IndexError:
            raise KeyError, 'popitem(): ordered dictionary is empty'
        val = self.__dict [key]
        del self.__dict [key]
        return (key, val)

    def setdefault (self, key, failobj = None):
        ret = self.__dict.setdefault (key, failobj)
        if key not in self.__okeys:
            self.__okeys.append (key)
        return ret

    def update (self, _dict):
        for k, v in _dict.iteritems ():
            self [k] = v

    def values (self):
        return map (self.__dict.get, self.__okeys)

    def iteritems (self):
        return list (((k, self.__dict [k]) for k in self.__okeys))
