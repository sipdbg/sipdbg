# 2013 -- sipdbg project -- argparse addon with completion (readline)
import argparse
from dictorder import odict

__license__ = "GNU GPL v3"
__author__ = "sipdbg@member.fsf.org"

# @retval True (if all arguments are consumed)
# @retval {'missing_positional': ...} (list of missing positional arguments)
# @retval {'missing': ...} (list of missing optional) XXX 
# @retval {'invalid': ...} (invalid : contains reason) XXX
# @retval type list (contains possible matchs)
# @retval type tuple (contains: 'argument name', offset)
def parse_positional (argv, idx, text,
                      optional_parameters_list,
                      positional_parameters_list, processed = 0):
    argcnt = len (argv)
    if idx == argcnt:
        # if we reach the end and there is still positional parameters,
        # indicate a missing positional parameter
        if positional_parameters_list:
            # if we consummed already one positional
            if processed:
                return {'missing_positional':
                            positional_parameters_list.keys ()}
            # else ask for any parameters possible
            _r = optional_parameters_list.keys () + \
                ["[%s]"%param for param in positional_parameters_list.keys ()]
            return _r
        # else if there is no optional_parameters_list neither, indicate OK
        elif not optional_parameters_list:
            return True
        # else offers possible optional parameters remaining
        return optional_parameters_list.keys ()
    # If this match an optional parameter, parse it
    if argv [idx] in optional_parameters_list.keys ():
        positional_parsed = True
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    # Or if there is no more positional parameters
    elif not len (positional_parameters_list):
        positional_parsed = True
        # and if we are at the end
        if idx == argcnt:
            # if no more parameters at all to parse, command line is ready
            if not len (optional_parameters_list):
                return True
            # matchs is possible optional-parameters
            return optional_parameters_list.keys ()
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    # get next positional parameter in "arg"
    argname, arg = positional_parameters_list [0]
    # If we are at the end, ask for completion
    if idx >= argcnt:
        return (argname, 0)
    # process this positional's parameter arguments now
    # arg ['nargs'] == 1 is default
    if 1 == arg ['nargs']:
        # if there is nothing left after the argument
        if argcnt == (idx + 1):
            return (argname, 1)
        # skip this parameter's argument
        idx += 2
        # consume this positional parameter
        del (positional_parameters_list [0])
        # scan next positional parameter
        return parse_positional (argv, idx, text,
                                 optional_parameters_list,
                                 positional_parameters_list, processed + 1)
    # this positional parameter has no argument
    elif 0 == arg ['nargs']:
        # skip this parameter
        idx += 1
        # TODO: if not arg.multiple
        # consume this positional parameter
        del (positional_parameters_list [0])
        # scan next positional parameter
        return parse_positional (argv, idx, text,
                                 optional_parameters_list,
                                 positional_parameters_list, processed + 1)
    # '?' means O or 1 (it is optional)
    elif '?' == arg ['nargs']:
        # NOTE: This is a special case because this parameter can be
        # optional (defined with nargs="?" or nargs="*").
        # If it has been ommited on cmdline and we process it, we migth end
        # messing with others parameters (optionals positional parameters
        # are not prioritary).
        # 
        # We fix this case using this algorithm :
        # store everything before an optional_parameter or "--" in list_parg
        # scans remaining positional and sum nargs in parg_score, with :
        # 0 when 'nargs' is "?" or "*"
        # 1 when 'nargs' is '+' or when it is 0 (action takes not argument)
        # N when nargs is N (an integer)
        #
        # if list_parg < parg_score, we discard this parameter (as argparse
        # will do)
        list_parg_idxend = idx + 1
        if list_parg_idxend == argcnt:
            if len (positional_parameters_list):
                argnme, arg = positional_parameters_list [1]
                # priorize next positional ?
                if arg ['nargs'] in [0, '+'] or int == type (arg ['nargs']):
                    idx -= 1 # i am terribly tired so this code is ugly
            # scan next positional parameter
            idx += 1
            # consume this positional parameter
            del (positional_parameters_list [0])
            return parse_positional (argv, idx, text,
                                     optional_parameters_list,
                                     positional_parameters_list, processed + 1)
        list_parg = None
        while not \
                optional_parameters_list.has_key (argv [list_parg_idxend]) and\
                "--" != argv [list_parg_idxend]:
            list_parg_idxend += 1
            if list_parg_idxend == argcnt:
                break # XXX
        list_parg = list_parg_idxend - (idx + 1)
        parg_score = 0
        parg_score_idx = 1 # skip ourself
        while len (positional_parameters_list) > parg_score_idx:
            argname, arg = positional_parameters_list [parg_score_idx]
            if arg ['nargs'] in [0, '+']:
                parg_score_idx += 1
            elif int == type (arg ['nargs']):
                parg_score_idx += arg ['nargs']
            elif arg ['nargs'] in ['*', '?']: # optionals
                pass
            parg_score_idx += 1
            continue
        # if list_parg < parg_score, this optional positional parameter is
        # skipped
        if list_parg < parg_score:
            # consume this positional parameter
            del (positional_parameters_list [0])
        else:
            # scan next positional parameter
            idx += 1
        # scan next positional parameter
        return parse_positional (argv, idx, text,
                                 optional_parameters_list,
                                 positional_parameters_list, processed + 1)
    # '+' means 1+ arguments following (we ignore how many argument follows)
    elif '+' == arg ['nargs']:
        # NOTE1: if value match "--", skip to next (either next positional
        # if any remaining, or optional, if not already parsed.
        # Otherwise all parameters are consumed are we indicates it.)
        # NOTE2: if a value match an optional_parameters_list
        # stop storing and start fetching optional, mark positional as
        # parsed. Except if all positional weren't consumed we indicate
        # the next missing positional.
        # NOTE3: if we reach end of arguments we are arg [argcnt - idx+off]
        idx_offset = 1
        if argcnt == idx + idx_offset:
            return (argname, idx_offset - 1) # NOTE3
        while "--" != argv [idx + idx_offset] and \
                not optional_parameters_list.has_key (argv [idx + idx_offset]):
            idx_offset += 1
            if argcnt == idx + idx_offset:
                return (argname, idx_offset - 1) # NOTE3
        if "--" == argv [idx + idx_offset]: # NOTE1
            # consume this positional parameter
            del (positional_parameters_list [0])
            # if there is no more positional parameters, parse optional
            if not len (positional_parameters_list):
                # mark positional parameters as parsed, parse optional
                positional_parsed = True
                return parse_optional (argv, idx, text,
                                       optional_parameters_list,
                                       positional_parameters_list,
                                       positional_parsed)
            # else scan next positional
            idx += idx_offset + 1
            return parse_positional (argv, idx, text,
                                     optional_parameters_list,
                                     positional_parameters_list, processed + 1)
        # else if next argument matchs an optional parameter (NOTE2)
        if argv [idx + idx_offset] not in optional_parameters_list:
            print "logical bug"
        # consume this positional parameter
        del (positional_parameters_list [0])
        idx += idx_offset
        # if positional parameters left, indicate it
        # (no positional parameters can follow X argument with X unknown list)
        if len (positional_parameters_list):
            # Not all positional were consumed, indicate missing
            return {'missing': positional_parameters_list.keys ()}
        # mark positional parameters as parsed, parse optional
        positional_parsed = True
        return parse_positional (argv, idx, text,
                                 optional_parameters_list,
                                 positional_parameters_list, processed + 1)
    # N means N's argument following (N is a positive)
    elif int == type (arg ['nargs']):
        # if there is not enough argument for this parameters, indicate it
        if idx + arg ['nargs'] > argcnt:
            # indicate at which offset in N in arg's parameter we are
            return (argname, idx + arg ['nargs'] - argcnt)
        # else consume this positional parameter and its N's argument
        del (positional_parameters_list [0])
        # scan next positional parameter (skip N arguments)
        idx += arg ['nargs']
        return parse_positional (argv, idx, text,
                                 optional_parameters_list,
                                 positional_parameters_list, processed + 1)
    # '*' means 0+ (optional) argument following, we ignore how many and if any
    elif '*' == arg ['nargs']:
        raise NotImplemented
    # ERROR
    print "ERROR positional"
    return None

