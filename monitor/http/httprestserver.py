# @date 2020-05-24
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# http rest server

import json
import time, datetime
import tempfile, os, posix
import threading
import traceback
import base64
import uuid

from monitor.service import MonitorService

from twisted.web import server, resource, static
from twisted.web.server import Session
from twisted.web.resource import NoResource
from twisted.internet import threads, reactor
from twisted.application import internet, service
from twisted.python.components import registerAdapter
from twisted.web.client import getPage

from zope.interface import Interface, Attribute, implementer

from strategy.strategy import Strategy

import logging
logger = logging.getLogger('siis.monitor.httpserver')
error_logger = logging.getLogger('siis.error.monitor.httpserver')
traceback_logger = logging.getLogger('siis.traceback.monitor.httpserver')


class IAuthToken(Interface):
    value = Attribute("An str containing the auth-token.")


@implementer(IAuthToken)
class AuthToken(object):

    def __init__(self, session):
        self.value = ""


registerAdapter(AuthToken, Session, IAuthToken)


class ShortSession(Session):
    sessionTimeout = 60*60*24*7  # 1w session


class AuthRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, api_key, api_secret):
        super().__init__()

        self.__api_key = api_key
        self.__api_secret = api_secret

        self._monitor_service = monitor_service

    def render_GET(self, request):
        # https://gist.github.com/Hornswoggles/2ef7177aa8eb614d674ea9b9bf1be819
        # https://pyjwt.readthedocs.io/en/latest/
        # https://opensource.com/article/20/3/treq-python
        return json.dumps({}).encode("utf-8")

    def render_POST(self, request):
        content = json.loads(request.content.read().decode("utf-8"))

        api_key = content.get('api-key')

        if api_key == self.__api_key:
            # @todo use a JWT
            auth_token = base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0')
            ws_auth_token = base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0')

            self._monitor_service.register_ws_auth_token(auth_token, ws_auth_token)
        else:
            return json.dumps({
                'error': False,
                'messages': ["invalid-auth"],
                'auth-token': None,
                'ws-auth-token': None,
            }).encode("utf-8")

        s_auth_token = IAuthToken(request.getSession())
        s_auth_token.value = auth_token

        request.setHeader('Authorization', 'Bearer ' + auth_token)

        return json.dumps({
            'error': False,
            'auth-token': auth_token,
            'ws-auth-token': ws_auth_token,
        }).encode("utf-8")

    def render_DELETE(self, request):
        request.getSession().expired()

        return json.dumps({}).encode("utf-8")


def check_auth_token(request):
    s_auth_token = IAuthToken(request.getSession())

    # from header (best)
    bearer = request.getHeader('Authorization')
    if bearer:
        bearer = bearer.split(' ')
    
        if bearer[0] == "Bearer" and bearer[1] == s_auth_token.value:
            return True

    # or from args (not safe)
    auth_token = request.args.get(b'auth-token', [b""])[0].decode("utf-8")
    if auth_token:
        if auth_token == s_auth_token.value:
            return True

    # or from body (intermediate)
    content = json.loads(request.content.read().decode("utf-8"))
    auth_token = content.get('auth-token')
    if auth_token:
        if auth_token == s_auth_token.value:
            return True

    return False


def check_ws_auth_token(monitor_service, request):
    auth_token = request.params.get('auth-token', [""])[0]
    ws_auth_token = request.params.get('ws-auth-token', [""])[0]

    result = False

    if auth_token and ws_auth_token:
        result = monitor_service.is_ws_auth_token(auth_token, ws_auth_token)

    monitor_service.unregister_ws_auth_token(auth_token)

    return result


