# @date 2020-05-24
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# http rest server

import json
import time, datetime
import tempfile, os, posix
import threading
import traceback

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


class AuthRestAPI(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        
        return json.dumps({}).encode("utf-8")

    def render_POST(self, request):
        api_key = request.args.get('api-key')
        auth_token = '123456789'  # @todo

        s_auth_token = IAuthToken(request.getSession())
        s_auth_token.value = auth_token

        return json.dumps({
            'auth-token': auth_token
        }).encode("utf-8")

    def render_DELETE(self, request):
        request.getSession().expired()

        return json.dumps({}).encode("utf-8")


class StrategyInfoRestAPI(resource.Resource):
    isLeaf = False

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')

        traders_names = self._trader_service.traders_names()
        appliances_names = self._strategy_service.appliances_identifiers()

        appliances = {}
        markets = {}

        for appliance in appliances_names:
            appliances[appliance] = {
                'name': appliance
            }

            instruments_ids = self._strategy_service.appliance(appliance).instruments_ids()

            for market_id in instruments_ids:
                instr = self._strategy_service.appliance(appliance).instrument(market_id)
                profiles = {}

                markets[market_id] = {
                    'appliance': appliance,
                    'market-id': market_id,
                    'symbol': instr.symbol,
                    'value-per-pip': instr.value_per_pip,
                    'price-limits': instr._price_limits,
                    'bid': instr.market_bid,
                    'ofr': instr.market_ofr,
                    'mid': instr.market_price,
                    'spread': instr.market_spread,
                    'profiles': profiles
                }

                contexts_ids = self._strategy_service.appliance(appliance).contexts_ids(market_id)

                for context_id in contexts_ids:
                    context = self._strategy_service.appliance(appliance).dumps_context(market_id, context_id)

                    profiles[context_id] = {
                        'appliance': appliance,
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

        result = {
            'broker': {
                'name': traders_names[0] if traders_names else None
            },
            'appliances': appliances,
            'markets': markets,
        }

        return json.dumps(result).encode("utf-8")

    def render_POST(self, request):
        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")

    def render_DELETE(self, request):
        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")


class InstrumentRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')
        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")

    def render_POST(self, request):
        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")

    def render_DELETE(self, request):
        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")


class StrategyTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')

        if uri[-1] != 'trade':
            try:
                trade_id = int(uri[-1])
            except ValeurError:
                return NoResource()

        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")

    def render_POST(self, request):
        result = {
            'messages': [],
            'error': False
        }

        try:
            content = json.loads(request.content.read().decode("utf-8"))
            command = content.get('command', "")

            if command == "trade-entry":
                result = self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, content)
            elif command == "trade-modify":
                result = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True
        except Exception as e:
            logger.debug(e)

        return json.dumps(result).encode("utf-8")

    def render_DELETE(self, request):
        result = {
            'messages': [],
            'error': False
        }

        content = json.loads(request.content.read().decode("utf-8"))

        result = self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, content)

        return json.dumps(result).encode("utf-8")


class ActiveTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')
        result = {}

        # @todo

        return json.dumps(result).encode("utf-8")


class HistoricalTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def render_GET(self, request):
        uri = request.uri.split('/')
        result = {}

        # @todo

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

    def __init__(self, host, port, strategy_service, trader_service):
        self._listener = None

        self._host = host
        self._port = port

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def start(self):
        root = static.File("monitor/web")
        api = resource.Resource()
        root.putChild(b"api", api)

        api_v1 = resource.Resource()
        api.putChild(b"v1", api_v1)

        # auth
        api_v1.putChild(b"auth", AuthRestAPI())

        # strategy
        strategy_api = StrategyInfoRestAPI(self._strategy_service, self._trader_service)
        api_v1.putChild(b"strategy", strategy_api)

        instrument_api = InstrumentRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"instrument", instrument_api)

        trade_api = StrategyTradeRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"trade", trade_api)

        active_trade_api = ActiveTradeRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"active", active_trade_api)

        historical_trade_api = HistoricalTradeRestAPI(self._strategy_service, self._trader_service)
        strategy_api.putChild(b"historical", historical_trade_api)

        # trader
        trader_api = resource.Resource()
        api_v1.putChild(b"trader", trader_api)

        # monitor
        monitor_api = resource.Resource()
        api_v1.putChild(b"monitor", monitor_api)

        factory = AllowedIPOnlyFactory(root)

        MonitorService.ref_reactor()
        self._listener = reactor.listenTCP(self._port, factory)

        if self._listener:
            MonitorService.set_reactor(installSignalHandlers=False)

    def stop(self):
        if self._listener:
            self._listener.stopListening()
            self._listener = None

            MonitorService.release_reactor()