def parse_optional (argv, idx, text,
                    optional_parameters_list,
                    positional_parameters_list,
                    positional_parsed):
    # XXX
    # optional_nargs = {'?': optional_nargs_optional0,
    #                   '*': optional_nargs_optional1,
    #                   '+': optional_nargs_infine,
    #                   1: optional_nargs_one,
    #                   0: optional_nargs_zero,
    #                   'default': optional_nargs_integer}
    argcnt = len (argv)
    if idx == argcnt:
        if not positional_parsed:
            return parse_positional (argv, idx, text,
                                     optional_parameters_list,
                                     positional_parameters_list)
        return optional_parameters_list.keys () or True
    # if no optional parameter left, parse positional parameters
    if not len (optional_parameters_list):
        return parse_positional (argv, idx, text,
                                 optional_parameters_list,
                                 positional_parameters_list)
    # if next argument is not an optional parameter
    if not optional_parameters_list.has_key (argv [idx]):
        # .. then parse positional if not parsed
        if not positional_parsed:
            return parse_positional (argv, idx, text,
                                     optional_parameters_list,
                                     positional_parameters_list)
        # if we are the at end
        if (idx + 1) == argcnt:
            return optional_parameters_list.keys ()
        # otherwise it's an error, indicate it
        return {'invalid': argv [idx]}
    # fetch this optional parameter
    argname = argv [idx]
    arg = optional_parameters_list [argname]
    # if it has zero argument
    if 0 == arg ['nargs']:
        #if not arg.multiple:
        # consume this optional parameter (and possible duplicate)
        for arg in optional_parameters_list [argname]['duplicate']:
            if arg != argname:
                del (optional_parameters_list [arg])
        del (optional_parameters_list [argname])
        # scan next optional parameter
        idx += 1
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    # if it has 1 argument
    if 1 == arg ['nargs']:
        # if there isn't enough space for the parameter, indicate we are
        # parsing this optional argument
        if argcnt < idx + 1:
            return (argname, 0)
        # or if the next parameter is the last one, indicate we are parsing it
        elif argcnt == idx + 1:
            return (argname, 1)
        # or if this parameter is the next one (text)
        elif argcnt == idx + 2 and text:
            return (argname, 1)
        # consume this optional parameter
        for arg in optional_parameters_list [argname]['duplicate']:
            if arg != argname:
                del (optional_parameters_list [arg])
        del (optional_parameters_list [argname])
        # skip this parameter's argument, scan next optional parameter
        idx += 2
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    # '?' means O or 1 (it is optional)
    elif '?' == arg ['nargs']:
        # NOTE:
        # We differ from argparse's parser because we don't want to do
        # completion on optional parameter (would stuck the whole line) when
        # there is the possibility it is not provided. That means if it is
        # possible that next argument is a positional, where argparse considers
        # it is the positional's parameter, we take it for the positional. --
        # if next matchs an optional parameter, the optional parameter is
        # not set.
        if optional_parameters_list.has_key (argv [idx + 1]):
            # consume this optional parameter
            for arg in optional_parameters_list [argname]['duplicate']:
                if arg != argname:
                    del (optional_parameters_list [arg])
            del (optional_parameters_list [argname])
            # scan next optional parameter
            idx += 1
            return parse_optional (argv, idx, text,
                                   optional_parameters_list,
                                   positional_parameters_list,
                                   positional_parsed)
        # else if next is '--', we are over with this optional parameter
        elif "--" == argv [idx + 1]:
            # consume this optional parameter
            for arg in optional_parameters_list [argname]['duplicate']:
                if arg != argname:
                    del (optional_parameters_list [arg])
            del (optional_parameters_list [argname])
            # skip this parameter's argument, scan next optional parameter
            idx += 2
            return parse_optional (argv, idx, text,
                                   positional_parameters_list,
                                   positional_parsed)
        # else if parameter's argument is at the end
        # [1] take it for a positional if any remains or
        # [2] we are parsing its argument
        elif argcnt == idx + 1:
            if positional_parsed:
                return (argname, 0) # [2]
            # [1]
            # consume this optional parameter
            for arg in optional_parameters_list [argname]['duplicate']:
                if arg != argname:
                    del (optional_parameters_list [arg])
            del (optional_parameters_list [argname])
            # scan next optional parameter
            idx += 1
            return parse_positional (argv, idx, text,
                                     optional_parameters_list,
                                     positional_parameters_list)
        # else if we are at the end
        elif argcnt == idx:
            # we migth be in optional argument of "arg" but consider we are 
            # in first positional if not parsed (give priority on positional)
            if positional_parsed:
                return (argname, 0)
            return parse_positional (argv, idx, text,
                                     optional_parameters_list,
                                     positional_parameters_list)
        # else if we have enough arguments we process it
        # skip this parameter's argument, scan next optional parameter
        idx += 2
        for arg in optional_parameters_list [argname]['duplicate']:
            if arg != argname:
                del (optional_parameters_list [arg])
        del (optional_parameters_list [argname])
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    # '+' means 1+ arguments following (we ignore how many argument follows)
    elif '+' == arg ['nargs']:
        # consume every argument until we find a new optional or the '--'
        # separator (argparse will not considere any argument as possible
        # optionals remaining, we behave the same).
        orig_idx = idx
        idx += 1
        if argcnt == idx:
            return (argname, 1)
        while "--" != argv [idx] and \
                not optional_parameters_list.has_key (argv [idx]):
            idx += 1
            # if we reach the end tell which N-argument it is to this arg
            # completion
            if argcnt == idx:
                return (argname, argcnt - orig_idx)
        # if we found a separator, skip it
        if "--" == argv [idx]:
            idx += 1
        # consume this optional parameter
        for arg in optional_parameters_list [argname]['duplicate']:
            if arg != argname:
                del (optional_parameters_list [arg])
        del (optional_parameters_list [argname])
        # scan next optional
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    # N means N's argument following (N is a positive)
    elif int == type (arg ['nargs']):
        # skip this parameter
        idx += 1
        # if we can't skip N's argument
        if not argcnt >= (idx + arg ['nargs']):
            if argcnt == idx + arg ['nargs']:
                # return completion for the last N argument
                return (argname, argcnt - idx + 1)
        # skip N argument, scan next optional parameter
        idx += arg ['nargs']
        # consume this optional parameter
        for arg in optional_parameters_list [argname]['duplicate']:
            if arg != argname:
                del (optional_parameters_list [arg])
        del (optional_parameters_list [argname])
        return parse_optional (argv, idx, text,
                               optional_parameters_list,
                               positional_parameters_list,
                               positional_parsed)
    elif '*' == arg ['nargs']:
        raise NotImplemented
    # ERROR
    print "nargs = '%s'"%arg ['nargs']
    print "ERROR optional"
    return None

