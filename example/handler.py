#!/usr/bin/python3

# CREATES, UPDATES, RESTARTS and DELETES VMs

import os
import json
import subprocess

# vms = {
#     'debian-test-vm01': {  # VM name
#         'type': 'debian',  # VM tyme (debian, ubuntu)
#         'memory': 512,     # Memory limit in MB
#         'disk': 10,        # Disk space in GB
#         'sequence': 0      # Sequence number, used for restarting VMs
#    }
# }


PATH = '/vms.list'


### UTILS

def read_conf(PATH):
    with open(PATH, 'r') as handler:
        return json.loads(handler.read())


def get_sequene(vm):
    try:
        with open('/tmp/%(name)s.squence' % vm, 'r') as handler:
            return int(handler.read().strip())
    except IOError:
        return None

def update_sequence(vm):
    with open('/tmp/%(name)s.squence' % vm, 'w') as handler:
        return handler.write(str(vm['sequence']))


### METHODS

def save_vms(PATH):
    vms = read_conf(PATH)['vms']
    existing = []
    for name, options in vms.items():
        vm = dict(options)
        vm['name'] = name
        os.system("lxc-create -n %(name)s -t %(type)s -B lvm -n u1 --fssize %(disk)G" % vm)
        os.system("lxc-cgroup -n %(name)s memory.soft_limit_in_megabytes %(memory)s" % vm)
        # Restart if needed
        sequence = read_sequence(vm)
        if sequence is None:
            update_sequence(vm)
        elif sequence > vm['sequence']:
            os.system("lxc-restart -n %(name)s" % vm)
            update_sequence(vm)
        existing.append(name)
    delete_vms(existing=existing)


def delete_vms(existing=None):
    vms = subprocess.Popen("lxc-ls", stdout=subprocess.PIPE)
    for name in vms.stdout.readlines():
        name = name.strip()
        if not existing or name not in existing:
            os.system("lxc-destroy -n %s" % name)


### MAIN

if __name__ == '__main__':
    if os.environ['BASEFS_EVENT_PATH'] == PATH:
        if os.environ['BASEFS_EVENT_TYPE'] == 'write':
            save_vms(PATH)
        elif os.environ['BASEFS_EVENT_TYPE'] == 'delete':
            delete_vms()
