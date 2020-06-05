# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import copy
import json
import time, datetime
import tempfile, os, posix
import threading
import traceback
import collections
import base64, hashlib

import asyncio

from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning, ReactorNotRunning
from common.service import Service

from monitor.streamable import Streamable
from monitor.rpc import Rpc

from strategy.strategy import Strategy

from config import utils

import logging
logger = logging.getLogger('siis.monitor')
error_logger = logging.getLogger('siis.error.monitor')
traceback_logger = logging.getLogger('siis.traceback.monitor')


class MonitorService(Service):
    """
    Monitoring web service.
    @todo REST HTTP(S) server + WS server.
    @todo receive REST external commands
    @todo streaming throught WS server + streaming API for any sort of data
    @todo streaming of the state and any signals that can be monitored + charting and appliances data
    """

    MODE_NONE = 0
    MODE_FIFO = 1
    MODE_HTTP_WEBSOCKET = 2

    REACTOR = 0  # global twisted reactor ref counter

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
        self._thread_ws = None
        self._running = False
        self._running_ws = False

        self._strategy_service = None
        self._trader_service = None
        self._watcher_service = None

        self._http = None
        self._ws = None

        # host, port, allowed host, order, deny... from config
        self._mode = None

        if self._monitoring_config.get('mode', None) == "fifo":
            self._mode = MonitorService.MODE_FIFO 
        elif self._monitoring_config.get('mode', None) == "http+websocket":
            self._mode = MonitorService.MODE_HTTP_WEBSOCKET 

        self._host = self._monitoring_config.get('host', '127.0.0.1')
        self._port = self._monitoring_config.get('port', '8080')

        # @todo allowdeny...
        allowdeny = self._monitoring_config.get('allowdeny', "allowonly")

        self._allowed_ips = None
        self._denied_ips = None

        if allowdeny == "allow":
            self._allowed_ips = self._monitoring_config.get('list', [])
        elif allowdeny == "any":
            self._allowed_ips = None
        elif allowdeny == "deny":
            self._denied_ips = self._monitoring_config.get('list', [])

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
        else:
            return ("", "")

    def setup(self, watcher_service, trader_service, strategy_service):
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._strategy_service = strategy_service

    #
    # twisted reactor
    #

    @classmethod
    def ref_reactor(cls):
        cls.REACTOR += 1

    @classmethod
    def set_reactor(cls, installSignalHandlers=False):
        if cls.REACTOR > 0 and not reactor.running:
            try:
                reactor.run(installSignalHandlers=installSignalHandlers)
            except ReactorAlreadyRunning:
                # Ignore error about reactor already running
                pass
            except Exception as e:
                error_logger.error(repr(e))
                return

    @classmethod
    def use_reactor(cls, installSignalHandlers=False):
        if cls.REACTOR == 0 and not reactor.running:
            try:
                reactor.run(installSignalHandlers=installSignalHandlers)
                cls.REACTOR += 1
            except ReactorAlreadyRunning:
                # Ignore error about reactor already running
                cls.REACTOR += 1
            except Exception as e:
                error_logger.error(repr(e))
                return
        else:
            cls.REACTOR += 1

    @classmethod
    def release_reactor(cls):
        if cls.REACTOR > 0:
            cls.REACTOR -= 1

        if cls.REACTOR == 0 and reactor.running:
            try:
                reactor.stop()
            except ReactorNotRunning:
                pass

    #
    # processing
    #

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
                from .http.httprestserver import HttpRestServer
                from .http.httpwsserver import HttpWebSocketServer

                self._http = HttpRestServer(self._host, self._port, self._strategy_service, self._trader_service)
                self._ws = HttpWebSocketServer(self._host, self._port+1)

                HttpRestServer.ALLOWED_IPS = copy.copy(self._allowed_ips)
                HttpRestServer.DENIED_IPS = copy.copy(self._denied_ips)

                self._running = True
                self._thread = threading.Thread(name="monitor-rest", target=self.run_http)
                self._thread.start()

                self._running_ws = True
                self._thread_ws = threading.Thread(name="monitor-ws", target=self.run_ws)
                self._thread_ws.start()

    def terminate(self):
        # remove any streamables
        self._running = False
        self._running_ws = False

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
            if self._ws:
                self._ws.stop()

            if self._http:
                self._http.stop()

            if self._thread:
                try:
                    self._thread.join()
                except:
                    pass

                self._thread = None

            if self._thread_ws:
                try:
                    self._thread_ws.join()
                except:
                    pass

                self._thread_ws = None

            self.release_reactor()

            self._http = None
            self._ws = None

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

            # don't waste the CPU, might need a condition on outgoing data and on select incoming
            # but this will be replaced by an asyncio WS + REST API
            time.sleep(0.001)

    def run_ws(self):
        self._ws.start()

    def run_http(self):
        self._http.start()

    def command(self, command_type, data):
        pass

    def publish(self, stream_category, stream_group, stream_name, content):
        if self._mode == MonitorService.MODE_FIFO:
            if self._running:
                self._content.append((stream_category, stream_group, stream_name, content))

        elif self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
            if self._running_ws:
                self._ws.publish(stream_category, stream_group, stream_name, content)

    def on_rpc_message(self, msg):
        # retrieve the appliance
        # @todo using Rpc model and update on the client side
        # rpc = Rpc()
        # rpc.loads(msg)

        cat = msg.get('c', -1)

        if cat == Rpc.STREAM_STRATEGY_CHART:
            appliance = msg.get('g')
            market_id = msg.get('s')
            timeframe = msg.get('v')

            if appliance and market_id:
                self._strategy_service.command(Strategy.COMMAND_TRADER_STREAM, {
                    'appliance': appliance,
                    'market-id': market_id,
                    'timeframe': timeframe,
                    'type': "chart",
                    'action': "unsubscribe" if msg.get('n', 'close') else "subscribe"
                })

        elif cat == Rpc.STREAM_STRATEGY_INFO:
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
                    'action': "unsubscribe" if msg.get('n', 'close') else "subscribe"
                })

        elif cat == Rpc.STRATEGY_TRADE_EXIT_ALL:
            pass

        elif cat == Rpc.STRATEGY_TRADE_ENTRY:
            pass

        elif cat == Rpc.STRATEGY_TRADE_MODIFY:
            pass

        elif cat == Rpc.STRATEGY_TRADE_EXIT:
            pass

        elif cat == Rpc.STRATEGY_TRADE_INFO:
            pass

        elif cat == Rpc.STRATEGY_TRADE_ASSIGN:
            pass

        elif cat == Rpc.STRATEGY_TRADE_CLEAN:
            pass

        elif cat == Rpc.STRATEGY_TRADER_MODIFY:
            pass

        elif cat == Rpc.STRATEGY_TRADER_INFO:
            pass

        elif cat == Rpc.STRATEGY_TRADER_INFO:
            pass
