# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import copy
import logging
import threading

from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning, ReactorNotRunning

from common.service import Service
from config import utils

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
    REACTOR_THREAD = None  # global twisted reactor thread

    PERM_NONE = 0
    PERM_DEBUG = 1
    PERM_ADMIN = 2
    
    PERM_STRATEGY_VIEW = 4
    PERM_STRATEGY_CLEAN_TRADE = 8
    PERM_STRATEGY_CLOSE_TRADE = 16
    PERM_STRATEGY_MODIFY_TRADE = 32
    PERM_STRATEGY_OPEN_TRADE = 64
    PERM_STRATEGY_TRADER = 128
    PERM_STRATEGY_CHART = 256

    PERM_TRADER_BALANCE_VIEW = 512
    PERM_TRADER_ORDER_POSITION_VIEW = 1024
    PERM_TRADER_CANCEL_ORDER = 2048
    PERM_TRADER_CLOSE_POSITION = 4096

    PERMISSIONS = {
        'debug': PERM_STRATEGY_VIEW,
        'admin': PERM_ADMIN,
        'strategy-view': PERM_STRATEGY_VIEW,
        'strategy-clean-trade': PERM_STRATEGY_CLEAN_TRADE,
        'strategy-close-trade': PERM_STRATEGY_CLOSE_TRADE,
        'strategy-modify-trade': PERM_STRATEGY_MODIFY_TRADE,
        'strategy-open-trade': PERM_STRATEGY_OPEN_TRADE,
        'strategy-trader': PERM_STRATEGY_TRADER,
        'strategy-chart': PERM_STRATEGY_CHART,
        'trader-balance-view': PERM_TRADER_BALANCE_VIEW,
        'trader-order-position-view': PERM_TRADER_ORDER_POSITION_VIEW,
        'trader-cancel-order': PERM_TRADER_CANCEL_ORDER,
        'trader-close-position': PERM_TRADER_CLOSE_POSITION,
    }

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

        # port can be override by command line --monitor-port= arg
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

        # permissions
        self._permissions = 0

        permissions = self._monitoring_config.get('permissions', (
            "strategy-view", "strategy-open-trade", "strategy-close-trade", "strategy-modify-trade",
            "strategy-trader",
            "trader-balance-view"))

        for perm in permissions:
            if perm in MonitorService.PERMISSIONS:
                self._permissions |= MonitorService.PERMISSIONS[perm]

        self._client_ws_auth_token = {}

    def setup(self, watcher_service, trader_service, strategy_service):
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._strategy_service = strategy_service

    #
    # permissions
    #

    @property
    def permissions(self):
        return self._permissions

    @property
    def has_debug_perm(self):
        return self._permissions & MonitorService.PERM_DEBUG == MonitorService.PERM_DEBUG

    @property
    def has_admin_perm(self):
        return self._permissions & MonitorService.PERM_ADMIN == MonitorService.PERM_ADMIN

    @property
    def has_strategy_view_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_VIEW == MonitorService.PERM_STRATEGY_VIEW

    @property
    def has_strategy_trader_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_TRADER == MonitorService.PERM_STRATEGY_TRADER

    @property
    def has_strategy_open_trade_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_OPEN_TRADE == MonitorService.PERM_STRATEGY_OPEN_TRADE

    @property
    def has_strategy_close_trade_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_CLOSE_TRADE == MonitorService.PERM_STRATEGY_CLOSE_TRADE

    @property
    def has_strategy_modify_trade_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_MODIFY_TRADE == MonitorService.PERM_STRATEGY_MODIFY_TRADE

    @property
    def has_strategy_clean_trade_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_CLEAN_TRADE == MonitorService.PERM_STRATEGY_CLEAN_TRADE

    @property
    def has_strategy_chart_perm(self):
        return self._permissions & MonitorService.PERM_STRATEGY_CHART == MonitorService.PERM_STRATEGY_CHART

    @property
    def has_trader_balance_view_perm(self):
        return self._permissions & MonitorService.PERM_TRADER_BALANCE_VIEW == MonitorService.PERM_TRADER_BALANCE_VIEW

    def permissions_str(self):
        """
        Returns an array with the permissions string.
        """
        permissions = []

        for str, v in MonitorService.PERMISSIONS.items():
            if self._permissions & v == v:
                permissions.append(str)

        return permissions

    #
    # twisted reactor
    #

    @classmethod
    def use_reactor(cls, installSignalHandlers=False):
        if cls.REACTOR == 0 and not reactor.running:
            try:
                logger.debug("Twisted Reactor Use : Starting...")

                # start a reactor thread
                cls.REACTOR_THREAD = threading.Thread(target=reactor.run, args=(installSignalHandlers,)).start()
                # reactor.run(installSignalHandlers=installSignalHandlers)
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
        #         reactor.callFromThread(reactor.stop)
        #
        #         if cls.REACTOR_THREAD:
        #             cls.REACTOR_THREAD.join()
        #             cls.REACTOR_THREAD = None
        #     except ReactorNotRunning:
        #         pass

        # logger.debug("Twisted Reactor Release : %s ref=%s" % ("running" if reactor.running else "stopped", cls.REACTOR))

    @classmethod
    def stop_reactor(cls):
        cls.REACTOR = 0

        if reactor.running:
            logger.debug("Twisted Reactor Stopping...")
            try:
                reactor.callFromThread(reactor.stop)

                if cls.REACTOR_THREAD:
                    cls.REACTOR_THREAD.join()
                    cls.REACTOR_THREAD = None
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

                self._http = HttpRestServer(self._host, self._port, self.__api_key, self.__api_secret,
                        self, self._strategy_service, self._trader_service, self._watcher_service)

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
