# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import copy
import json
import time, datetime
import threading
import traceback
import collections

from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning, ReactorNotRunning
from common.service import Service

from monitor.streamable import Streamable

from strategy.strategy import Strategy

from config import utils

import logging
logger = logging.getLogger('siis.monitor')
error_logger = logging.getLogger('siis.error.monitor')
traceback_logger = logging.getLogger('siis.traceback.monitor')


class MonitorService(Service):
    """
    Monitoring web service.
    """

    MODE_NONE = 0
    MODE_HTTP_WEBSOCKET = 1

    REACTOR = 0  # global twisted reactor ref counter

    def __init__(self, options):
        super().__init__("monitor", options)

        # monitoring config
        self._monitoring_config = utils.load_config(options, 'monitoring')

        if options.get('monitored', True):
            self._monitoring = True
        else:
            self._monitoring = False

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

        if self._monitoring_config.get('mode', None) == "http+websocket":
            self._mode = MonitorService.MODE_HTTP_WEBSOCKET 

        self._host = self._monitoring_config.get('host', '127.0.0.1')
        self._port = self._monitoring_config.get('port', '8080')

        # port can be overrided by command line --monitor-port= arg
        if options.get('monitor-port'):
            self._port = options['monitor-port']

        self.__api_key = self._monitoring_config.get('api-key', "")
        self.__api_secret = self._monitoring_config.get('api-secret', "")

        # allow deny rules
        allowdeny = self._monitoring_config.get('allowdeny', "allowonly")

        self._allowed_ips = None
        self._denied_ips = None

        if allowdeny == "allow":
            self._allowed_ips = self._monitoring_config.get('list', [])
        elif allowdeny == "any":
            self._allowed_ips = None
        elif allowdeny == "deny":
            self._denied_ips = self._monitoring_config.get('list', [])

        self._client_ws_auth_token = {}

    def setup(self, watcher_service, trader_service, strategy_service):
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._strategy_service = strategy_service

    #
    # twisted reactor
    #

    @classmethod
    def use_reactor(cls, installSignalHandlers=False):
        if cls.REACTOR == 0 and not reactor.running:
            try:
                logger.debug("Twisted Reactor Use : Starting...")
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

        # logger.debug("Twisted Reactor Use : %s ref=%s" % ("running" if reactor.running else "stopped", cls.REACTOR))

    @classmethod
    def release_reactor(cls):
        if cls.REACTOR > 0:
            cls.REACTOR -= 1

        # if cls.REACTOR == 0 and reactor.running:
        #     logger.debug("Twisted Reactor Stopping...")
        #     try:
        #         reactor.stop()
        #     except ReactorNotRunning:
        #         pass

        # logger.debug("Twisted Reactor Release : %s ref=%s" % ("running" if reactor.running else "stopped", cls.REACTOR))
    
    @classmethod
    def stop_reactor(cls):
        cls.REACTOR = 0

        if reactor.running:
            logger.debug("Twisted Reactor Stopping...")
            try:
                reactor.stop()
            except ReactorNotRunning:
                pass

    #
    # processing
    #

    def start(self):
        if self._monitoring:
            if self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
                from .http.httprestserver import HttpRestServer
                from .http.httpwsserver import HttpWebSocketServer

                self._http = HttpRestServer(self._host, self._port, self.__api_key, self.__api_secret, self, self._strategy_service, self._trader_service)
                self._ws = HttpWebSocketServer(self._host, self._port+1, self)

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

        if self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
            if self._ws:
                self._ws.stop()

            if self._http:
                self._http.stop()

            self.release_reactor()

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

    def run_ws(self):
        self._ws.start()

    def run_http(self):
        self._http.start()

    def register_ws_auth_token(self, auth_token, ws_auth_token):
        self._client_ws_auth_token[auth_token] = ws_auth_token

    def is_ws_auth_token(self, auth_token, ws_auth_token):
        return self._client_ws_auth_token.get(auth_token, "") == ws_auth_token

    def unregister_ws_auth_token(self, auth_token):
        if auth_token in self._client_ws_auth_token:
            del (self._client_ws_auth_token[auth_token])

    def publish(self, stream_category, stream_group, stream_name, content):
        try:
            if self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
                if self._running_ws:
                    self._ws.publish(stream_category, stream_group, stream_name, content)

        except Exception as e:
            error_logger.error(repr(e))
