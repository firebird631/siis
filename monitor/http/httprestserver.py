# @date 2020-05-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# http rest server

import json
import base64
import uuid

from monitor.service import MonitorService

from twisted.web import server, resource, static
from twisted.web.server import Session
from twisted.web.resource import NoResource
from twisted.internet import reactor
from twisted.python.components import registerAdapter

from zope.interface import Interface, Attribute, implementer

from strategy.strategy import Strategy
from trader.trader import Trader

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


class LongSession(Session):
    sessionTimeout = 60*60*24*7  # 1w session


class AuthRestAPI(resource.Resource):
    isLeaf = True
    sessions = set()

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
            auth_token = base64.b64encode(
                uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0')

            ws_auth_token = base64.b64encode(
                uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0')

            self._monitor_service.register_ws_auth_token(auth_token, ws_auth_token)
        else:
            return json.dumps({
                'error': False,
                'messages': ["invalid-auth"],
                'auth-token': None,
                'ws-auth-token': None,
                'session': "",
                'permissions': []
            }).encode("utf-8")

        session = request.getSession()

        s_auth_token = IAuthToken(session)
        s_auth_token.value = auth_token

        request.setHeader('Authorization', 'Bearer ' + auth_token)
        request.setHeader('Session', session.uid.decode('utf-8'))

        if session.uid not in self.sessions:
            self.sessions.add(session.uid)
            session.notifyOnExpire(lambda: self._expired(session.uid))

        permissions = self._monitor_service.permissions_str()

        return json.dumps({
            'error': False,
            'auth-token': auth_token,
            'ws-auth-token': ws_auth_token,
            'session': session.uid.decode('utf-8'),
            'permissions': permissions
        }).encode("utf-8")

    def render_DELETE(self, request):
        request.getSession().expired()

        return json.dumps({}).encode("utf-8")

    def _expired(self, uid):
        # cleanup here or could disconnect related websocket
        self.sessions.remove(uid)


def check_auth_token(request):
    s_auth_token = IAuthToken(request.getSession())

    # from header (best)
    bearer = request.getHeader('Authorization')
    if bearer:
        bearer = bearer.split(' ')
    
        if bearer[0] == "Bearer" and bearer[1] == s_auth_token.value:
            return True

    # or from args (not safe)
    try:
        auth_token = request.args.get(b'auth-token', [b"\"\""])[0].decode("utf-8")
        if auth_token:
            if auth_token == s_auth_token.value:
                return True
    except Exception as e:
        error_logger.error(repr(e))

    # or from body (intermediate)
    try:
        content = json.loads(request.content.read().decode("utf-8"))
        auth_token = content.get('auth-token')
        if auth_token:
            if auth_token == s_auth_token.value:
                return True
    except Exception as e:
        error_logger.error(repr(e))

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

    def __init__(self, monitor_service, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._allow_view = monitor_service.has_strategy_view_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        uri = request.uri.decode("utf-8").split('/')

        trader_name = self._trader_service.trader_name()
        strategy_name = self._strategy_service.strategy_name()
        strategy_id = self._strategy_service.strategy_identifier()

        # insert markets details
        markets = {}

        instruments_ids = self._strategy_service.strategy().instruments_ids()

        for market_id in instruments_ids:
            instr = self._strategy_service.strategy().instrument(market_id)

            strategy_trader = self._strategy_service.strategy().strategy_traders.get(market_id)
            if strategy_trader is None:
                continue

            profiles = {}

            markets[market_id] = {
                'strategy': strategy_name,
                'market-id': market_id,
                'symbol': instr.symbol,
                'base': instr.base,       # base or asset
                'quote': instr.quote,
                'currency': instr.currency,
                'tradeable': instr.tradeable,
                'value-per-pip': instr.value_per_pip,
                'price-limits': instr.price_limits,
                'notional-limits': instr.notional_limits,
                'size-limits': instr.size_limits,
                'bid': instr.market_bid,
                'ask': instr.market_ask,
                'mid': instr.market_price,
                'spread': instr.market_spread,
                'last-update-time': instr.last_update_time,
                'sessions': {
                    'timezone': instr.timezone,
                    'offset': instr.session_offset,
                    'duration': instr.session_duration,
                    'trading': [t.to_dict() for t in instr.trading_sessions]
                },
                'trade': {
                    'activity': strategy_trader.activity,       # bool
                    'affinity': strategy_trader.affinity,       # int
                    'max-trades': strategy_trader.max_trades,   # int
                    'quantity': instr.trade_quantity,           # float
                    'quantity-mode': instr.trade_quantity_mode  # int const
                },
                'volumes': {
                    'base': instr.vol24h_base,   # float
                    'quote': instr.vol24h_quote  # float
                },
                'profiles': profiles  # dict str:dict
            }

            contexts_ids = self._strategy_service.strategy().contexts_ids(market_id)

            for context_id in contexts_ids:
                context = self._strategy_service.strategy().dumps_context(market_id, context_id)
                context['strategy'] = strategy_name  # related strategy
                context['profile-id'] = context_id   # context id to profile id

                profiles[context_id] = context

        results = {
            'broker': {
                'name': trader_name
            },
            'strategy': {
                'name': strategy_name,
                'id': strategy_id,
                'backtesting': self._strategy_service.backtesting,
            },
            'markets': markets
        }

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

            if command == "subscribe":
                pass  # @todo
                # results =
            elif command == "unsubscribe":
                pass  # @todo
                # results =
            else:
                results['messages'].append("Missing command.")
                results['error'] = True
        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        results = {}

        return json.dumps(results).encode("utf-8")


class InstrumentRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._allow_trader = monitor_service.has_strategy_trader_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        uri = request.uri.decode("utf-8").split('/')

        market_id = ""
        context_id = ""

        if b'market-id' in request.args:
            try:
                market_id = request.args[b'market-id'][0].decode("utf-8")
            except ValueError:
                return NoResource("Incorrect market-id value")

        if b'context-id' in request.args:
            try:
                context_id = request.args[b'context-id'][0].decode("utf-8")
            except ValueError:
                return NoResource("Incorrect context-id value")

        strategy_name = self._strategy_service.strategy_name()
        strategy_id = self._strategy_service.strategy_identifier()

        # @todo get state info quantity, context/profile

        with self._strategy_service.strategy().mutex:
            strategy_trader = self._strategy_service.strategy().strategy_traders.get(market_id)
            if strategy_trader is None:
                return NoResource("Unknown market-id %s" % market_id)

            with strategy_trader.trade_mutex:
                results = {
                    'strategy': strategy_name,
                    'strategy-id': strategy_id,
                    'market-id': market_id,
                    'activity': strategy_trader.activity,
                    'affinity': strategy_trader.affinity,
                    # context/profile
                    # 'trade-mode': strategy_trader.
                }

        return json.dumps(results).encode("utf-8")

    def render_POST(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_trader:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        results = {
            'messages': [],
            'error': False
        }

        try:
            content = json.loads(request.content.read().decode("utf-8"))
            command = content.get('command', "")

            if command in ("activity", "affinity", "quantity", "max-trades", "option"):
                results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True
        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_trader:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        results = {}

        return json.dumps(results).encode("utf-8")


class StrategyTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._allow_view = monitor_service.has_strategy_view_perm
        self._allow_open_trade = monitor_service.has_strategy_open_trade_perm
        self._allow_close_trade = monitor_service.has_strategy_close_trade_perm
        self._allow_modify_trade = monitor_service.has_strategy_modify_trade_perm
        self._allow_clean_trade = monitor_service.has_strategy_clean_trade_perm

    def render_GET(self, request):
        # list active/pending trades without theirs operations or a specific trade with its operations in details
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        trade_id = -1
        market_id = None

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

        if b'market-id' in request.args:
            try:
                market_id = request.args[b'market-id'][0].decode("utf-8")
            except ValueError:
                return NoResource("Incorrect market-id value")

        if trade_id > 0:
            with self._strategy_service.strategy.mutex:
                strategy_trader = self._strategy_service.strategy().strategy_traders.get(market_id)
                if strategy_trader is None:
                    return NoResource("Unknown market-id %s" % market_id)

                found_trade = None

                with strategy_trader.trade_mutex:
                    for trade in strategy_trader.trades:
                        if trade.id == trade_id:
                            found_trade = trade
                            break

                    if found_trade:
                        # trade dumps with its operations
                        trade_dumps = trade.dumps_notify_update(self._strategy_service.timestamp, strategy_trader)
                        trade_dumps['operations'] = [operation.dumps() for operation in trade.operations]

                        results['data'] = trade_dumps
                    else:
                        return NoResource("Unknown trade-id %s for market %s" % (trade_id, market_id))
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
                if not self._allow_open_trade:
                    return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

                results = self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, content)

            elif command == "trade-modify":
                if not self._allow_modify_trade:
                    return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

                results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, content)

            elif command == "trade-clean":
                if not self._allow_clean_trade:
                    return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

                results = self._strategy_service.command(Strategy.COMMAND_TRADE_CLEAN, content)

            else:
                results['messages'].append("Missing command.")
                results['error'] = True

        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_close_trade:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        content = json.loads(request.content.read().decode("utf-8"))

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, content)

        return json.dumps(results).encode("utf-8")


class HistoricalTradeRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._allow_view = monitor_service.has_strategy_view_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        trade_id = -1
        market_id = None

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

        if b'market-id' in request.args:
            try:
                market_id = request.args[b'market-id'][0].decode("utf-8")
            except ValueError:
                return NoResource("Incorrect market-id value")

        if trade_id > 0:
            results['data'] = None  # @todo
        else:
            # historical trades list
            history_trades = self._strategy_service.strategy().dumps_trades_history()

            # sort by last realized exit trade timestamp
            results['data'] = sorted(history_trades, key=lambda trade: trade['stats']['last-realized-exit-datetime'])

        return json.dumps(results).encode("utf-8")


class StrategyAlertRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service):
        super().__init__()

        self._strategy_service = strategy_service

        self._allow_view = monitor_service.has_strategy_view_perm
        self._allow_open_alert = monitor_service.has_strategy_trader_perm
        self._allow_clean_alert = monitor_service.has_strategy_trader_perm

    def render_GET(self, request):
        # list active alert or a specific alert
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        alert_id = -1
        market_id = None

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if b'alert' in request.args:
            try:
                alert_id = int(request.args[b'alert'][0].decode("utf-8"))
            except ValueError:
                return NoResource("Incorrect alert value")

        if b'market-id' in request.args:
            try:
                market_id = request.args[b'market-id'][0].decode("utf-8")
            except ValueError:
                return NoResource("Incorrect market-id value")

        if alert_id > 0:
            results['data'] = None  # @todo
        else:
            # current active alerts list
            results['data'] = self._strategy_service.strategy().dumps_active_alerts()

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

            if command == "alert-create":
                if not self._allow_open_alert:
                    return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

                results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True

        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_clean_alert:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        content = json.loads(request.content.read().decode("utf-8"))

        if content.get('action') != 'del-alert':
            return json.dumps({'error': True, 'messages': ['inconsistent-content']}).encode("utf-8")

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, content)

        return json.dumps(results).encode("utf-8")


class HistoricalAlertRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, view_service):
        super().__init__()

        self._view_service = view_service

        self._allow_view = monitor_service.has_strategy_view_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        alert_id = -1

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if b'alert' in request.args:
            try:
                alert_id = int(request.args[b'alert'][0].decode("utf-8"))
            except ValueError:
                return NoResource("Incorrect alert value")

        if alert_id > 0:
            # @todo
            results['data'] = None
        else:
            # triggered alert list
            history_alerts = self._view_service.dumps_alerts_history()

            # sort by last execution timestamp
            results['data'] = sorted(history_alerts, key=lambda alert: alert['timestamp'])

        return json.dumps(results).encode("utf-8")


class StrategyRegionRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service):
        super().__init__()

        self._strategy_service = strategy_service

        self._allow_view = monitor_service.has_strategy_view_perm
        self._allow_open_region = monitor_service.has_strategy_trader_perm
        self._allow_clean_region = monitor_service.has_strategy_trader_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        region_id = -1

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if b'region' in request.args:
            try:
                region_id = int(request.args[b'region'][0].decode("utf-8"))
            except ValueError:
                return NoResource("Incorrect trade value")

        if region_id > 0:
            # @todo
            results['data'] = None
        else:
            # strategy trader region for a specific market
            trade_regions = self._strategy_service.strategy().dumps_regions()

            # sort by last created timestamp
            results['data'] = sorted(trade_regions, key=lambda region: region['created'])

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

            if command == "region-create":
                if not self._allow_open_region:
                    return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

                results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True

        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")

    def render_DELETE(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_clean_region:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        content = json.loads(request.content.read().decode("utf-8"))

        if content.get('action') != 'del-region':
            return json.dumps({'error': True, 'messages': ['inconsistent-content']}).encode("utf-8")

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, content)

        return json.dumps(results).encode("utf-8")


