import json


def dumper(obj):
    try:
        return obj.toJSON()
    except:
        return str(obj)


class CommandHandler:
    def __init__(self, view, serf):
        self.view = view
        self.serf = serf
    
    def log(self, data):
        log = self.view.log
        data = data.split()
        path, color, ascii = data[2:]
        color = int(color)
        ascii = int(ascii)
        return log.print_tree(view=self.view, color=color, ascii=ascii).encode()
    
    def grant(self, data):
        pass
    
    def revoke(self, data):
        pass
    
    def revert(self, data):
        pass
    
    def blockstate(self, data):
        return json.dumps({
            'buffer': {k: ' '.join((v.hash, str(v.next))) for k, v in self.serf.blockstate.buffer.items()},
            'incomlete': self.serf.blockstate.incomplete,
            'receiving': self.serf.blockstate.receiving,
        }, indent=4, default=dumper)
    
    def members(self, data):
        results = []
        max_name, max_addr = 0, 0
        for member in self.serf.members().body[b'Members']:
            name = member[b'Name']
            addr = member[b'Addr']+b':'+str(member[b'Port']).encode()
            max_name = max(max_name, len(name))
            max_addr = max(max_addr, len(addr))
            results.append([name, addr, member[b'Status']])
        ret = []
        name_tabs = int((max_name+4)/8)
        addr_tabs = int((max_addr+4)/8)
        for name, addr, status in results:
            ret.append(''.join((
                name.decode(), '\t'*(name_tabs - int(len(name)/8)+1),
                addr.decode(), '\t'*(addr_tabs - int(len(addr)/8)+1),
                status.decode()
            )))
        return '\n'.join(ret)
    
    def data_received(self, reader, writer, token):
        peername = writer.get_extra_info('peername')
        if peername[0] != '127.0.0.1':
            response = b"%s not authorized address\n" % peername[0]
        else:
            data = yield from reader.read(4096)
            cmd = data.split()[0].decode()
            try:
                method = getattr(self, cmd.lower())
            except AttributeError:
                response = cmd.encode()+ b" command not found\n"
            else:
                response = method(data).encode()
        writer.write(response)
        writer.close()
