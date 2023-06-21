# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import copy
import logging
import threading
import traceback

from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning, ReactorNotRunning

from common.service import Service
from config import utils

logger = logging.getLogger('siis.monitor')
error_logger = logging.getLogger('siis.error.monitor')
traceback_logger = logging.getLogger('siis.traceback.monitor')


class MonitorService(Service):
    """
    Monitoring Web service.
    Support HTTP REST and WebSocket channel for command and supervision.
    It also supports a REDIS channel streaming (read-only) to publish signals, charting data, performance.
    And it is responsible to manage the user installed scripts.
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

    REDIS_DATA_NONE = 0
    REDIS_DATA_STATUS = 1
    REDIS_DATA_STRATEGY_TRADER = 2
    REDIS_DATA_STRATEGY_TRADE_EX = 4
    REDIS_DATA_STRATEGY_TRADE_UPDATE = 8
    REDIS_DATA_INSTRUMENT_INFO = 16
    REDIS_DATA_STRATEGY_CHART = 32

    REDIS_DEFAULT_PORT = 6379
    REDIS_STREAMS = {
        "strategy-info": REDIS_DATA_STRATEGY_TRADER,
        "strategy-trade-ex": REDIS_DATA_STRATEGY_TRADE_EX,
        "strategy-trade-update": REDIS_DATA_STRATEGY_TRADE_UPDATE,
        "instrument-info": REDIS_DATA_INSTRUMENT_INFO,
        "status": REDIS_DATA_STATUS,
        "strategy-chart": REDIS_DATA_STRATEGY_CHART
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
        self._thread_redis = None

        self._running = False
        self._running_ws = False
        self._running_redis = False

        self._strategy_service = None
        self._trader_service = None
        self._watcher_service = None
        self._view_service = None

        self._http = None
        self._ws = None
        self._redis = None

        # host, port, allowed host, order, deny... from config
        self._mode = None

        if self._monitoring_config.get('mode', None) == "http+websocket":
            self._mode = MonitorService.MODE_HTTP_WEBSOCKET 

        self._host = self._monitoring_config.get('host', '127.0.0.1')
        self._port = self._monitoring_config.get('port', '8080')

        # port can be overridden by command line --monitor-port= arg
        if options.get('monitor-port'):
            self._port = options['monitor-port']

        # admin/managers api key/secret
        self.__api_key = self._monitoring_config.get('api-key', "")
        self.__api_secret = self._monitoring_config.get('api-secret', "")

        # allow / deny rules
        allow_deny = self._monitoring_config.get('allow-deny', "any")

        self._allowed_ips = None
        self._denied_ips = None

        if allow_deny == "allow":
            self._allowed_ips = self._monitoring_config.get('list', [])
        elif allow_deny == "any":
            self._allowed_ips = None
        elif allow_deny == "deny":
            self._denied_ips = self._monitoring_config.get('list', [])

        # permissions
        self._permissions = 0

        permissions = self._monitoring_config.get('permissions', (
            "strategy-view",
            "strategy-open-trade", "strategy-close-trade", "strategy-modify-trade", "strategy-clean-trade",
            "strategy-trader",
            "trader-balance-view",
            "strategy-chart"
        ))
        logger.debug(permissions)

        for perm in permissions:
            if perm in MonitorService.PERMISSIONS:
                self._permissions |= MonitorService.PERMISSIONS[perm]

        # REDIS
        self._use_redis = False
        self._redis_host = "127.0.0.1"
        self._redis_port = MonitorService.REDIS_DEFAULT_PORT
        self._redis_pwd = ""
        self._redis_data = 0

        if self._monitoring_config.get('redis', {}):
            self._redis_host = self._monitoring_config['redis'].get('host', "127.0.0.1")
            self._redis_port = self._monitoring_config['redis'].get('port', MonitorService.REDIS_DEFAULT_PORT)
            self._redis_pwd = self._monitoring_config['redis'].get('password', "")

            redis_data = self._monitoring_config['redis'].get('data', list(MonitorService.REDIS_STREAMS.keys()))

            for data in redis_data:
                if data in MonitorService.REDIS_STREAMS:
                    self._redis_data |= MonitorService.REDIS_STREAMS[data]

            if self._redis_host and self._redis_port and self._redis_data:
                self._use_redis = True

        self._client_ws_auth_token = {}

        self._scripts = {}  # user installed scripts registry

    def setup(self, watcher_service, trader_service, strategy_service, view_service):
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._strategy_service = strategy_service
        self._view_service = view_service

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

    @property
    def redis_stream_strategy_trade_ex(self):
        return self._redis_data & MonitorService.REDIS_DATA_STRATEGY_TRADE_EX == MonitorService.REDIS_DATA_STRATEGY_TRADE_EX

    @property
    def redis_stream_strategy_trade_update(self):
        return self._redis_data & MonitorService.REDIS_DATA_STRATEGY_TRADE_UPDATE == MonitorService.REDIS_DATA_STRATEGY_TRADE_UPDATE

    @property
    def redis_stream_strategy_trader(self):
        return self._redis_data & MonitorService.REDIS_DATA_STRATEGY_TRADER == MonitorService.REDIS_DATA_STRATEGY_TRADER

    @property
    def redis_stream_status(self):
        return self._redis_data & MonitorService.REDIS_DATA_STATUS == MonitorService.REDIS_DATA_STATUS

    @property
    def redis_stream_strategy_chart(self):
        return self._redis_data & MonitorService.REDIS_DATA_STRATEGY_CHART == MonitorService.REDIS_DATA_STRATEGY_CHART

    def permissions_str(self):
        """
        Returns an array with the permissions string.
        """
        permissions = []

        for k, v in MonitorService.PERMISSIONS.items():
            if self._permissions & v == v:
                permissions.append(k)

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
            except ReactorNotRunning:
                pass

            if cls.REACTOR_THREAD:
                try:
                    cls.REACTOR_THREAD.join()
                except:
                    pass

                cls.REACTOR_THREAD = None

    #
    # processing
    #

    def start(self, options):
        if self._monitoring:
            if self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
                from .http.httprestserver import HttpRestServer
                from .http.httpwsserver import HttpWebSocketServer

                self._http = HttpRestServer(self._host, self._port, self.__api_key, self.__api_secret,
                                            self, self._strategy_service, self._trader_service,
                                            self._watcher_service, self._view_service)

                self._ws = HttpWebSocketServer(self._host, self._port+1, self)

                HttpRestServer.ALLOWED_IPS = copy.copy(self._allowed_ips)
                HttpRestServer.DENIED_IPS = copy.copy(self._denied_ips)

                MonitorService.use_reactor(installSignalHandlers=False)

                self._running = True
                self._thread = threading.Thread(name="monitor-rest", target=self.run_http)
                self._thread.start()

                self._running_ws = True
                self._thread_ws = threading.Thread(name="monitor-ws", target=self.run_ws)
                self._thread_ws.start()

            if self._use_redis:
                from .redis.redisclient import RedisClient

                self._redis = RedisClient(self._redis_host, self._redis_port, self._redis_pwd,
                                          self, self._strategy_service, self._trader_service,
                                          self._watcher_service, self._view_service)

                self._running_redis = True
                self._thread_redis = threading.Thread(name="monitor-redis", target=self.run_redis)
                self._thread_redis.start()

    def terminate(self):
        # remove any streamable
        self._running = False
        self._running_ws = False
        self._running_redis = False

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

        if self._use_redis:
            if self._redis:
                self._redis.stop()

            if self._thread_redis:
                try:
                    self._thread_redis.join()
                except:
                    pass

                self._thread_redis = None

            self._redis = None

        # user scripts
        for k, script in self._scripts.items():
            try:
                script.stop()
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        self._scripts = {}

    def run_ws(self):
        self._ws.start()

    def run_http(self):
        self._http.start()

    def run_redis(self):
        self._redis.start()

    #
    # auth token
    #

    def register_ws_auth_token(self, auth_token, ws_auth_token):
        self._client_ws_auth_token[auth_token] = ws_auth_token

    def is_ws_auth_token(self, auth_token, ws_auth_token):
        return self._client_ws_auth_token.get(auth_token, "") == ws_auth_token

    def unregister_ws_auth_token(self, auth_token):
        if auth_token in self._client_ws_auth_token:
            del (self._client_ws_auth_token[auth_token])

    #
    # messages publisher
    #

    def publish(self, stream_category, stream_group, stream_name, content):
        # insert category, group and stream name before publish
        content['c'] = stream_category
        content['g'] = stream_group
        content['s'] = stream_name

        try:
            if self._mode == MonitorService.MODE_HTTP_WEBSOCKET:
                if self._running_ws:
                    self._ws.publish(stream_category, stream_group, stream_name, content)

            if self._use_redis:
                if self._running_redis:
                    self._redis.publish(stream_category, stream_group, stream_name, content)

        except Exception as e:
            error_logger.error(repr(e))

    #
    # users scripts
    #

    def has_script(self, name):
        return name in self._scripts

    def install_script(self, name, inst):
        try:
            inst.start()
        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())
            return False

        self._scripts[name] = inst
        return True

    def remove_script(self, name):
        if name in self._scripts:
            inst = self._scripts[name]

            try:
                inst.stop()
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

            del self._scripts[name]
            return True

        return False