class TraderRestAPI(resource.Resource):
    isLeaf = False

    def __init__(self, monitor_service, trader_service):
        super().__init__()

        self._trader_service = trader_service

        self._allow_view = monitor_service.has_strategy_view_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        trader = self._trader_service.trader()
        if trader is None:
            results = {
                'error': True,
                'messages': ["Undefined trader"],
                'data': None
            }
            return json.dumps(results).encode("utf-8")

        uri = request.uri.decode("utf-8").split('/')

        trader_name = self._trader_service.trader_name()

        asset_symbol = None

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if b'asset' in request.args:
            try:
                asset_symbol = int(request.args[b'asset'][0].decode("utf-8"))
            except ValueError:
                return NoResource("Incorrect asset value")

        if asset_symbol:
            # @todo
            results['data'] = None
        else:
            # asset list + margin
            results['data'] = trader.fetch_assets_balances()

        return json.dumps(results).encode("utf-8")

    def render_POST(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_chart:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        results = {
            'messages': [],
            'error': False
        }

        try:
            content = json.loads(request.content.read().decode("utf-8"))
            command = content.get('command', "")

            # subscribe/unsubscribe to trader market data
            if command == "subscribe-trade":
                results = self._trader_service.command(Trader.COMMAND_STREAM, content)
            elif command == "unsubscribe-trade":
                results = self._trader_service.command(Trader.COMMAND_STREAM, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True
        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")


class HistoricalSignalRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, view_service):
        super().__init__()

        self._view_service = view_service

        self._allow_view = monitor_service.has_strategy_view_perm

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_view:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        signal_id = -1

        results = {
            'error': False,
            'messages': [],
            'data': None
        }

        if b'signal' in request.args:
            try:
                signal_id = int(request.args[b'signal'][0].decode("utf-8"))
            except ValueError:
                return NoResource("Incorrect signal value")

        if signal_id > 0:
            # @todo
            results['data'] = None
        else:
            # triggered signal list
            history_signals = self._view_service.dumps_signals_history()

            # sort by last execution timestamp
            results['data'] = sorted(history_signals, key=lambda signal: signal['timestamp'])

        return json.dumps(results).encode("utf-8")


class Charting(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service, trader_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._allow_chart = monitor_service.has_strategy_chart_perm

        self._template = self.init_template()

    def init_template(self):
        data = ""

        try:
            with open("monitor/web/charting.html", "rb") as f:
                data = f.read()

        except FileNotFoundError:
            error_logger.error("Template charting.html was not found, not template available")

        return data

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_chart:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        uri = request.uri.split('/')
        result = {}

        # @todo fill template
        result = ""

        return json.dumps(result).encode("utf-8")

    def render_POST(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        if not self._allow_chart:
            return json.dumps({'error': True, 'messages': ['permission-not-allowed']}).encode("utf-8")

        results = {
            'messages': [],
            'error': False
        }

        try:
            content = json.loads(request.content.read().decode("utf-8"))
            command = content.get('command', "")

            if command == "subscribe-chart":
                results = self._strategy_service.command(Strategy.COMMAND_TRADER_STREAM, content)
            elif command == "unsubscribe-chart":
                results = self._strategy_service.command(Strategy.COMMAND_TRADER_STREAM, content)
            else:
                results['messages'].append("Missing command.")
                results['error'] = True
        except Exception as e:
            logger.debug(e)

        return json.dumps(results).encode("utf-8")


class StatusInfoRestAPI(resource.Resource):
    isLeaf = True

    def __init__(self, monitor_service, strategy_service, trader_service, watcher_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service
        self._watcher_service = watcher_service

    def render_GET(self, request):
        if not check_auth_token(request):
            return json.dumps({'error': True, 'messages': ['invalid-auth-token']}).encode("utf-8")

        trader = self._trader_service.trader()
        if trader is None:
            results = {
                'error': True,
                'messages': ["Undefined trader"],
                'data': None
            }
            return json.dumps(results).encode("utf-8")

        trader_data = {
            'name': trader.name,
            'connected': trader.connected,
        }

        watchers_data = []
        watchers_ids = self._watcher_service.watchers_ids()

        for watcher_id in watchers_ids:
            watcher = self._watcher_service.watcher(watcher_id)
            watchers_data.append({
                    'name': watcher.name,
                    'connected': watcher.connected,
                })

        results = {
            'error': False,
            'messages': [],
            'data': {
                'trader': trader_data,
                'watchers': watchers_data
            }
        }

        return json.dumps(results).encode("utf-8")


class AllowedIPOnlyFactory(server.Site):

    def buildProtocol(self, addr):
        logger.debug("%s %s %s" % (HttpRestServer.DENIED_IPS, addr.host, HttpRestServer.ALLOWED_IPS))
        if HttpRestServer.DENIED_IPS and addr.host in HttpRestServer.DENIED_IPS:
            return None

        if HttpRestServer.ALLOWED_IPS and addr.host in HttpRestServer.ALLOWED_IPS:
            return super().buildProtocol(addr)

        if HttpRestServer.ALLOWED_IPS is None and HttpRestServer.DENIED_IPS is None:
            # allow any
            return super().buildProtocol(addr)
          
        return None


class HttpRestServer(object):

    ALLOWED_IPS = None
    DENIED_IPS = None

    def __init__(self, host, port, api_key, api_secret, monitor_service,
                 strategy_service, trader_service, watcher_service, view_service):
        self._listener = None

        self._host = host
        self._port = port

        self.__api_key = api_key
        self.__api_secret = api_secret

        self._monitor_service = monitor_service
        self._strategy_service = strategy_service
        self._trader_service = trader_service
        self._watcher_service = watcher_service
        self._view_service = view_service

    def start(self):
        root = static.File("monitor/web")
        api = resource.Resource()
        root.putChild(b"api", api)

        api_v1 = resource.Resource()
        api.putChild(b"v1", api_v1)

        # auth
        api_v1.putChild(b"auth", AuthRestAPI(self._monitor_service, self.__api_key, self.__api_secret))

        # strategy
        strategy_api = StrategyInfoRestAPI(self._monitor_service, self._strategy_service, self._trader_service)
        api_v1.putChild(b"strategy", strategy_api)

        # strategy instrument
        instrument_api = InstrumentRestAPI(self._monitor_service, self._strategy_service, self._trader_service)
        strategy_api.putChild(b"instrument", instrument_api)

        # strategy trade
        trade_api = StrategyTradeRestAPI(self._monitor_service, self._strategy_service, self._trader_service)
        strategy_api.putChild(b"trade", trade_api)

        # strategy trader history
        historical_trade_api = HistoricalTradeRestAPI(self._monitor_service, self._strategy_service,
                                                      self._trader_service)
        strategy_api.putChild(b"historical", historical_trade_api)

        # strategy trader alert
        alert_api = StrategyAlertRestAPI(self._monitor_service, self._strategy_service)
        strategy_api.putChild(b"alert", alert_api)

        # strategy trader alert history
        historical_alert_api = HistoricalAlertRestAPI(self._monitor_service, self._view_service)
        strategy_api.putChild(b"historical-alert", historical_alert_api)

        # strategy trader region
        region_api = StrategyRegionRestAPI(self._monitor_service, self._strategy_service)
        strategy_api.putChild(b"region", region_api)

        # trader
        trader_api = TraderRestAPI(self._monitor_service, self._trader_service)
        api_v1.putChild(b"trader", trader_api)

        # strategy signal history
        historical_signal_api = HistoricalSignalRestAPI(self._monitor_service, self._view_service)
        strategy_api.putChild(b"historical-signal", historical_signal_api)

        # monitor
        monitor_api = resource.Resource()
        api_v1.putChild(b"monitor", monitor_api)

        status_api = StatusInfoRestAPI(self._monitor_service, self._strategy_service, self._trader_service,
                                       self._watcher_service)
        monitor_api.putChild(b"status", status_api)

        # charting
        strategy_api.putChild(b"chart", Charting(self._monitor_service, self._strategy_service, self._trader_service))

        factory = AllowedIPOnlyFactory(root)
        factory.sessionFactory = LongSession

        def listen(_server, _port, _factory):
            _server._listener = reactor.listenTCP(_port, _factory)
            # if _server._listener:
            #     MonitorService.use_reactor(installSignalHandlers=False)

        reactor.callFromThread(listen, self, self._port, factory)      

    def stop(self):
        if self._listener:
            self._listener.stopListening()
            self._listener = None

            MonitorService.release_reactor()
