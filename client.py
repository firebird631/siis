# @date 2019-01-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Monitoring client

import signal
import sys
import threading

import json
import os
import pathlib
import logging
import traceback

import requests
import websocket

from common.siislog import SiisLog
from config import utils
from monitor.client import APP_SHORT_NAME, APP_VERSION
from terminal.terminal import Terminal
from common.utils import fix_thread_set_name
from charting.charting import Charting

from monitor.client.dispatcher import Dispatcher

import matplotlib

matplotlib.use('QtAgg')

import matplotlib.pyplot as plt


running = False


def signal_int_handler(sig, frame):
    Charting.inst().stop()


def display_help():
    pass


def has_exception(_logger, e):
    _logger.error(repr(e))
    _logger.error(traceback.format_exc())


def install(options):
    config_path = "monitor/client/"
    data_path = "monitor/client/"

    home = pathlib.Path.home()
    if home.exists():
        if sys.platform == "linux":
            config_path = pathlib.Path(home, '.siis', 'config')
            log_path = pathlib.Path(home, '.siis', 'log')
        elif sys.platform == "windows":
            app_data = os.getenv('APPDATA')

            config_path = pathlib.Path(home, app_data, 'siis', 'config')
            log_path = pathlib.Path(home, app_data, 'siis', 'log')
        else:
            config_path = pathlib.Path(home, '.siis', 'config')
            log_path = pathlib.Path(home, '.siis', 'log')
    else:
        # uses cwd
        home = pathlib.Path(os.getcwd())

        config_path = pathlib.Path(home, 'user', 'config')
        log_path = pathlib.Path(home, 'user', 'log')

    # config/
    if not config_path.exists():
        config_path.mkdir(parents=True)

    options['config-path'] = str(config_path)

    # log/
    if not log_path.exists():
        log_path.mkdir(parents=True)

    options['log-path'] = str(log_path)


def base_url(host, port, protocol="http"):
    return "%s://%s:%i/api/v1" % (protocol, host, port)


def make_url(host, port, protocol, endpoint):
    return base_url(host, port, protocol) + '/' + endpoint


class Connection(object):

    def __init__(self, data):
        self.auth_token = data.get('auth-token')
        self.ws_auth_token = data.get('ws-auth-token')
        self.permissions = data.get('permissions')
        self.twisted_session = data.get('session')

        self.session = None  # HTTP requests session

        self.protocol = "http"
        self.api_key = ""

        self.host = ""
        self.port = 0

        self.ws = None
        self.wst = None

        self.dispatcher = None

    # def on_message(self, cls, msg):
    def on_message(self, msg):
        try:
            message = json.loads(msg)
        except json.JSONDecodeError as e:
            message = {}

        if message and self.dispatcher:
            self.dispatcher.on_message(message)

    def on_close(self, cls, close_status_code, close_msg):
        pass

    def on_open(self, cls):
        pass

    def on_error(self, cls, error):
        pass

    def close(self):
        if self.ws is not None:
            try:
                self.ws.close()
            except:
                pass

            self.ws = None

        if self.wst is not None:
            try:
                if self.wst.is_alive():
                    self.wst.join()
            except:
                pass

            self.wst = None


def http_auth(session, host: str, port: int, api_key: str):
    session.headers.update({'user-agent': "%s-%s" % (
        APP_SHORT_NAME, '.'.join([str(x) for x in APP_VERSION]))})
    session.headers.update({'content-type': 'application/json'})

    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json; charset=UTF-8',
        'TWISTED_SESSION': ""
    })

    url = make_url(host, port, "http", "auth")
    params = {
        'api-key': api_key
    }

    try:
        response = session.post(url, data=json.dumps(params))
    except requests.exceptions.ConnectionError:
        Terminal.inst().error("Unable to auth")
        return None

    if not response.ok:
        Terminal.inst().error("HTTP status code %s %s " % (response.status_code, response.text))
        return None

    data = response.json()

    if data.get('error') or not data.get('auth-token'):
        return None

    Terminal.inst().info("HTTP Connection and Auth : OK")
    conn = Connection(data)

    conn.session = session
    conn.host = host
    conn.port = port
    conn.protocol = "http"
    conn.api_key = api_key

    return conn


class WsSocketManager(threading.Thread):

    def __init__(self):  # client
        """Initialise the WsSocketManager"""
        threading.Thread.__init__(self)
        self.factories = {}
        self._connected_event = threading.Event()
        self._user_timer = None
        self._user_listen_key = None
        self._user_callback = None

    def start_socket(self, url, callback):
        factory = WsClientFactory(url)
        factory.base_client = self
        factory.protocol = WsClientProtocol
        factory.callback = callback
        factory.reconnect = False  # True
        reactor.callFromThread(connectWS, factory)


def conn_ws(connection: Connection):
    ws_url = "ws://%s:%s?ws-auth-token=%s&auth-token=%s" % (
        connection.host, connection.port+1, connection.ws_auth_token, connection.auth_token)

    threading.Thread(target=reactor.run, args=(False,)).start()

    ws = WsSocketManager()
    ws.start_socket(ws_url, connection.on_message)

    wst = None

    # ws = websocket.WebSocketApp(ws_url,
    #                             on_message=connection.on_message,
    #                             on_close=connection.on_close,
    #                             on_open=connection.on_open,
    #                             on_error=connection.on_error)
    #
    # wst = threading.Thread(name="siis.ws", target=lambda: ws.run_forever())
    # wst.daemon = True
    # wst.start()

    connection.ws = ws
    connection.wst = wst

    return True


from autobahn.twisted.websocket import WebSocketClientFactory, WebSocketClientProtocol, connectWS
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory


class WsClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        pass

    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                payload_obj = payload.decode('utf8')
            except ValueError:
                pass
            else:
                try:
                    self.factory.callback(payload_obj)
                except Exception as e:
                    Terminal.inst().error(repr(e))


class WsReconnectingClientFactory(ReconnectingClientFactory):
    """
    Finally manage at watcher level (reconnect = False)
    """

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 2  # 20

    maxRetries = 3  # 30


class WsClientFactory(WebSocketClientFactory, WsReconnectingClientFactory):

    def __init__(self, *args, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None

    protocol = WsClientProtocol

    def clientConnectionFailed(self, connector, reason):
        if not self.reconnect:
            return

        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        if not self.reconnect:
            return

        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def buildProtocol(self, addr):
        return WsClientProtocol(self)


def subscribe(connection, market_id, timeframe):
    if not connection or not connection.session:
        return None

    session = connection.session

    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json; charset=UTF-8',
        'TWISTED_SESSION': connection.twisted_session,
        'Authorization': "Bearer " + connection.auth_token,
    })

    url = make_url(connection.host, connection.port, connection.protocol, "strategy")
    params = {
        'api-key': connection.api_key,
        'command': 'subscribe',
        'type': 'chart',
        'market-id': market_id,
        'timeframe': timeframe
    }

    try:
        response = session.post(url, data=json.dumps(params))
    except requests.exceptions.ConnectionError:
        Terminal.inst().error("Unable to subscribe")
        return None

    if not response.ok:
        Terminal.inst().error("HTTP status code %s %s " % (response.status_code, response.text))
        return None

    data = response.json()

    if data.get('error'):
        return None

    return True


def unsubscribe(connection, market_id, timeframe):
    if not connection or not connection.session:
        return None

    session = connection.session

    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json; charset=UTF-8',
        'TWISTED_SESSION': connection.twisted_session,
        'Authorization': "Bearer " + connection.auth_token,
    })

    url = make_url(connection.host, connection.port, connection.protocol, "strategy")
    params = {
        'api-key': connection.api_key,
        'command': 'unsubscribe',
        'type': 'chart',
        'market-id': market_id,
        'timeframe': timeframe
    }

    try:
        response = session.post(url, data=json.dumps(params))
    except requests.exceptions.ConnectionError:
        Terminal.inst().error("Unable to unsubscribe")
        return None

    if not response.ok:
        Terminal.inst().error("HTTP status code %s %s " % (response.status_code, response.text))
        return None

    data = response.json()

    if data.get('error'):
        return None

    return True


def terminate(connection, market_id, timeframes):
    # subscribe
    for timeframe in timeframes:
        unsubscribe(connection, market_id, timeframe)

    if connection:
        reactor.callFromThread(reactor.stop)

        connection.close()
        connection = None


def application(argv):
    fix_thread_set_name()

    # init terminal display
    Terminal.inst()

    options = {
        'working-path': os.getcwd(),
        'config-path': './user/config',
        'log-path': './user/log',
        'log-name': 'client.log'
    }

    # create initial siis data structure if necessary
    install(options)

    siis_log = SiisLog(options)
    logger = logging.getLogger('siis.client')
    hostname = ""
    host = ""
    http_port = 0
    ws_port = 0
    api_key = ""
    market_id = ""
    timeframes = ""

    for arg in sys.argv:
        if arg.startswith("http"):
            hostname = arg
        elif arg.startswith("--"):
            api_key = argv
            api_key = api_key.lstrip("--")
        elif arg.startswith("-m"):
            market_id = arg
            market_id = market_id.lstrip('-m')
        elif arg.startswith("-t"):
            timeframe = arg
            timeframes = timeframe.lstrip('-t').split(',')

    monitoring_config = utils.load_config(options, 'monitoring')

    if not api_key:
        api_key = monitoring_config.get('api-key', "")

    if not api_key:
        Terminal.inst().info("Missing API key")

    parts = hostname.split(':')
    if len(parts) > 0:
        host = parts[0]
    if len(parts) > 1:
        http_port = int(parts[1])
        ws_port = http_port + 1

    if not host:
        host = monitoring_config.get('host')
        Terminal.inst().info("Use default host")

    if not host:
        Terminal.inst().error("- Missing host !")
        sys.exit(-1)

    if not http_port:
        http_port = monitoring_config.get('port')
        ws_port = http_port + 1
        Terminal.inst().info("Use default port")

    if not http_port:
        Terminal.inst().info("Missing port")
        sys.exit(-1)

    if not ws_port:
        Terminal.inst().info("Missing WS port")
        sys.exit(-1)

    # sig int and sig term handler
    signal.signal(signal.SIGINT, signal_int_handler)
    signal.signal(signal.SIGTERM, signal_int_handler)

    # auth HTTP
    connection = http_auth(requests.Session(), host, http_port, api_key)
    if not connection:
        Terminal.inst().info("Unable to auth")
        sys.exit(-1)

    # conn WS
    conn_ws(connection)

    # subscribe
    for timeframe in timeframes:
        subscribe(connection, market_id, timeframe)

    Terminal.inst().info("Starting SIIS simple chart client...")
    Terminal.inst().flush()

    dispatcher = Dispatcher()
    connection.dispatcher = dispatcher

    Terminal.inst().message("Running main loop...")

    Charting.inst().show()
    Charting.inst().run()

    # close message
    messages = dispatcher.close()

    terminate(connection, market_id, timeframes)

    connection = None
    session = None

    Terminal.inst().info("Terminate...")
    Terminal.inst().flush()

    # terminate charting singleton
    Charting.terminate()

    Terminal.inst().info("Bye!")
    Terminal.inst().flush()

    Terminal.terminate()


if __name__ == "__main__":
    application(sys.argv)