def parse_completion (cmdline, command_list, text):
    argv = cmdline.split ()
    cmd = argv [0]
    if not command_list.has_key (cmd):
        return command_list.keys ()
    parameters = command_list [cmd]['parser'].completion_get ()
    optional_parameters_list = odict ()
    positional_parameters_list = odict ()
    for _k, value in parameters.iteritems ():
        if parameters [_k]['positional']:
            positional_parameters_list [_k] = value
        else:
            optional_parameters_list [_k] = value
            for _param in ['-h', '--help']:
                if optional_parameters_list.has_key (_param):
                    del (optional_parameters_list [_param])
    positional_parsed = False
    _r = parse_optional (argv [1:], 0, text,
                         optional_parameters_list,
                         positional_parameters_list,
                         positional_parsed)
    return _r

def add_argument (self, *args, **kwargs):
    # completion algorithm on argument's parameters depend from previous
    # occurence of an argument (backward parsing).
    # Argument shall have more than one parameter, indicated by "nargs",
    positional = 1 == len (args) and args [0][0] not in self.prefix_chars
    n_args = 1 if not positional else 0
    if kwargs.has_key ('nargs'):
        n_args = kwargs ['nargs']
    # Argument have no parameter if specified with "action"'s value
    multiple = False
    if kwargs.has_key ('action'):
        if kwargs ['action'] in ['store_const', 'store_true',
                                 'store_false', 'version',
                                 'append_const']:
            n_args = 0
        if kwargs ['action'] == 'count':
            multiple = True # This option can appears more than one
            n_args = 0
    n_completion = None
    if kwargs.has_key ('completion'):
        # must be a list or a function returning a list
        n_completion = kwargs ['completion']
        # delete our custom parameter now
        del (kwargs ['completion'])
    n_help = None if not kwargs.has_key ('help') else kwargs ['help']
    self.__completion_register (args, n_completion, n_args, positional, 
                                n_help, multiple)
    return self.orig_add_argument (*args, **kwargs)

