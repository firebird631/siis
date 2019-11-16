# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import json
import time, datetime
import tempfile, os, posix
import threading
import traceback
import collections
import base64, hashlib

import asyncio

from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory

from twisted.python import log
from twisted.internet import reactor

from common.service import Service

from monitor.streamable import Streamable
from monitor.rpc import Rpc

from strategy.strategy import Strategy

from config import utils

import logging
logger = logging.getLogger('siis.monitor')
error_logger = logging.getLogger('siis.error.monitor')
traceback_logger = logging.getLogger('siis.traceback.monitor')


class ServerProtocol(WebSocketServerProtocol):

    def onConnect(self, request):
        logger.debug("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        logger.debug("WebSocket connection open")

    def onMessage(self, payload, isBinary):
        if isBinary:
            logger.info("Binary message received: {0} bytes".format(len(payload)))
        else:
            logger.info("Text message received: {0}".format(payload.decode('utf8')))

        # echo back message verbatim
        self.sendMessage(payload, isBinary)

    def onClose(self, wasClean, code, reason):
        logger.debug("WebSocket connection closed: {0}".format(reason))


class MonitorService(Service):
    """
    Monitoring web service.
    @todo REST HTTP(S) server + WS server.
    @todo receive REST external commands
    @todo streaming throught WS server + streaming API for any sort of data
    @todo streaming of the state and any signals that can be monitored + charting and appliances data
    """

    MODE_FIFO = 0
    MODE_HTTP_WEBSOCKET = 1

    def __init__(self, options):
        super().__init__("monitor", options)

        # monitoring config
        self._monitoring_config = utils.load_config(options, 'monitoring')

        if options.get('monitored', True):
            self._monitoring = True
        else:
            self._monitoring = False

        self._content = collections.deque()

        self._thread = None
        self._running = False

        self._strategy_service = None
        self._trader_service = None
        self._watcher_service = None

        self._server = None
        self._loop = None

        # host, port, allowed host, order, deny... from config
        self._mode = MonitorService.MODE_FIFO  # MODE_HTTP_WEBSOCKET

        self._host = self._monitoring_config.get('host', '127.0.0.1')
        self._port = self._monitoring_config.get('port', '8080')

        # @todo allowdeny...

        # fifo
        self._tmpdir = None
        self._filename_read = None
        self._filename = None
        self._fifo = -1
        self._fifo_read = None

    def url(self):
        if self._mode == MonitorService.MODE_FIFO:
            return (self._filename, self._filename_read)
        elif self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
            return ("ws://%s:%i" % (self._host, self._port), "ws://%s:%i" % (self._host, self._port))

        return ("", "")

    def setup(self, watcher_service, trader_service, strategy_service):
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._strategy_service = strategy_service

    def start(self):
        if self._monitoring:
            if self._mode == MonitorService.MODE_FIFO:
                # publish fifo
                self._tmpdir = tempfile.mkdtemp()
                self._filename = os.path.join(self._tmpdir, 'siis.stream')

                try:
                    os.mkfifo(self._filename, 0o600)
                except OSError as e:
                    error_logger.error("Failed to create monitor write FIFO: %s" % repr(e))
                    os.rmdir(self._tmpdir)
                    self._filename = None
                else:
                    self._fifo = posix.open(self._filename, posix.O_NONBLOCK | posix.O_RDWR)  # posix.O_WRONLY

                # read command fifo
                self._filename_read = os.path.join(self._tmpdir, 'siis.rpc')

                try:
                    os.mkfifo(self._filename_read, 0o600)
                except OSError as e:
                    error_logger.error("Failed to create monitor read FIFO: %s" % repr(e))
                    os.rmdir(self._tmpdir)

                    # close the write fifo
                    os.remove(self._filename)
                    posix.close(self._fifo)
                    self._fifo = -1
                    self._filename = None
                    self._filename_read = None
                else:
                    self._fifo_read = posix.open(self._filename_read, posix.O_NONBLOCK)

                if self._fifo and self._fifo_read:
                    self._running = True
                    self._thread = threading.Thread(name="monitor", target=self.run_fifo)
                    self._thread.start()

            elif self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
                # logger.startLogging(sys.stdout)

                self._factory = WebSocketServerFactory(u"ws://%s:%i" % (self._host, self._port))
                self._factory.protocol = ServerProtocol
                # self._factory.setProtocolOptions(maxConnections=2)

                # self._loop = asyncio.get_event_loop()
                # coro = self._loop.create_server(self._factory, self._host, self._port)
                # self._server = self._loop.run_until_complete(coro)

                # reactor.listenTCP(self._port, self._factory)
                # if not reactor.running:
                #     reactor.run()

                self._running = True
                self._thread = threading.Thread(name="monitor", target=self.run_autobahn)
                self._thread.start()

    def terminate(self):
        # remove any streamables
        self._running = False

        if self._mode == MonitorService.MODE_FIFO:
            if self._thread:
                try:
                    self._thread.join()
                except:
                    pass

                self._thread = None

            if self._fifo_read:
                try:
                    posix.close(self._fifo_read)
                    self._fifo_read = -1
                except (BrokenPipeError, IOError):
                    pass

                if self._filename_read:
                    os.remove(self._filename_read)
                    self._filename_read = None

            if self._fifo:
                try:
                    posix.close(self._fifo)
                    self._fifo = -1
                except (BrokenPipeError, IOError):
                    pass

                if self._filename:
                    os.remove(self._filename)
                    self._filename = None

            if self._tmpdir:
                os.rmdir(self._tmpdir)
                self._tmpdir = None

        elif self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
            if self._loop:
                self._loop.stop()

            if self._thread:
                try:
                    self._thread.join()
                except:
                    pass

                self._thread = None

            if self._server:
                self._server.close()
                self._loop.close()

            self._server = None
            self._loop = None

    def run_fifo(self):
        size = 32768
        cur = bytearray()

        while self._running:
            if self._fifo > 0 and self._fifo_read and self._monitoring:
                # receive
                try:
                    # buf = posix.read(self._fifo, len(buf))
                    # buf = os.read(self._fifo, size)
                    buf = os.read(self._fifo_read, size)

                    if buf:
                        for n in buf:
                            if n == 10:  # new line as message termination
                                try:
                                    msg = json.loads(cur.decode('utf8'))
                                    self.on_rpc_message(msg)

                                except Exception as e:
                                    error_logger.error(repr(e))
                                    traceback_logger.error(traceback.format_exc())

                                cur = bytearray()
                            else:
                                cur.append(n)

                except (BrokenPipeError, IOError):
                    pass

                # publish
                count = 0

                while self._content:
                    c = self._content.popleft()

                    # insert category, group and stream name
                    c[3]['c'] = c[0]
                    c[3]['g'] = c[1]
                    c[3]['s'] = c[2]

                    try:
                        # write to fifo
                        posix.write(self._fifo, (json.dumps(c[3]) + '\n').encode('utf8'))
                    except (BrokenPipeError, IOError):
                        pass
                    except (TypeError, ValueError) as e:
                        error_logger.error("Monitor error sending message : %s" % repr(c))
                        traceback_logger.error(traceback.format_exc())

                    count += 1
                    if count > 10:
                        break

            # don't waste the CPU
            time.sleep(0.0001)  # yield 0.001)

    def run_autobahn(self):
        # async def push(self):
        #     count = 0

        #     while self._content:
        #         c = self._content.popleft()

        #         # insert category, group and stream name
        #         c[3]['c'] = c[0]
        #         c[3]['g'] = c[1]
        #         c[3]['s'] = c[2]

        #         # write to fifo
        #         await websocket.send((json.dumps(c[3]) + '\n').encode('utf8'))
        #         # posix.write(self._fifo, (json.dumps(c[3]) + '\n').encode('utf8'))

        #         count += 1
        #         if count > 10:
        #             break
        pass

    def command(self, command_type, data):
        pass

    def push(self, stream_category, stream_group, stream_name, content):
        if self._running:
            self._content.append((stream_category, stream_group, stream_name, content))

    def on_rpc_message(self, msg):
        # retrieve the appliance
        # @todo using Rpc model and update on the client side
        # rpc = Rpc()
        # rpc.loads(msg)

        cat = msg.get('c', -1)

        if cat == Streamable.STREAM_STRATEGY_CHART:
            appliance = msg.get('g')
            market_id = msg.get('s')
            timeframe = msg.get('v')

            if appliance and market_id:
                self._strategy_service.command(Strategy.COMMAND_TRADER_STREAM, {
                    'appliance': appliance,
                    'market-id': market_id,
                    'timeframe': timeframe,
                    'type': "chart",
                    'action': "unsubscribe"
                })

        elif cat == Streamable.STREAM_STRATEGY_INFO:
            appliance = msg.get('g')
            market_id = msg.get('s')
            timeframe = msg.get('v')
            # sub_key = msg.get('v')[1]

            if appliance and market_id:
                self._strategy_service.command(Strategy.COMMAND_TRADER_STREAM, {
                    'appliance': appliance,
                    'market-id': market_id,
                    'timeframe': None,
                    'subscriber-key': "",  # @todo
                    'type': "info",
                    'action': "unsubscribe"
                })
