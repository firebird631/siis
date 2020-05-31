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


class StrategyTradeRestAPI(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')
        return "<html>Hello, strat get world!</html>".encode("utf-8")

    def render_POST(self, request):
        return "<html>Hello, strat post world!</html>".encode("utf-8")

    def render_DELETE(self, request):
        return "<html>Hello, strat delete world!</html>".encode("utf-8")


class InstrumentRestAPI(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')
        return "<html>Hello, instrument get world!</html>".encode("utf-8")

    def render_POST(self, request):
        return "<html>Hello, instrument post world!</html>".encode("utf-8")

    def render_DELETE(self, request):
        return "<html>Hello, instrument delete world!</html>".encode("utf-8")


class TradeRestAPI(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')

        if uri[-1] != 'trade':
            try:
                trade_id = int(uri[-1])
            except ValeurError:
                return NoResource()

        return "<html>Hello, trade get world!</html>".encode("utf-8")

    def render_POST(self, request):
        return "<html>Hello, trade post world!</html>".encode("utf-8")

    def render_DELETE(self, request):
        return "<html>Hello, trade delete world!</html>".encode("utf-8")


class ActiveTradeRestAPI(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        uri = request.uri.decode("utf-8").split('/')
        return "<html>Hello, ActiveTradeRestAPI get world!</html>".encode("utf-8")

    def render_POST(self, request):
        return "<html>Hello, ActiveTradeRestAPI post world!</html>".encode("utf-8")

    def render_DELETE(self, request):
        return "<html>Hello, ActiveTradeRestAPI delete world!</html>".encode("utf-8")


class HistoricalTradeRestAPI(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        uri = request.uri.split('/')
        return "<html>Hello, HistoricalTradeRestAPI get world!</html>".encode("utf-8")

    def render_POST(self, request):
        return "<html>Hello, HistoricalTradeRestAPI post world!</html>".encode("utf-8")

    def render_DELETE(self, request):
        return "<html>Hello, HistoricalTradeRestAPI delete world!</html>".encode("utf-8")



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

    def __init__(self, host, port):
        self._site = None
        self._listener = None
        self._host = host
        self._port = port

    def start(self):
        root = static.File("monitor/web")
        api = resource.Resource()

        root.putChild(b"api", api)

        api_v1 = resource.Resource()
        api.putChild(b"v1", api_v1)

        # auth
        api_v1.putChild(b"auth", AuthRestAPI())

        # strategy
        strategy_api = resource.Resource()
        api_v1.putChild(b"strategy", strategy_api)

        instrument_api = InstrumentRestAPI()
        strategy_api.putChild(b"instrument", instrument_api)

        trade_api = StrategyTradeRestAPI()
        strategy_api.putChild(b"trade", trade_api)

        active_trade_api = ActiveTradeRestAPI()
        strategy_api.putChild(b"active", active_trade_api)

        historical_trade_api = HistoricalTradeRestAPI()
        strategy_api.putChild(b"historical", historical_trade_api)

        # trader
        trader_api = resource.Resource()
        api_v1.putChild(b"trader", trader_api)

        # monitor
        monitor_api = resource.Resource()
        api_v1.putChild(b"monitor", monitor_api)

        # factory = server.Site(root)
        factory = AllowedIPOnlyFactory(root)

        self._listener = reactor.listenTCP(self._port, factory)

        MonitorService.use_reactor(installSignalHandlers=False)

    def stop(self):
        if self._listener:
            self._listener.stopListening()
            self._listener = None

        MonitorService.release_reactor()
