class CommandHandler:
    def __init__(self, view):
        self.view = view
    
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
    
    def data_received(self, transport, data):
        peername = transport.get_extra_info('peername')
        if peername[0] != '127.0.0.1':
            response = b"%s not authorized address\n" % peername[0]
        else:
            cmd = data.split()[1]
            try:
                method = getattr(self, cmd.lower())
            except AttributeError:
                response = b"%s command not found\n" % cmd
            else:
                response = method(data)
        transport.write(response)
        transport.close()
