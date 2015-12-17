import argparse

from basefs import validators

from . import run


parser = argparse.ArgumentParser(
    description='Mount an existing filesystem',
    prog='basefs mount')


def command():
    # mount <name/logpath> <mountpoint> [-b <ip>[:<port>]] [-i <ip>[:<port>]] [-l <logpath>] [-k <keypath/keyname>] [-H <hostname>] [-d]
    run.set_parser(parser)
    parser.add_argument('mountpoint',
        type=validators.dir_exists(parser, name='mountpoint'))
    run.command(mount=True, arg_parser=parser)
