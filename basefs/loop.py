import asyncio
import logging
import traceback
import threading

from . import sync, commands


logger = logging.getLogger('basefs.loop')


def run(view, serf, port, config=None):
    handlers = {
        b's': sync.SyncHandler(view, serf),
        b'c': commands.CommandHandler(view, serf),
        b'e': serf,
        b'b': serf,
    }
    
    @asyncio.coroutine
    def handle_connection(reader, writer, handlers=handlers):
        token = yield from reader.read(1)
        peername = writer.get_extra_info('peername')
        try:
            handler = handlers[token]
        except KeyError:
            data = yield from reader.read(100)
            logger.debug("Unknown token from %s: %s, data: %s", peername, token, data)
            writer.close()
        else:
            logger.debug('Reciving %s from %s', getattr(handler, 'description', handler), peername)
            try:
                yield from handler.data_received(reader, writer, token)
            except Exception as exc:
                logger.error(traceback.format_exc())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    coro = asyncio.start_server(handle_connection, '0.0.0.0', port, loop=loop)
    server = loop.run_until_complete(coro)
    asyncio.async(sync.do_full_sync(handlers[b's'], config=config))
    try:
        logger.debug("Event loop running on port %i", port)
        loop.run_forever()
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()


def run_thread(view, serf, port, config=None):
    handler = threading.Thread(target=run, args=(view, serf, port), kwargs={'config': config}, daemon=True)
    handler.start()