def __completion_register (self, args, n_completion, n_args, positional,
                           n_help, multiple):
    obj = { 'completion'     : n_completion,
            'argcnt'         : n_args,
            'positional'     : positional,
            'help'           : n_help,
            'nargs'          : n_args,
            'multiple'       : multiple }
    if not positional:
        obj ['duplicate'] = args if len (args) > 1 else []
    for arg in args:
        self.completion_cache [arg] = obj
    return True

# monkey patching : work on subparser / exclusive group aswell
setattr (argparse._ActionsContainer,
         'orig_add_argument',
         argparse._ActionsContainer.add_argument)
setattr (argparse._ActionsContainer,
         'add_argument', add_argument)
setattr (argparse._MutuallyExclusiveGroup,
         '__completion_register', __completion_register)
setattr (argparse.ArgumentParser,
         '__completion_register', __completion_register)

# use CompletionArgumentParser instead of ArgumentParser
class CompletionArgumentParser (argparse.ArgumentParser):
    def __init__ (self, *args, **kwargs):
        # ordered dictionnary
        self.completion_cache = odict ()
        # handle "parent"'s members
        if kwargs.has_key ('parents'):
            for parent in kwargs ['parents']:
                if isinstance (parent, CompletionArgumentParser):
                    _cc = parent.completion_get ()
                    if _cc:
                        # merge parent's arguments
                        self.completion_cache.update (_cc)
                else:
                    raise ValueError (
                        "parent is not of type %s"%self.__class__.__name__)
        return super (
            CompletionArgumentParser, self).__init__ (*args, **kwargs)

    def parse_args (self, args=None, namespace=None, raiseonfault=False):
        # fix for exit on error, return either None or an exception
        try:
            return super (CompletionArgumentParser,
                          self).parse_args (args, namespace)
        except SystemExit:
            if raiseonfault:
                raise ValueError (
                    "%s: Invalid argument"%self.prog)
            return None

    def completion_get (self):
        return self.completion_cache

    # handle groups (mutually exclusive group)
    def add_mutually_exclusive_group (self, **kwargs):
        _r = super (CompletionArgumentParser,
                    self).add_mutually_exclusive_group (**kwargs)
        if _r:
            setattr (_r,
                     'completion_cache', self.completion_cache)
        return _r

