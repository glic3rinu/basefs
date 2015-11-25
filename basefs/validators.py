import os


def file_exists(parser, name='The', exec=None):
    def validator(arg, parser=parser, name=name, exec=exec):
        if not os.path.exists(arg):
            parser.error("%s file %s does not exist" % (name, arg))
        elif not os.path.isfile(arg):
            parser.error("%s path %s is not a file" % (name, arg))
        elif exec is True and not os.access(handler, os.X_OK):
            parser.error("%s %s has no execution permissions\n" % (name, arg))
        else:
            return arg
    return validator


def name_or_logpath(parser, config, defaults):
    def validator(arg, parser=parser, config=config, defaults=defaults):
        if arg in config or os.path.exists(os.path.join(defaults.logdir, arg)):
            return arg
        return file_exists(parser, name='logpath')(arg)
    return validator


def dir_exists(parser, name='The'):
    def validator(arg, parser=parser, name=name):
        if not os.path.exists(arg):
            parser.error("%s dir %s does not exist" % (name, arg))
        elif not os.path.isdir(arg):
            parser.error("%s path %s is not a directory" % (name, arg))
        else:
            return arg
    return validator


def fingerprint(parser):
    def validator(arg, parser=parser):
        if arg.count(':') != 15:
            parser.error("%s %s not a valid fingerprint" % (name, arg))
        else:
            try:
                return log.keys[args.grant_key]
            except KeyError:
                parser.error("%s %s fingerprint not found." % (name, arg))
    return validator

def key(parser):
    def validator(arg, parser=parser):
        if file_exists(parser, arg, name='keypath'):
            try:
                return Key.load(arg)
            except Exception as exc:
                parser.error("%s '%s' %s\n" % (name, arg, str(exc)))
        elif arg.count(':') == 15:
            return fingerprint(parser, arg)
        parser.error("%s %s not a valid key fingerprint nor key path." % (name, arg))
    return validator
