# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import json
import time, datetime
import tempfile, os, posix
import threading
import collections
import base64, hashlib

import asyncio

from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory

from twisted.python import log
from twisted.internet import reactor

from common.service import Service
from terminal.terminal import Terminal

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from config import utils

import logging
logger = logging.getLogger('siis.monitor')


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
        self._monitoring_config = utils.monitoring(options.get('config-path')) or {}

        if options.get('monitored', True):
            self._monitoring = True
        else:
            self._monitoring = False

        self._content = collections.deque()

        self._fifo = -1
        self._fifo_read = None

        self._thread = None
        self._running = False

        self._server = None
        self._loop = None

        # host, port, allowed host, order, deny... from config
        self._mode = MonitorService.MODE_FIFO  # MODE_HTTP_WEBSOCKET

        self._host = self._monitoring_config.get('host', '127.0.0.1')
        self._port = self._monitoring_config.get('port', '8080')

        # @todo allowdeny...

    def start(self):
        if self._monitoring:
            if self._mode == MonitorService.MODE_FIFO:
                self._tmpdir = tempfile.mkdtemp()
                self._filename = os.path.join(self._tmpdir, 'siis.stream')

                Terminal.inst().info("- Open a monitoring FIFO at %s" % self._filename)

                try:
                    os.mkfifo(self._filename, 0o600)
                except OSError as e:
                    logger.error("Failed to create monitor FIFO: %s" % repr(e))
                    os.rmdir(self._tmpdir)
                else:
                    # self._fifo = posix.open(self._filename, posix.O_NONBLOCK + posix.O_WRONLY)
                    self._fifo = posix.open(self._filename, posix.O_RDWR + posix.O_NONBLOCK)

                if self._fifo:
                    self._running = True
                    self._thread = threading.Thread(name="monitor", target=self.run_fifo)
                    self._thread.start()

            elif self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
                # log.startLogging(sys.stdout)

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
            if self._fifo > 0:
                try:
                    posix.close(self._fifo)
                    self._fifo = -1
                except (BrokenPipeError, IOError):
                    pass

                os.remove(self._filename)
                os.rmdir(self._tmpdir)

            if self._thread:
                try:
                    self._thread.join()
                except:
                    pass

                self._thread = None

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
        while self._running:
            buf = []*8192

            if self._fifo > 0 and self._monitoring:
                try:
                    buf = posix.read(self._fifo, len(buf))
                except (BrokenPipeError, IOError):
                    pass    

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
                    logger.error("Monitor error sending message : %s" % repr(c))

                count += 1
                if count > 10:
                    break

            # don't waste the CPU
            time.sleep(0)  # yield 0.001)

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