if '__main__' == __name__:
    # command2 (with parent)
    parent_parser = CompletionArgumentParser (
        add_help=False)
    parent_parser.add_argument('parent',
                               completion = "help completion")
    foo_parser = CompletionArgumentParser ('command2', parents=[parent_parser])
    foo_parser.add_argument('bar', nargs='*', help="pass a foo to this bar")
    foo_parser.add_argument ('--foo', '-f', help="foo indicates param",
                             completion = ["foo1", "foo2", "valuefoo"])
    foo_parser.add_argument ('--doe', '-d', help="doe indicates param",
                             completion = ["bar"])
    group = foo_parser.add_mutually_exclusive_group ()
    group.add_argument ('--current', help = "Make PROFILE the current profile",
                        action = 'store_true')
    group.add_argument ('--info', help = "Provide informations",
                         action = 'store_true')
    group.add_argument ('--show-log', help = "Output profile's log",
                        action = 'store_true')
    #
    # NOTE : the positional argument can be anywhere until they are following
    # each others, in this example 'parent' then 'bar'
    #r = foo_parser.parse_args (['--doe', 'mydoe', 'parentvalue',
    #                            'barvalue1', '--foo', 'foovalue'])
    #r = foo_parser.parse_args (['parentvalue', 'barvalue1', 'barvalue2', '--doe', 'mydoe', '--foo', 'foovalue'])
    #r = foo_parser.parse_args (['--doe', 'mydoe', '--foo', 'foovalue',
    #                            'parentvalue', 'bar1', 'bar2'])
    #r = foo_parser.parse_args ( # Invalid -- positional argument not following
    #    ['--doe', 'mydoe', 'parentvalue', '--foo', 'foovalue',
    #     'bar1value', 'bar2value']) 
    #
    r = foo_parser.parse_args (['parentvalue', 'barvalue1', 'barvalue2', '--doe', 'mydoe', '--foo', 'foovalue', '--info'])
    if r:
        print vars (r)
    #foo_parser.completion_get ()
    # REGISTER COMMAND
    command_list = {}
    mycmd = 'mycommand'
    foo_parser = CompletionArgumentParser (mycmd)
    foo_parser.add_argument('test')
    foo_parser.add_argument ('fox')
    foo_parser.add_argument ('foxy')
    foo_parser.add_argument ('--oo')
    foo_parser.add_argument ('--omp')
    command_list [mycmd] = {}
    command_list [mycmd]['parser'] = foo_parser
    # cmdline = "mycommand --oo ooisgreat testval foxval foxyval -- foxy -"
    cmdline = "mycommand --oo ooisgreat testval foxval foxyval -"
    print parse_completion (cmdline, command_list, False)

