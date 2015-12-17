import configparser
import hashlib
import os
import pwd
import socket
import uuid

from basefs import utils


basefs_dir = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, '.basefs')
defaults = utils.AttrDict(**{
    'dir': basefs_dir,
    'config': os.path.join(basefs_dir, 'config.ini'),
    'keypath': os.path.join(basefs_dir, 'id_ec'),
    'logdir': os.path.join(basefs_dir, 'logs'),
    'hostname': "%s-%s" % (str(uuid.uuid1()).split('-')[-1], socket.gethostname()),
})


# TODO inspect directory before configuration
def get_or_create_config(defaults):
    config = configparser.ConfigParser()
    def save(config=config, defaults=defaults):
        with open(defaults.config, 'w') as configfile:
           config.write(configfile)
    config.save = save
    if not os.path.exists(defaults.config):
        config_dir = os.path.dirname(defaults.config)
        if not os.path.exists(config_dir):
            os.mkdir(config_dir)
        config['DEFAULT'] = {
            '; block_receiving_buffer': 4096,
            '; block_receiving_timeout': 10,
            '; full_sync_interval': 30,
            '; max_block_messages': 15,
            'hostname': defaults.hostname,
        }
        config.save()
    else:
        config.read(defaults.config)
    return config


def get_port(name):
    return 10000 + int(hashlib.md5(name.encode()).hexdigest(), 16) % (10**4)