class StrategyInfoRestAPI(resource.Resource):
    isLeaf = False

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        uri = request.uri.decode("utf-8").split('/')

        trader_name = self._trader_service.trader_name()
        strategy_name = self._strategy_service.strategy_name()
        strategy_id = self._strategy_service.strategy_identifier()

        markets = {}

        instruments_ids = self._strategy_service.strategy().instruments_ids()

        for market_id in instruments_ids:
            instr = self._strategy_service.strategy().instrument(market_id)
            profiles = {}

            markets[market_id] = {
                'strategy': strategy_name,
                'market-id': market_id,
                'symbol': instr.symbol,
                'value-per-pip': instr.value_per_pip,
                'price-limits': instr._price_limits,
                'notional-limits': instr._notional_limits,
                'size-limits': instr._size_limits,
                'bid': instr.market_bid,
                'ofr': instr.market_ofr,
                'mid': instr.market_price,
                'spread': instr.market_spread,
                'profiles': profiles
            }

            contexts_ids = self._strategy_service.strategy().contexts_ids(market_id)

            for context_id in contexts_ids:
                context = self._strategy_service.strategy().dumps_context(market_id, context_id)

                profiles[context_id] = {
                    'strategy': strategy_name,
                    'profile-id': context_id,
                    'entry': {
                        'timeframe': context['entry']['timeframe'],
                        'type': context['entry']['type'],
                    },
                    'take-profit': {
                        'timeframe': context['take-profit']['timeframe'],
                        'distance': context['take-profit']['distance'],
                        'distance-mode': context['take-profit']['distance-type'],
                    },
                    'stop-loss': {
                        'timeframe': context['stop-loss']['timeframe'],
                        'distance': context['stop-loss']['distance'],
                        'distance-mode': context['stop-loss']['distance-type'],
                    }
                }

        results = {
            'broker': {
                'name': trader_name
            },
            'strategy': {
                'name': strategy_name,
                'id': strategy_id,
            },
            'markets': markets,
        }

        return json.dumps(results).encode("utf-8")

    def render_POST(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {}

        # @todo to add dynamically a new instrument

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {}

        # @todo to remove dynamically an instrument

        return json.dumps(results).encode("utf-8")


class InstrumentRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        uri = request.uri.decode("utf-8").split('/')
        results = {}

        # @todo get state info

        return json.dumps(results).encode("utf-8")

    def render_POST(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        # @todo toggle play/pause

        results = {}

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {}

        # @todo remove an instrument and watcher subscription

        return json.dumps(results).encode("utf-8")


class StrategyTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        # list active trade or trade specific
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        trade_id = -1

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if b'trade' in request.args:
            try:
                trade_id = int(request.args[b'trade'][0].decode("utf-8"))
            except ValueError:
                return NoResource("Incorrect trade value")

        if trade_id > 0:
            # @todo
            results['data'] = None
        else:
            # current active trade list
            results['data'] = self._strategy_service.strategy().dumps_trades_update()

        return json.dumps(results).encode("utf-8")

    def render_POST(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {
            'messages': [],
            'error': False
        }

        try:
            content = json.loads(request.content.read().decode("utf-8"))
            command = content.get('command', "")

            if command == "trade-entry":
                results = self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, content)
            elif command == "trade-modify":
                results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True
        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {
            'messages': [],
            'error': False
        }

        content = json.loads(request.content.read().decode("utf-8"))

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, content)

        return json.dumps(results).encode("utf-8")


class HistoricalTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if trade_id > 0:
            # @todo
            results['data'] = None
        else:
            # current active trade list
            results['data'] = self._strategy_service.strategy().dumps_trades_history()

        return json.dumps(result).encode("utf-8")


class Charting(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        uri = request.uri.split('/')
        result = {}

        template = open("monitor/web/charting.html", "rb")

        # @todo replace template part
        result = ""

        close(template)

        return json.dumps(result).encode("utf-8")


class AllowedIPOnlyFactory(server.Site):

    def buildProtocol(self, addr):
        if HttpRestServer.DENIED_IPS and addr.host in HttpRestServer.DENIED_IPS:
            return None

        if HttpRestServer.ALLOWED_IPS and addr.host in HttpRestServer.ALLOWED_IPS:
            return super().buildProtocol(addr)

        return None


class HttpRestServer(object):

    ALLOWED_IPS = None
    DENIED_IPS = None

    def __init__(self, host, port, api_key, api_secret, monitor_service, strategy_service, trader_service):
        self._listener = None

        self._host = host
        self._port = port

        self.__api_key = api_key
        self.__api_secret = api_secret

        self._monitor_service = monitor_service
        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def start(self):
        root = static.File("monitor/web")
        api = resource.Resource()
        root.putChild(b"api", api)

        api_v1 = resource.Resource()
        api.putChild(b"v1", api_v1)

        # auth
        api_v1.putChild(b"auth", AuthRestAPI(self._monitor_service, self.__api_key, self.__api_secret))

        # strategy
        strategy_api = StrategyInfoRestAPI(self._strategy_service, self._trader_service)
        api_v1.putChild(b"strategy", strategy_api)

        instrument_api = InstrumentRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"instrument", instrument_api)

        trade_api = StrategyTradeRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"trade", trade_api)

        historical_trade_api = HistoricalTradeRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"historical", historical_trade_api)

        # trader
        trader_api = resource.Resource()
        api_v1.putChild(b"trader", trader_api)

        # monitor
        monitor_api = resource.Resource()
        api_v1.putChild(b"monitor", monitor_api)

        # charting
        root.putChild(b"chart", Charting(self._strategy_service, self._trader_service))

        factory = AllowedIPOnlyFactory(root)
        factory.sessionFactory = ShortSession

        MonitorService.ref_reactor()
        self._listener = reactor.listenTCP(self._port, factory)

        if self._listener:
            MonitorService.set_reactor(installSignalHandlers=False)

    def stop(self):
        if self._listener:
            self._listener.stopListening()
            self._listener = None

            MonitorService.release_reactor()
