import asyncio

from . import sync, commands


class BasefsProtocol(asyncio.Protocol):
    def __init__(self, handlers, client=False):
        self.handlers = handlers
        self.client = client
        super().__init__()
    
    def connection_made(self, transport):
        """
        Called when a connection is made.
        The argument is the transport representing the pipe connection.
        To receive data, wait for data_received() calls.
        When the connection is closed, connection_lost() is called.
        """
        self.transport = transport
        if self.client:
            request = self.handlers[self.client].initial_request()
            self.transport.write(request)
    
    def data_received(self, data):
        """
        Called when some data is received.
        The argument is a bytes object.
        """
        try:
            handler = self.handlers[data[0]]
        except KeyError:
            print('UNKNOWN TOKEN', data[0])
        else:
            handler.data_received(self.transport, data)


def run(view, serf, port):
    handlers = {
        ord('s'): sync.SyncHandler(view, serf),
        ord('c'): commands.CommandHandler(view),
        ord('e'): serf,
        ord('b'): serf,
    }
    server_factory = lambda: BasefsProtocol(handlers)
    client_factory = lambda: BasefsProtocol(handlers, client=ord('s'))
    
    full_sync = sync.do_full_sync(client_factory, serf)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = loop.run_until_complete(loop.create_server(server_factory, '0.0.0.0', port))
    asyncio.async(full_sync)
    try:
        loop.run_until_complete(server.wait_closed())
    finally:
        loop.close()
