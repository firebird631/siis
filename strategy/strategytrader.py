# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trader base class.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .strategy import Strategy
    from .alert.alert import Alert
    from .region.region import Region
    from trader.trader import Trader

import pathlib
import threading
import time
import traceback

from datetime import datetime
from typing import Union, Optional, List

from strategy.trade.strategyassettrade import StrategyAssetTrade
from strategy.trade.strategyindmargintrade import StrategyIndMarginTrade
from strategy.trade.strategymargintrade import StrategyMarginTrade
from strategy.trade.strategypositiontrade import StrategyPositionTrade
from strategy.trade.strategytrade import StrategyTrade

from .strategytradercontext import StrategyTraderContext, StrategyTraderContextBuilder

from .indicator.models import Limits

from instrument.instrument import Instrument

from common.utils import timeframe_to_str
from strategy.strategysignal import StrategySignal
from terminal.terminal import Terminal

from database.database import Database
from trader.order import Order

import logging
logger = logging.getLogger('siis.strategy.trader')
error_logger = logging.getLogger('siis.error.strategy.trader')
traceback_logger = logging.getLogger('siis.traceback.strategy.trader')


class StrategyTrader(object):
    """
    A strategy can manage multiple instrument. Strategy trader is on of the managed instruments.
    """
    MARKET_TYPE_MAP = {
        'asset': Instrument.TRADE_SPOT,
        'spot': Instrument.TRADE_SPOT,
        'margin': Instrument.TRADE_MARGIN,
        'position': Instrument.TRADE_POSITION,
        'ind-margin': Instrument.TRADE_IND_MARGIN,
    }

    REPORTING_NONE = 0
    REPORTING_VERBOSE = 1

    REPORTING_MAP = {
        'none': REPORTING_NONE,
        'verbose': REPORTING_VERBOSE,
    }

    _trade_context_builder: Union[StrategyTraderContextBuilder, Any, None]

    def __init__(self, strategy: Strategy, instrument: Instrument):
        self.strategy = strategy
        self.instrument = instrument

        self._mutex = threading.RLock()  # activity, global locker, region locker, instrument locker
        self._activity = True
        self._affinity = 5          # based on a linear scale [0..100]

        self.max_trades = 0

        self._initialized = 1       # initiate data before running, 1 waited, 2 in progress, 0 normal
        self._checked = 1           # check trades/orders/positions, 1 waited, 2 in progress, 0 normal

        self._limits = Limits()     # price and timestamp ranges

        self._preprocessing = 1     # 1 waited, 2 to 4 in progress, 0 normal
        self._preprocess_depth = 0  # in second, need of preprocessed data depth of history
        self._preprocess_streamer = None       # current tick or quote streamer
        self._preprocess_from_timestamp = 0.0  # preprocessed date from this timestamp to limit last timestamp

        self._bootstrapping = 1      # 1 waited, 2 in progress, 0 normal, done from loaded OHLCs history

        self._processing = False   # True during processing

        self._trade_mutex = threading.RLock()   # trades locker
        self._trades = []
        self._next_trade_id = 1

        self._regions = []
        self._next_region_id = 1

        self._alerts = []
        self._next_alert_id = 1

        self._handlers = {}  # installed handlers per context (some can be shared)

        self._global_streamer = None
        self._trade_entry_streamer = None
        self._trade_update_streamer = None
        self._trade_exit_streamer = None
        self._signal_streamer = None
        self._alert_streamer = None
        self._region_streamer = None

        self._reporting = StrategyTrader.REPORTING_NONE
        self._report_filename = None

        self._stats = {
            'perf': 0.0,       # initial
            'worst': 0.0,      # worst trade lost
            'best': 0.0,       # best trade profit
            'high': 0.0,       # if closed at best price
            'low': 0.0,        # if closed at worst price
            'failed': [],      # failed terminated trades
            'success': [],     # success terminated trades
            'roe': [],         # return to equity trades
            'cont-win': 0,     # contiguous win trades
            'cont-loss': 0,    # contiguous loss trades
            'closed': 0,       # num of closed trades
            'rpnl': 0.0        # realize profit and loss
        }

        self._trade_context_builder = None

    #
    # properties
    #

    @property
    def is_timeframes_based(self):
        return False

    @property
    def is_tickbars_based(self):
        return False

    @property
    def mutex(self):
        return self._mutex

    def check_option(self,
                     option: Union[str, None],
                     value: Union[int, float, str, None]) -> Union[str, None]:
        """
        Check for a local option. Validate the option name and value format.
        @return None or a str with the message of the error.
        """
        if option is None or type(option) is not str:
            return "Invalid option"

        if value is None or type(value) not in (int, float, str):
            return "Invalid value"

        keys = option.split('.')

        for k in keys:
            if not k:
                return "Invalid option format"

        if keys[0] not in ('max-trades', 'context', 'mode'):
            return "Invalid option %s" % keys[0]

        if keys[0] == 'context':
            if len(keys) < 2:
                return "Context must be named"

            context = self.retrieve_context(keys[1])
            if context is None:
                return "Unknown context %s" % keys[1]

            if len(keys) == 3:
                if keys[2] not in ('max-trades', 'mode'):
                    return "Invalid option %s" % keys[2]

                if context.trade_quantity_type == context.TRADE_QUANTITY_MANAGED:
                    return "Forbidden, changes on this context are locked by a handler."

                if keys[2] == 'max-trades':
                    try:
                        v = int(value)
                        if not 0 <= v <= 999:
                            return "Value must be between 0..999"
                    except ValueError:
                        return "Value must be integer"

                elif keys[2] == 'mode':
                    if value not in context.MODE:
                        return "Unsupported value for mode"

            elif len(keys) == 4:
                if keys[2] in ('stop-loss', 'dynamic-stop-loss', 'take-profit', 'dynamic-take-profit'):
                    if keys[3] not in ('distance', 'orientation', 'depth', 'multi', 'timeout-distance'):
                        return "Invalid %s option %s" % (keys[2], keys[3])

                    if keys[3] == 'distance':
                        try:
                            if type(value) is str and value.endswith('%'):
                                v = float(value[:-1])
                                if v <= -100:
                                    return "Distance must not exceed 100%"
                            elif type(value) is str and value.endswith('pip'):
                                v = float(value[:-3])
                            else:
                                v = float(value)
                        except ValueError:
                            return "Distance must be a float with an optional suffix '%' or 'pip'"

                    elif keys[3] == 'timeout-distance':
                        try:
                            if type(value) is str and value.endswith('%'):
                                v = float(value[:-1])
                                if v <= -100:
                                    return "Timeout distance must not exceed 100%"
                            elif type(value) is str and value.endswith('pip'):
                                v = float(value[:-3])
                            else:
                                v = float(value)
                        except ValueError:
                            return "Timeout distance must be a float with an optional suffix '%' or 'pip'"

                    elif keys[3] == "multi":
                        if value not in (0, 1):
                            return "Multi must be 0 or 1"

                    elif keys[3] == "depth":
                        try:
                            v = int(value)
                        except ValueError:
                            return "Depth must be an integer"

                    elif keys[3] == "orientation":
                        choices = ('up', 'upper', 'high', 'higher', 'dn', 'down', 'low', 'lower', 'both')
                        if value not in choices:
                            return "Orientation must be one of %s" % ' '.join(choices)

                elif keys[2] == 'trade-quantity':
                    if keys[3] not in ('type', 'quantity', 'step'):
                        return "Invalid %s option %s" % (keys[2], keys[3])

                    if context.trade_quantity_type == context.TRADE_QUANTITY_MANAGED:
                        return "Forbidden, changes on this context are locked by a handler."

                    if keys[3] == 'type':
                        # other choices use keys[4]
                        choices = ('normal', 'reinvest-max-last')
                        if value not in choices:
                            return "Type must be one of %s" % ' '.join(choices)

                    elif keys[3] == 'quantity':
                        try:
                            v = float(value)
                            if v < 0.0:
                                return "Value must be greater or equal to zero"
                        except ValueError:
                            return "Value must be float"

                    elif keys[3] == 'step':
                        try:
                            v = float(value)
                            if v < 0.0:
                                return "Value must be greater or equal to zero"
                        except ValueError:
                            return "Value must be float"
                else:
                    return "Invalid option %s" % keys[2]

            elif len(keys) == 4:
                if keys[2] == 'trade-quantity':
                    if keys[3] not in ('type',):
                        return "Invalid %s option %s" % (keys[2], keys[3])

                    if context.trade_quantity_type == context.TRADE_QUANTITY_MANAGED:
                        return "Forbidden, changes on this context are locked by a handler."

                    if keys[3] == 'type':
                        # other choices use keys[3]
                        choices = ('specific', 'increment-step')
                        if value not in choices:
                            return "Type must be one of %s" % ' '.join(choices)

        elif keys[0] == 'max-trades':
            try:
                int(value)
            except ValueError:
                return "Value must be integer"

        return None

    def set_option(self,
                   option: Union[str, None],
                   value: Union[int, float, str, None]) -> bool:
        """
        Set for a local option. Validate the option name and value format and apply it.
        @return True if the option was modified.
        """
        if option is None or type(option) is not str:
            return False

        if value is None or type(value) not in (int, float, str):
            return False

        keys = option.split('.')

        for k in keys:
            if not k:
                return False

        if keys[0] not in ('max-trades', 'context', 'mode'):
            return False

        if keys[0] == 'context':
            if len(keys) < 2:
                return False

            context = self.retrieve_context(keys[1])
            if context is None:
                return False

            if len(keys) == 3:
                if keys[2] not in ('max-trades', 'mode'):
                    return False

                if context.trade_quantity_type == context.TRADE_QUANTITY_MANAGED:
                    # in this mode it must be managed by its handler
                    return False

                if keys[2] == 'max-trades':
                    try:
                        v = int(value)
                        if 0 <= v <= 999:
                            context.max_trades = v
                            return True
                        else:
                            return False
                    except ValueError:
                        return False

                elif keys[2] == 'mode':
                    if value not in context.MODE:
                        return False

                    context.mode = context.MODE[value]
                    return True

            elif len(keys) == 4:
                if keys[2] in ('stop-loss', 'dynamic-stop-loss', 'take-profit', 'dynamic-take-profit'):
                    if keys[3] not in ('distance', 'orientation', 'depth', 'multi', 'timeout-distance'):
                        return False

                    # retrieve the related target
                    ex_entry_exit = None

                    if keys[2] == 'stop-loss':
                        if not hasattr(context, 'stop_loss'):
                            return False

                        ex_entry_exit = context.stop_loss

                    if keys[2] == 'dynamic-stop-loss':
                        if not hasattr(context, 'dynamic_stop_loss'):
                            return False

                        ex_entry_exit = context.dynamic_stop_loss

                    if keys[2] == 'take-profit':
                        if not hasattr(context, 'take_profit'):
                            return False

                        ex_entry_exit = context.take_profit

                    if keys[2] == 'dynamic-take-profit':
                        if not hasattr(context, 'dynamic_take_profit'):
                            return False

                        ex_entry_exit = context.dynamic_take_profit

                    if not ex_entry_exit:
                        return False

                    # update value
                    if keys[3] == 'distance':
                        try:
                            if type(value) is str and value.endswith('%'):
                                v = float(value[:-1])
                                if v <= -100:
                                    return False
                            elif type(value) is str and value.endswith('pip'):
                                v = float(value[:-3])
                            else:
                                v = float(value)
                        except ValueError:
                            return False

                        if not hasattr(ex_entry_exit, 'modify_distance'):
                            return False

                        ex_entry_exit.modify_distance(self, value)
                        return True

                    elif keys[3] == 'timeout-distance':
                        try:
                            if type(value) is str and value.endswith('%'):
                                v = float(value[:-1])
                                if v <= -100:
                                    return False
                            elif type(value) is str and value.endswith('pip'):
                                v = float(value[:-3])
                            else:
                                v = float(value)
                        except ValueError:
                            return False

                        if not hasattr(ex_entry_exit, 'modify_timeout_distance'):
                            return False

                        ex_entry_exit.modify_timeout_distance(self, value)
                        return True

                    elif keys[3] == "multi":
                        if value not in (0, 1):
                            return False

                        if not hasattr(ex_entry_exit, 'multi'):
                            return False

                        ex_entry_exit.multi = True if value else False
                        return True

                    elif keys[3] == "depth":
                        try:
                            v = int(value)
                        except ValueError:
                            return False

                        if not hasattr(ex_entry_exit, 'depth'):
                            return False

                        ex_entry_exit.depth = v
                        return True

                    elif keys[3] == "orientation":
                        if value not in ('up', 'upper', 'high', 'higher', 'dn', 'down', 'low', 'lower', 'both'):
                            return False

                        if not hasattr(ex_entry_exit, 'modify_orientation'):
                            return False

                        ex_entry_exit.modify_orientation(value)
                        return True

                elif keys[2] == 'trade-quantity':
                    if keys[3] not in ('type', 'quantity', 'step'):
                        return False

                    if context.trade_quantity_type == context.TRADE_QUANTITY_MANAGED:
                        # this mode is globally managed and cannot be locally modified
                        return False

                    if keys[3] == 'type':
                        # other choices use keys[4]
                        if value not in ('normal', 'reinvest-max-last'):
                            return False

                        try:
                            quantity = float(value)
                        except ValueError:
                            return False

                        if quantity < 0:
                            return False

                        return context.modify_trade_quantity_type(self.instrument, value, quantity)

                    elif keys[3] == 'quantity':
                        try:
                            quantity = float(value)
                        except ValueError:
                            return False

                        return context.modify_trade_quantity(quantity)

                    elif keys[3] == 'step':
                        try:
                            step = float(value)
                        except ValueError:
                            return False

                        return context.modify_trade_step(step)

                else:
                    return False

            elif len(keys) == 4:
                if keys[2] == 'trade-quantity':
                    if keys[3] not in ('type',):
                        return False

                    if context.trade_quantity_type == context.TRADE_QUANTITY_MANAGED:
                        # this mode is globally managed and cannot be locally modified
                        return False

                    if keys[3] == 'type':
                        # other choices use keys[3]
                        if keys[4] not in ('specific', 'increment-step'):
                            return False

                        try:
                            quantity = float(value)
                        except ValueError:
                            return False

                        if quantity < 0:
                            return False

                        return context.modify_trade_quantity_type(self.instrument, keys[4], quantity)

        elif keys[0] == 'max-trades':
            try:
                v = int(value)
                if 0 <= v <= 999:
                    self.max_trades = v
                    return True
                else:
                    return False
            except ValueError:
                return False

        return False

    #
    # processing
    #

    @property
    def activity(self) -> bool:
        """
        Strategy trader Local state.
        """
        return self._activity

    def set_activity(self, status: bool):
        """
        Enable/disable execution of the automated orders.
        """
        self._activity = status

    @property
    def affinity(self) -> int:
        """
        Strategy trader affinity rate.
        """
        return self._affinity

    @affinity.setter
    def affinity(self, affinity: int):
        """
        Set strategy trader affinity rate.
        """
        self._affinity = affinity

    def restart(self):
        """
        Needed on a reconnection to reset some states.
        """
        with self._mutex:
            self._initialized = 1
            self._checked = 1
            self._preprocessing = 1
            self._bootstrapping = 1

    def recheck(self):
        """
        Query for recheck any trades of the trader.
        """
        with self._mutex:
            self._checked = 1

    #
    # pre-processing
    #

    def preprocess_load_cache(self, from_date: datetime, to_date: datetime):
        """
        Override this method to load the cached data before performing preprocess.
        """
        pass

    def preprocess(self, trade: StrategyTrade):
        """
        Override this method to preprocess trade per trade each most recent data than the cache.
        """
        pass

    def preprocess_store_cache(self, from_date: datetime, to_date: datetime):
        """
        Override this method to store in cache the preprocessed data.
        """
        pass

    #
    # processing
    #

    def prepare(self):
        """
        Prepare before entering live or backtest data stream.
        Prepare indicators, signals states and flags.

        It is called before bootstrap iterations and before process iterations.
        """
        pass

    def bootstrap(self, timestamp: float):
        """
        Override this method to do all the initial strategy work using the preloaded OHLCs history.
        No trade must be done here, but signal pre-state could be computed.

        This is useful for strategies having pre trigger signal, in way to don't miss the comings
        signals validations.
        """
        pass

    def process(self, timestamp: float):
        """
        Override this method to do her all the strategy work.
        You must call the update_trades method during the process in way to manage the trades.

        @param timestamp Current timestamp (or in backtest the processed time in past).
        """
        pass

    def check_trades(self, timestamp: float):
        """
        Recheck actives or pending trades. Useful after a reconnection.
        """
        with self._mutex:
            if self._checked != 1:
                # only if waiting to check trades
                return

            # process
            self._checked = 2

        trader = self.strategy.trader()

        if not trader.paper_mode:
            # do not process in paper-mode
            with self._trade_mutex:
                for trade in self._trades:
                    try:
                        # check and update from order info orders/position/quantity
                        result = trade.check(trader, self.instrument)

                        # do not repair automatically because of free quantity can be necessary to another trade
                        # and could results to error another trade

                        # if result == 0:
                        #     # try to repair it else stay in error status
                        #     trade.repair(trader, self.instrument)

                        time.sleep(1.0)  # do not saturate API

                    except Exception as e:
                        error_logger.error(repr(e))
                        traceback_logger.error(traceback.format_exc())

        with self._mutex:
            # done
            self._checked = 0

    def terminate(self):
        """
        Delete any non realized trades (new or open) or remaining closed but not closing.
        """
        trader = self.strategy.trader()
        mutated = False
        trades_list = []

        with self._mutex:
            with self._trade_mutex:
                for trade in self._trades:
                    if trade.can_delete() or trade.is_closed() or not trade.is_active():
                        # cleanup if necessary before deleting the trade related refs
                        if trade.remove(trader, self.instrument):
                            mutated = True
                        else:
                            # error during canceling orders, potential API or response error : keep for persistence
                            trades_list.append(trade)
                    else:
                        # keep for persistence
                        trades_list.append(trade)

                # updated trade list, the ones we would save
                if mutated:
                    self._trades = trades_list

    #
    # persistence
    #

    def save(self):
        """
        Trader and trades persistence (might occurs only for live mode on real accounts).
        @note Must be called only after terminate.
        """
        trader = self.strategy.trader()

        with self._mutex:
            with self._trade_mutex:
                for trade in self._trades:
                    t_data = trade.dumps()
                    ops_data = [operation.dumps() for operation in trade.operations]

                    # store per trade
                    Database.inst().store_user_trade((
                        trader.name, trader.account.name, self.instrument.market_id,
                        self.strategy.identifier, trade.id, trade.trade_type, t_data, ops_data))

            # dumps of trader data, regions and alerts
            trader_data = {
                'affinity': self._affinity,
                # @todo context data or into a distinct column
            }

            regions_data = [region.dumps() for region in self._regions]
            alerts_data = [alert.dumps() for alert in self._alerts]

            Database.inst().store_user_trader((
                trader.name, trader.account.name, self.instrument.market_id,
                self.strategy.identifier, self.activity, trader_data, regions_data, alerts_data))

    def dumps(self) -> dict:
        """
        Trader state, context and trades persistence.
        """
        trader = self.strategy.trader()

        trades_data = []
        contexts_data = []  # @todo

        with self._mutex:
            with self._trade_mutex:
                for trade in self._trades:
                    t_data = trade.dumps()
                    t_data['operations'] = [operation.dumps() for operation in trade.operations]

                    trades_data.append(t_data)

            # dumps of trader data, regions and alerts
            trader_data = {
                'activity': self._activity,
                'affinity': self._affinity,
                'next-trade-id': self._next_trade_id,
                'next-alert-id': self._next_alert_id,
                'next-region-id': self._next_region_id,
                'contexts': contexts_data
            }

            regions_data = [region.dumps() for region in self._regions]
            alerts_data = [alert.dumps() for alert in self._alerts]

        return {
            'trader-name': trader.name,
            'account-name': trader.account.name,
            'strategy': self.strategy.identifier,
            'symbol': self.instrument.market_id,
            'market-id': self.instrument.market_id,
            'trader': trader_data,
            'trades': trades_data,
            'regions': regions_data,
            'alerts': alerts_data
        }

    def loads(self, data: dict, regions: List[dict], alerts: List[dict], force_id: bool = False):
        """
        Load strategy trader state and regions.
        @param data: Strategy-trader data dump dict
        @param regions: list of data dump dict of regions
        @param alerts: list of data dump dict of alerts
        @param force_id: To reuse original id, take care to update next_alert_id and next_region_id
            and to don't override.
        """
        # trader data
        if 'activity' in data and type(data['activity']) is int:
            self._activity = data['activity']

        if 'affinity' in data and type(data['affinity']) is int:
            self._affinity = data['affinity']

        # specific data
        if 'next-trade-id' in data and type(data['next-trade-id']) is int:
            self._next_trade_id = data['next-trade-id']

        if 'next-alert-id' in data and type(data['next-alert-id']) is int:
            self._next_alert_id = data['next-alert-id']

        if 'next-region-id' in data and type(data['next-region-id']) is int:
            self._next_region_id = data['next-region-id']

        # contexts data
        # @todo

        # instantiates the regions
        for r in regions:
            if r['name'] in self.strategy.service.regions:
                try:
                    # instantiate the region
                    region = self.strategy.service.regions[r['name']](0, 0, 0, 0)
                    region.loads(r)

                    if region.check():
                        if force_id:
                            with self._mutex:
                                self._regions.append(region)
                        else:
                            self.add_region(region)
                    else:
                        error_logger.error("During loads, region checking error %s" % r['name'])
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                error_logger.error("During loads, unsupported region %s" % r['name'])

        # instantiate the alerts
        for a in alerts:
            if a['name'] in self.strategy.service.alerts:
                try:
                    # instantiate the alert
                    alert = self.strategy.service.alerts[a['name']](0, 0)
                    alert.loads(a)

                    if alert.check():
                        if force_id:
                            with self._mutex:
                                self._alerts.append(alert)
                        else:
                            self.add_alert(alert)
                    else:
                        error_logger.error("During loads, alert checking error %s" % a['name'])
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                error_logger.error("During loads, unsupported alert %s" % a['name'])

    def loads_trade(self, trade_id: int, trade_type: int, data: dict, operations: List[dict],
                    check: bool = False, force_id: bool = False):
        """
        Load a strategy trader trade and its operations.
        There is many scenarios where the trade state changed, trade executed, order modified or canceled...
        @param trade_id: Original trade id
        @param trade_type: Trade type integer constant
        @param data: Trade data dump dict
        @param operations: Trade operation data dump dict into a list
        @param check: Check trade related orders and position according to the trader
        @param force_id: To reuse original id, take care to update next_trade_id and to don't override.
        """
        # trade builder
        if trade_type == StrategyTrade.TRADE_BUY_SELL:
            trade = StrategyAssetTrade(0)
        elif trade_type == StrategyTrade.TRADE_MARGIN:
            trade = StrategyMarginTrade(0)
        elif trade_type == StrategyTrade.TRADE_POSITION:
            trade = StrategyPositionTrade(0)
        elif trade_type == StrategyTrade.TRADE_IND_MARGIN:
            trade = StrategyIndMarginTrade(0)
        else:
            error_logger.error("During loads, unsupported trade type %i" % trade_type)
            return

        trade.loads(data, self, self._trade_context_builder)

        logger.debug("Load trade %s:%s" % (self.instrument.symbol, trade_id))

        # operations
        for op in operations:
            if op['name'] in self.strategy.service.tradeops:
                try:
                    operation = self.strategy.service.tradeops[op['name']]()
                    operation.loads(op)

                    if operation.check(trade):
                        # append the operation to the trade
                        trade.add_operation(operation)
                    else:
                        error_logger.error("During loads, trade operation checking error %s" % op['name'])
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                error_logger.error("During loads, trade operation checking error %s" % op['name'])

        if check:
            # check the trade before to add it to prevent sides effects cause by the strategy behavior
            trade.check(self.strategy.trader(), self.instrument)

        # and finally add the trade
        if force_id:
            # conserve original trade id
            with self._trade_mutex:
                self._trades.append(trade)
        else:
            # add and assign a new trade id
            self.add_trade(trade)

    def loads_alert(self, alert_id: int, alert_type: int, data: dict, force_id: bool = False):
        """
        Load a strategy trader alert.
        @param alert_id Above 0 original alert identifier
        @param alert_type String type name of the alert to instantiate (optional use data['name'])
        @param data Loaded data a dict
        @param force_id: To reuse original id, take care to update next_alert_id and to don't override.
        """
        alert_name = data.get('name')

        if not alert_name:
            error_logger.error("During loads, undefined alert %i type name" % alert_id)
            return

        if alert_name not in self.strategy.service.alerts:
            error_logger.error("During loads, unsupported alert %s %i" % (alert_name, alert_id))

        try:
            # instantiate the alert
            alert = self.strategy.service.alerts[alert_name](0, 0)
            alert.loads(data)

            if alert.check():
                if force_id:
                    with self._mutex:
                        self._alerts.append(alert)
                else:
                    self.add_alert(alert)
            else:
                error_logger.error("During loads, alert checking error %s %i" % (alert_name, alert_id))
        except Exception as e:
            error_logger.error(repr(e))

    def loads_region(self, region_id: int, region_type: int, data: dict, force_id: bool = False):
        """
        Load a strategy trader region.
        @param region_id Above 0 original region identifier
        @param region_type String type name of the region to instantiate (optional use data['name'])
        @param data Loaded data a dict
        @param force_id: To reuse original id, take care to update next_region_id and to don't override.
        """
        region_name = data.get('name')

        if not region_name:
            error_logger.error("During loads, undefined region %i type name" % region_id)
            return

        if region_name not in self.strategy.service.regions:
            error_logger.error("During loads, unsupported region %s %i" % (region_name, region_id))

        try:
            # instantiate the region
            region = self.strategy.service.regions[region_name](0, 0)
            region.loads(data)

            if region.check():
                if force_id:
                    with self._mutex:
                        self._regions.append(region)
                else:
                    self.add_region(region)
            else:
                error_logger.error("During loads, region checking error %s %i" % (region_name, region_id))
        except Exception as e:
            error_logger.error(repr(e))

    #
    # order/position slot
    #

    def order_signal(self, signal_type: int, data: dict):
        """
        Update quantity/filled on a trade, deleted or canceled.
        """
        with self._trade_mutex:
            try:
                for trade in self._trades:
                    # update each trade relating the order (might be a unique)
                    order_id = data[1]['id'] if type(data[1]) is dict else data[1]
                    ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                    if trade.is_target_order(order_id, ref_order_id):
                        trade.order_signal(signal_type, data[1], data[2] if len(data) > 2 else None, self.instrument)

                        # notify update only if trade is not closed by the signal
                        if not trade.is_closed():
                            self.notify_trade_update(self.strategy.timestamp, trade)

            except Exception as e:
                error_logger.error(traceback.format_exc())
                error_logger.error(repr(e))

    def position_signal(self, signal_type: int, data: dict):
        """
        Update quantity/filled on a trade, delete or cancel.
        """
        with self._trade_mutex:
            try:
                for trade in self._trades:
                    # update each trade relating the position (could be many)
                    position_id = data[1]['id'] if type(data[1]) is dict else data[1]
                    ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                    if trade.is_target_position(position_id, ref_order_id):
                        trade.position_signal(signal_type, data[1], data[2] if len(data) > 2 else None, self.instrument)

                        # notify update only if trade is not closed by the signal
                        if not trade.is_closed():
                            self.notify_trade_update(self.strategy.timestamp, trade)

            except Exception as e:
                error_logger.error(traceback.format_exc())
                error_logger.error(repr(e))

    #
    # trade
    #

    @property
    def trade_mutex(self) -> threading.RLock:
        return self._trade_mutex

    @property
    def trades(self) -> List[StrategyTrade]:
        return self._trades

    def add_trade(self, trade: StrategyTrade):
        """
        Add a new trade.
        """
        if not trade:
            return False

        with self._trade_mutex:
            trade.id = self._next_trade_id
            self._next_trade_id += 1

            self._trades.append(trade)

    def remove_trade(self, trade: StrategyTrade):
        """
        Remove an existing trade.
        """
        if not trade:
            return False

        with self._trade_mutex:
            self._trades.remove(trade)

    def has_trades(self) -> bool:
        """
        Is pending or active trades.
        """
        with self._trade_mutex:
            return len(self._trades) > 0

        return False

    def list_trades(self) -> List[StrategyTrade]:
        """
        List of ids of pending and actives trades.
        """
        results = []

        with self._trade_mutex:
            for trade in self._trades:
                results.append(trade.id)

        return results

    def dumps_trades_update(self) -> List[dict]:
        """
        Dumps the update notify state of each existing trades.
        """
        results = []

        with self._trade_mutex:
            for trade in self._trades:
                results.append(trade.dumps_notify_update(self.strategy.timestamp, self))

        return results

    def dumps_trades_history(self) -> List[dict]:
        """
        Dumps the historical record of each historical trades. Not sorted.
        """
        with self._mutex:
            results = self._stats['success'] + self._stats['failed'] + self._stats['roe']

        return results

    def dumps_active_alerts(self) -> List[dict]:
        """
        Dumps the active alerts. Not sorted.
        """
        results = []

        with self._mutex:
            for alert in self._alerts:
                alert_dumps = alert.dumps()
                alert_dumps['market-id'] = self.instrument.market_id
                alert_dumps['symbol'] = self.instrument.symbol

                results.append(alert_dumps)

        return results

    def update_trades(self, timestamp: float):
        """
        Update managed trades per instruments and delete terminated trades.
        """
        if not self._trades:
            return

        trader = self.strategy.trader()

        #
        # for each trade check if the TP or SL is reached and trigger if necessary
        #

        with self._trade_mutex:
            for trade in self._trades:

                # cannot manage a trade in state error
                if trade.is_error():
                    continue

                #
                # managed operation
                #

                if trade.has_operations():
                    mutated = False

                    for operation in trade.operations:
                        mutated |= operation.test_and_operate(trade, self, trader)

                    if mutated:
                        trade.cleanup_operations()

                #
                # active trade
                #

                if trade.is_active():
                    # for statistics usage
                    trade.update_stats(self.instrument, timestamp)

                    # stream
                    self.stream_trade_update(timestamp, trade)

                #
                # asset trade
                #

                if trade.trade_type == StrategyTrade.TRADE_BUY_SELL:
                    if trade.is_closed():
                        continue

                    # process only on active trades
                    if not trade.is_active():
                        # @todo timeout if not filled before condition...
                        continue

                    if trade.is_closing():
                        continue

                    if not self.instrument.tradeable:
                        continue

                    if trade.is_dirty:
                        # entry quantity changed need to update the exits orders
                        trade.update_dirty(trader, self.instrument)

                    # potential order exec close price (always close a long)
                    close_exec_price = self.instrument.close_exec_price(Order.LONG)

                    if (trade.tp > 0) and (close_exec_price >= trade.tp) and not trade.has_limit_order():
                        # take profit trigger stop, close at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_TAKE_PROFIT_MARKET

                    elif (trade.sl > 0) and (close_exec_price <= trade.sl) and not trade.has_stop_order():
                        # stop loss trigger stop, close at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

                #
                # margin trade
                #

                elif trade.trade_type in (StrategyTrade.TRADE_MARGIN, StrategyTrade.TRADE_POSITION,
                                          StrategyTrade.TRADE_IND_MARGIN):
                    if trade.is_closed():
                        continue

                    # process only on active trades
                    if not trade.is_active():
                        # @todo timeout if not filled before condition...
                        continue

                    if trade.is_closing():
                        continue

                    if not self.instrument.tradeable:
                        continue

                    if trade.is_dirty:
                        # entry quantity changed need to update the exits orders
                        trade.update_dirty(trader, self.instrument)

                    # potential order exec close price
                    close_exec_price = self.instrument.close_exec_price(trade.direction)

                    if (trade.tp > 0) and ((trade.direction > 0 and close_exec_price >= trade.tp) or (
                            trade.direction < 0 and close_exec_price <= trade.tp)) and not trade.has_limit_order():
                        # close in profit at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_TAKE_PROFIT_MARKET

                    elif (trade.sl > 0) and ((trade.direction > 0 and close_exec_price <= trade.sl) or (
                            trade.direction < 0 and close_exec_price >= trade.sl)) and not trade.has_stop_order():
                        # close a long or a short position at stop-loss level at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

        #
        # remove terminated, rejected, canceled and empty trades
        #

        mutated = False

        with self._trade_mutex:
            for trade in self._trades:
                if trade.can_delete():
                    mutated = True

                    # cleanup if necessary before deleting the trade related refs
                    # but there might be no order or position remaining at this level
                    trade.remove(trader, self.instrument)

                    # record the trade for analysis and study
                    if not trade.is_canceled():
                        # last update of stats before logging (useless because no longer active and done before)
                        trade.update_stats(self.instrument, timestamp)

                        # realized profit/loss
                        profit_loss = trade.profit_loss - trade.entry_fees_rate() - trade.exit_fees_rate()

                        best_pl = (trade.best_price() - trade.entry_price if trade.direction > 0 else
                                   trade.entry_price - trade.best_price()) / trade.entry_price

                        worst_pl = (trade.worst_price() - trade.entry_price if trade.direction > 0 else
                                    trade.entry_price - trade.worst_price()) / trade.entry_price

                        # perf summed here it means that its not done during partial closing
                        if profit_loss != 0.0:
                            self._stats['perf'] += profit_loss  # total profit/loss percent
                            self._stats['best'] = max(self._stats['best'], profit_loss)  # retains the best win
                            self._stats['worst'] = min(self._stats['worst'], profit_loss)  # retain the worst loss
                            self._stats['high'] += best_pl  # sum if all trades was closed at best price
                            self._stats['low'] += worst_pl  # sum if all trades was closed at worst price
                            self._stats['closed'] += 1
                            self._stats['rpnl'] += trade.unrealized_profit_loss

                        if profit_loss <= 0.0:
                            self._stats['cont-loss'] += 1
                            self._stats['cont-win'] = 0

                        elif profit_loss > 0.0:
                            self._stats['cont-loss'] = 0
                            self._stats['cont-win'] += 1

                        # notification exit reason if not reported
                        if not trade.exit_reason:
                            if trade.direction > 0:
                                if trade.exit_price >= trade.take_profit > 0:
                                    trade.exit_reason = trade.REASON_TAKE_PROFIT_LIMIT

                                elif trade.exit_price <= trade.stop_loss and trade.stop_loss > 0:
                                    trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

                            elif trade.direction < 0:
                                if trade.exit_price <= trade.take_profit and trade.take_profit > 0:
                                    trade.exit_reason = trade.REASON_TAKE_PROFIT_LIMIT

                                elif trade.exit_price >= trade.stop_loss > 0:
                                    trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

                        record = trade.dumps_notify_exit(timestamp, self)

                        if profit_loss < 0:
                            self._stats['failed'].append(record)
                        elif profit_loss > 0:
                            self._stats['success'].append(record)
                        else:
                            self._stats['roe'].append(record)

                        if self._reporting == StrategyTrader.REPORTING_VERBOSE:
                            try:
                                self.report(trade, False)
                            except Exception as e:
                                error_logger.error(str(e))

                        self.notify_trade_exit(timestamp, trade)

                        # store for history, only for real mode
                        if not trader.paper_mode:
                            Database.inst().store_user_closed_trade((trader.name, trader.account.name,
                                                                     self.instrument.market_id,
                                                                     self.strategy.identifier, timestamp, record))
                    else:
                        if not trade.exit_reason:
                            trade.exit_reason = trade.REASON_CANCELED_TIMEOUT

                        self.notify_trade_exit(timestamp, trade)

            # recreate the list of trades
            if mutated:
                trades_list = []

                for trade in self._trades:
                    if not trade.can_delete():
                        # keep only active and pending trades
                        trades_list.append(trade)

                self._trades = trades_list

        #
        # shared or local handler
        #

        self.process_handlers()

    def on_received_liquidation(self, liquidation):
        """
        Receive a trade liquidation (not user trade, global).
        """
        pass

    def on_market_info(self):
        """
        When receive initial or update of market/instrument data.
        """
        pass

    #
    # trade method handler (uses this method, not directly them from the trade class
    #

    def trade_modify_take_profit(self, trade: StrategyTrade, limit_price: float, hard=True):
        """
        Modify the take-profit limit or market price of a trade.
        @param trade: Valid trade model
        @param limit_price: Limit price if hard else market price once reached
        @param hard: True create an order if possible depending of the market type else software order at market
            with possible slippage and at market price
        @return: A StrategyTrade status code.

        @node On spot market either a take-profit limit or a market stop-loss order can be defined. One of them
            will be a soft order (meaning managed by strategy when the market will reach the price).

        @note If the trade is not active (not full or partially realized) an hard order cannot be created.
        @note If there is too many attempt to modify an order (hard) the modification will be rejected temporarily.
        """
        if trade:
            if trade.is_active():
                if trade.can_modify_limit_order(self.strategy.timestamp):
                    # create an order, can cancel some previous, broker will send signals
                    return trade.modify_take_profit(self.strategy.trader(), self.instrument, limit_price, hard)
                else:
                    # must be retried later
                    return StrategyTrade.REJECTED
            else:
                # soft only until active
                trade.tp = limit_price

                # local notification
                self.notify_trade_update(self.strategy.timestamp, trade)

                return StrategyTrade.ACCEPTED

        return StrategyTrade.NOTHING_TO_DO

    def trade_modify_stop_loss(self, trade: StrategyTrade, stop_price: float, hard=True):
        """
        Modify the stop-loss (or in profit) stop or market price of a trade.
        @param trade: Valid trade model
        @param stop_price: Stop market price if hard else market price once reached
        @param hard: True create an order if possible depending of the market type else software order at market
            with possible slippage and at market price
        @return: A StrategyTrade status code.

        @node On spot market either a take-profit limit or a market stop-loss order can be defined. One of them
            will be a soft order (meaning managed by strategy when the market will reach the price).

        @note If the trade is not active (not full or partially realized) an hard order cannot be created.
        @note If there is too many attempt to modify an order (hard) the modification will be rejected temporarily.
        """
        if trade:
            if trade.is_active():
                if trade.can_modify_stop_order(self.strategy.timestamp):
                    # cancel previous order, create new if hard is defined. broker will send signals
                    return trade.modify_stop_loss(self.strategy.trader(), self.instrument, stop_price, hard)
                else:
                    # must be retried later
                    return StrategyTrade.REJECTED
            else:
                # soft only until active
                trade.sl = stop_price

                # local notification
                self.notify_trade_update(self.strategy.timestamp, trade)

                return StrategyTrade.ACCEPTED

        return StrategyTrade.NOTHING_TO_DO

    def trade_modify_oco(self, trade: StrategyTrade, limit_price: float, stop_price: float, hard=True):
        """
        Modify the take-profit (limit or market) and stop-loss (or in profit) stop or market price of a trade.
        It will create if possible an OCO order.

        @param trade: Valid trade model
        @param limit_price: Limit price if hard else market price once reached
        @param stop_price: Stop market price if hard else market price once reached
        @param hard: True create an order if possible depending of the market type else software order at market
            with possible slippage and at market price
        @return: A StrategyTrade status code.

        @note If the trade is not active (not full or partially realized) an hard order cannot be created.
        @note Available only for spot market, and allowing to place a stop-loss and a take-profit order at the
            same time, execution of One will Cancel the Other.

        @warning Not fully implemented. Should be not used for now.
        """
        if trade:
            if trade.is_active():
                if trade.can_modify_limit_order(self.strategy.timestamp):
                    # cancel previous order, create new if hard is defined. broker will send signals
                    return trade.modify_oco(self.strategy.trader(), self.instrument, limit_price, stop_price, hard)
                else:
                    # must be retried later
                    return StrategyTrade.REJECTED
            else:
                # soft only until active
                trade.tp = limit_price
                trade.sl = stop_price

                # local notification
                self.notify_trade_update(self.strategy.timestamp, trade)

                return StrategyTrade.ACCEPTED

        return StrategyTrade.NOTHING_TO_DO

    #
    # watcher signals
    #

    def on_watcher_connected(self):
        """
        Watcher/broker connected.
        """
        pass

    def on_watcher_disconnected(self):
        """
        Watcher/broker lost connection.
        """
        pass

    #
    # balance signals
    #

    def on_account_balance(self, balance):
        """
        Receive a balance margin (free, available, percent...) update.
        """
        pass

    def on_asset_balance(self, balance):
        """
        Receive a balance update for a specific asset (free, locked, total) update.
        """
        pass

    #
    # region management
    #

    @property
    def regions(self):
        return self._regions

    def add_region(self, region):
        with self._mutex:
            region.set_id(self._next_region_id)
            self._next_region_id += 1
            self._regions.append(region)

        self.stream_region_create(self.strategy.timestamp, region)

    def remove_region(self, region_id):
        with self._mutex:
            for region in self._regions:
                if region.id == region_id:
                    self._regions.remove(region)
                    self.stream_region_remove(self.strategy.timestamp, region_id)
                    return True

        return False

    def cleanup_regions(self, timestamp, bid, ask):
        """
        Regenerate the list of regions by removing the expired regions.
        @warning Non thread-safe but must be protected.
        """
        regions = []

        for region in self._regions:
            if not region.can_delete(timestamp, bid, ask):
                regions.append(region)
            else:
                self.stream_region_remove(self.strategy.timestamp, region.id)

        # replace the regions list
        self._regions = regions

    def check_regions(self, timestamp, bid, ask, signal, allow=True):
        """
        Compare a signal to defined regions if some are defined.
        @param timestamp Current timestamp.
        @param signal StrategySignal to check with any regions.
        @param bid float Last instrument bid price
        @param ask float Last instrument ask price
        @param allow Default returned value if there is no defined region (default True).

        @note Thread-safe method.
        """
        if self._regions:
            mutated = False

            # one ore many region, have to pass at least one test
            with self._mutex:
                for region in self._regions:
                    if region.can_delete(timestamp, bid, ask):
                        mutated |= True

                    elif region.test_region(timestamp, signal):
                        # match with at least one region
                        return True

                if mutated:
                    self.cleanup_regions(timestamp, bid, ask)

            return False
        else:
            # no region always pass
            return allow

    #
    # alert management
    #

    @property
    def alerts(self):
        return self._alerts

    def add_alert(self, alert):
        with self._mutex:
            alert.set_id(self._next_alert_id)
            self._next_alert_id += 1
            self._alerts.append(alert)

        self.stream_alert_create(self.strategy.timestamp, alert)

    def remove_alert(self, alert_id):
        with self._mutex:
            for alert in self._alerts:
                if alert.id == alert_id:
                    self._alerts.remove(alert)
                    self.stream_alert_remove(self.strategy.timestamp, alert_id)
                    return True

        return False

    def cleanup_alerts(self, timestamp, bid, ask):
        """
        Regenerate the list of alerts by removing the expired alerts.
        @warning Non thread-safe but must be protected.
        """
        alerts = []

        for alert in self._alerts:
            if not alert.can_delete(timestamp, bid, ask):
                alerts.append(alert)
            else:
                self.stream_alert_remove(self.strategy.timestamp, alert.id)

        # replace the alerts list
        self._alerts = alerts

    def check_alerts(self, timestamp, bid, ask, timeframes):
        """
        Compare timeframes indicators values to defined alerts if some are defined.
        @param timestamp Current timestamp.
        @param bid float Last instrument bid price
        @param ask float Last instrument ask price
        @param timeframes list of TimeframeBasedSub to check with any alerts.

        @note Thread-safe method.
        @note If the alert is triggered, it still keep alive until the next check_alerts call,
              even if its a one shot alert.
        """
        if self._alerts:
            mutated = False

            # one ore many alert, have to pass at least one test
            with self._mutex:
                results = []

                for alert in self._alerts:
                    if alert.can_delete(timestamp, bid, ask):
                        mutated |= True
                    else:
                        result = alert.test_alert(timestamp, bid, ask, timeframes)
                        if result:
                            # alert triggered, dump message could be done with alert dump_notify and result data
                            results.append((alert, result))

                if mutated:
                    self.cleanup_alerts(timestamp, bid, ask)

                if results:
                    return results

            return None
        else:
            # no alerts
            return None

    #
    # actions
    #

    def install_handler(self, handler):
        """
        Add a trade handler to be executed at each update, can be shared between many strategy-traders.
        """
        if handler is not None:
            with self._mutex:
                if handler.context_id not in self._handlers:
                    # setup the new
                    self._handlers[handler.context_id] = handler
                    handler.install(self)

    def uninstall_handler(self, context_id, name):
        with self._mutex:
            if context_id in self._handlers:
                if self._handlers[context_id].name == name:
                    self._handlers[context_id].uninstall(self)
                    del self._handlers[context_id]

    def process_handlers(self):
        """
        Perform the installed handlers.
        """
        if self._handlers:
            with self._mutex:
                for context_id, handler in self._handlers.items():
                    try:
                        handler.process(self)
                    except Exception as e:
                        error_logger.error(repr(e))

    def retrieve_handler(self, context_id):
        with self._mutex:
            return self._handlers.get(context_id)

    def dumps_handlers(self):
        results = []

        if self._handlers:
            with self._mutex:
                for context_id, handler in self._handlers.items():
                    try:
                        results.append(handler.dumps())
                    except Exception as e:
                        error_logger.error(repr(e))

        return results

    #
    # misc
    #

    def check_entry_canceled(self, trade):
        """
        Cancel entry if take-profit price is reached before filling the entry.
        """
        if trade.is_opened() and trade.tp > 0.0:
            if trade.direction > 0:
                if self.instrument.close_exec_price(trade.direction) >= trade.tp:
                    trader = self.strategy.trader()
                    if trade.cancel_open(trader, self.instrument) > 0:
                        trade.exit_reason = trade.REASON_CANCELED_TARGETED
                        return True

            elif trade.direction < 0:
                if self.instrument.close_exec_price(trade.direction) <= trade.tp:
                    trader = self.strategy.trader()
                    if trade.cancel_open(trader, self.instrument) > 0:
                        trade.exit_reason = trade.REASON_CANCELED_TARGETED
                        return True

        return False

    def check_entry_timeout(self, trade, timestamp, timeout):
        """
        Timeout then can cancel a non filled trade if exit signal occurs before timeout (timeframe).
        """
        if trade.is_entry_timeout(timestamp, timeout):
            trader = self.strategy.trader()
            if trade.cancel_open(trader, self.instrument) > 0:
                trade.exit_reason = trade.REASON_CANCELED_TIMEOUT
                return True

        return False

    def check_trade_timeout(self, trade, timestamp):
        """
        Close a profitable trade that has passed its expiry.
        """
        if not trade:
            return False

        trade_profit_loss = trade.profit_loss

        if trade_profit_loss >= 0.0:
            if (trade.context and trade.context.take_profit and trade.context.take_profit.timeout > 0 and
                    trade.context.take_profit.timeout_distance != 0.0):
                if (trade.is_duration_timeout(timestamp, trade.context.take_profit.timeout) and
                        trade_profit_loss < trade.context.take_profit.timeout_distance):
                    trader = self.strategy.trader()

                    if trade.close(trader, self.instrument) > 0:
                        trade.exit_reason = trade.REASON_MARKET_TIMEOUT

                    return True

        elif trade_profit_loss < 0.0:
            if (trade.context and trade.context.stop_loss and trade.context.stop_loss.timeout > 0 and
                    trade.context.stop_loss.timeout_distance != 0.0):
                if (trade.is_duration_timeout(timestamp, trade.context.stop_loss.timeout) and
                        -trade_profit_loss > trade.context.stop_loss.timeout_distance):
                    trader = self.strategy.trader()

                    if trade.close(trader, self.instrument) > 0:
                        trade.exit_reason = trade.REASON_MARKET_TIMEOUT

                    return True

        return False

    def retrieve_context(self, name) -> Optional[StrategyTraderContext]:
        """
        Return a trade context object. Used by set_trade_context.
        Must be override.
        """
        return None

    def apply_trade_context(self, trade: StrategyTrade, context: StrategyTraderContext) -> bool:
        """
        Apply a trade context to a valid trade.
        Must be override.
        """
        if not trade or not context:
            return False

        return True

    def set_trade_context(self, trade: StrategyTrade, name: str) -> bool:
        """
        Apply a trade context to a valid trade.
        Must be override.
        """
        if not trade or not name:
            return False

        context = self.retrieve_context(name)

        if not context:
            return False

        return self.apply_trade_context(trade, context)

    def contexts_ids(self) -> List[str]:
        """
        Returns the list of context ids.
        Must be override.
        """
        return []

    def dumps_context(self, context_id) -> Optional[dict]:
        """
        Returns a dict with the normalized contexts details or None if don't exists.
        Must be override.
        """
        return None

    #
    # signal data streaming and monitoring
    #

    def create_chart_streamer(self, timeframe):
        """
        Create a streamer for the chart at a specific timeframe.
        Must be override.
        """
        return None

    def subscribe_stream(self, timeframe):
        """
        Use or create a specific streamer.
        Must be override.
        """
        return False

    def unsubscribe_stream(self, timeframe):
        """
        Delete a specific streamer when no more subscribers.
        Must be override.
        """
        return False

    def report_state(self, mode=0):
        """
        Collect the state of the strategy trader (instant) and return a dataset.
        Default only return a basic dataset, it must be override per strategy.

        @param mode integer Additional report context.
        """
        return {
            'market-id': self.instrument.market_id,
            'activity': self._activity,
            'affinity': self._affinity,
            'initialized': self._initialized == 0,
            'checked': self._checked == 0,
            'ready': self._initialized == 0 and self._checked == 0 and self.instrument.ready(),
            'bootstrapping': self._bootstrapping > 1,
            'preprocessing': self._preprocessing > 1,
            'members': [],
            'data': [],
            'num-modes': 1
        }

    #
    # reporting
    #

    def report_path(self, *relative_path):
        """
        Check and generated a path where to write reporting files.
        """
        report_path = pathlib.Path(self.strategy.service.report_path)
        if report_path.exists():
            # only create the relative path (not the report if not exists, it might from config setup else its an issue)
            report_path = report_path.joinpath(*relative_path)
            if not report_path.exists():
                try:
                    report_path.mkdir(parents=True)
                except Exception as e:
                    error_logger.error(repr(e))
                    return None

                return report_path
            else:
                return report_path
        else:
            return None

    def default_report_filename(self, ext=".csv", header=None):
        """
        Generate a default filename for reporting.
        """
        report_path = self.report_path(self.strategy.identifier, self.instrument.market_id)
        if report_path:
            filename = str(report_path.joinpath(datetime.now().strftime('%Y%m%d_%Hh%Mm%S') + ext))

            try:
                with open(filename, "wt") as f:
                    if header:
                        f.write(header + '\n')
            except Exception as e:
                error_logger.error(repr(e))
                return None

            return filename

        return None

    def write_report_row(self, row):
        """
        Write a new row into the report file. Default behavior.
        """
        if self._report_filename:
            try:
                with open(self._report_filename, "at") as f:
                    f.write(",".join([str(v) for v in row]) + "\n")
            except Exception as e:
                error_logger.error(repr(e))

    def report(self, trade: StrategyTrade, is_entry: bool):
        """
        Override this method to write trade entry (when is_entry is True) and exit.
        """
        pass

    def report_header(self):
        """
        Override this method to write a header line into the report.
        """
        pass

    #
    # checks
    #

    def compute_asset_quantity(self, trader: Trader, price: float, trade_quantity: float = 0.0) -> float:
        quantity = 0.0

        if not trade_quantity:
            # if not specified use default
            trade_quantity = self.instrument.trade_quantity

        if trader.has_asset(self.instrument.quote):
            # quantity = min(quantity, trader.asset(self.instrument.quote).free) / self.instrument.market_ask
            if trader.has_quantity(self.instrument.quote, trade_quantity or self.instrument.trade_quantity):
                quantity = self.instrument.adjust_quantity(trade_quantity / price)  # and adjusted to 0/max/step
            else:
                msg = "Not enough free quote asset %s, has %s but need %s" % (
                    self.instrument.quote,
                    self.instrument.format_quantity(trader.asset(self.instrument.quote).free),
                    self.instrument.format_quantity(trade_quantity))

                logger.warning(msg)
                Terminal.inst().notice(msg, view='status')
        else:
            msg = "Quote asset %s not found" % self.instrument.quote

            logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

        return quantity

    def compute_margin_quantity(self, trader: Trader, price: float, trade_quantity: float = 0.0) -> float:
        quantity = 0.0

        if not trade_quantity:
            # if not specified use default
            trade_quantity = self.instrument.trade_quantity

        original_quantity = trade_quantity

        if self.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            trade_quantity = self.instrument.adjust_quantity(trade_quantity / price)  # and adjusted to 0/max/step
        else:
            trade_quantity = self.instrument.adjust_quantity(trade_quantity)

        if trader.has_margin(self.instrument.market_id, trade_quantity, price):
            quantity = trade_quantity
        else:
            msg = "Not enough free margin %s, has %s but need %s" % (
                self.instrument.quote, self.instrument.format_quantity(trader.account.margin_balance),
                self.instrument.format_quantity(original_quantity))

            logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

        return quantity

    def check_min_notional(self, order_quantity: float, order_price: float) -> bool:
        if order_quantity <= 0 or order_quantity * order_price < self.instrument.min_notional:
            # min notional not reached
            msg = "Min notional not reached for %s, order %s%s => %s%s but need %s%s" % (
                    self.instrument.symbol,
                    order_quantity, self.instrument.base,
                    order_quantity * order_price, self.instrument.quote,
                    self.instrument.min_notional, self.instrument.quote)

            logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

            return False

        return True

    def has_max_trades(self, max_trades: int, same_timeframe: int = 0, same_timeframe_num: int = 0) -> bool:
        """
        @param max_trades Max simultaneous trades for this instrument.
        @param same_timeframe Compared timeframe.
        @param same_timeframe_num 0 mean Allow multiple trade of the same timeframe, else it define the max allowed.
        """
        result = None

        if self._trades:
            with self._trade_mutex:
                if len(self._trades) >= max_trades:
                    result = "Total max trades of %s reached for %s" % (max_trades, self.instrument.symbol)

                elif same_timeframe > 0 and same_timeframe_num > 0:
                    for trade in self._trades:
                        if trade.timeframe == same_timeframe:
                            same_timeframe_num -= 1
                            if same_timeframe_num <= 0:
                                result = "Max trades of %s reached for timeframe %s for %s" % (
                                    same_timeframe_num, timeframe_to_str(same_timeframe), self.instrument.symbol)
                                break

        if result:
            # logger.warning(result)
            Terminal.inst().notice(result, view='status')
            return True

        return False

    def has_max_trades_by_context(self, max_trades: int, same_context: Optional[StrategyTraderContext] = None) -> bool:
        """
        @param max_trades Max simultaneous trades for this instrument or context or 0.
        @param same_context Context to check with
        @return True if a limit is reached.
        """
        result = None

        if self._trades:
            with self._trade_mutex:
                if len(self._trades) >= max_trades:
                    result = "Total max trades of %s reached for %s" % (max_trades, self.instrument.symbol)

                elif same_context:
                    if same_context.max_trades <= 0:
                        result = "No trades allowed for context %s for %s" % (same_context.name, self.instrument.symbol)
                    else:
                        # count trade base on the same context
                        same_context_num = 0

                        for trade in self._trades:
                            if trade.context == same_context:
                                same_context_num += 1
                                if same_context_num >= same_context.max_trades:
                                    result = "Max trades of %s reached for context %s for %s" % (
                                        same_context.max_trades, same_context.name, self.instrument.symbol)
                                    break

        elif max_trades <= 0:
            result = "No trades allowed for %s" % self.instrument.symbol

        elif same_context and same_context.max_trades <= 0:
            result = "No trades allowed for context %s for %s" % (same_context.name, self.instrument.symbol)

        if result:
            # logger.warning(result)
            Terminal.inst().notice(result, view='status')
            return True

        return False

    #
    # notification helpers
    #

    def notify_signal(self, timestamp: float, signal: StrategySignal):
        if signal:
            # system notification
            self.strategy.notify_signal(timestamp, signal, self)

            # stream
            if self._signal_streamer:
                try:
                    self._signal_streamer.member('signal').update(self, signal, timestamp)
                    self._signal_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    def notify_trade_entry(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            self.strategy.notify_trade_entry(timestamp, trade, self)

            # stream
            if self._trade_entry_streamer:
                try:
                    self._trade_entry_streamer.member('trade-entry').update(self, trade, timestamp)
                    self._trade_entry_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

            # for reporting if specified
            if self._reporting == self.REPORTING_VERBOSE:
                self.report(trade, True)

            # inform handler
            if self._handlers and trade.context is not None and trade.context.name in self._handlers:
                with self._mutex:
                    self._handlers[trade.context.name].on_trade_opened(self, trade)

    def notify_trade_update(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            self.strategy.notify_trade_update(timestamp, trade, self)

            # stream
            if self._trade_update_streamer:
                try:
                    self._trade_update_streamer.member('trade-update').update(self, trade, timestamp)
                    self._trade_update_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    def notify_trade_exit(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            self.strategy.notify_trade_exit(timestamp, trade, self)

            # stream
            if self._trade_exit_streamer:
                try:
                    self._trade_exit_streamer.member('trade-exit').update(self, trade, timestamp)
                    self._trade_exit_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

            # for reporting if specified
            if self._reporting == self.REPORTING_VERBOSE:
                self.report(trade, False)

            # inform handler
            if self._handlers and trade.context is not None and trade.context.name in self._handlers:
                with self._mutex:
                    self._handlers[trade.context.name].on_trade_exited(self, trade)

    def notify_trade_error(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            self.strategy.notify_trade_error(timestamp, trade.id, self)

            # @todo could have a stream

    def notify_alert(self, timestamp: float, alert: Alert, result: dict):
        if alert and result:
            # system notification
            self.strategy.notify_alert(timestamp, alert, result, self)

            # stream
            if self._alert_streamer:
                try:
                    self._alert_streamer.member('alert').update(self, alert, result, timestamp)
                    self._alert_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    #
    # stream helpers
    #

    def stream_trade_update(self, timestamp: float, trade: StrategyTrade):
        if self._trade_update_streamer:
            try:
                self._trade_update_streamer.member('trade-update').update(self, trade, timestamp)
                self._trade_update_streamer.publish()
            except Exception as e:
                logger.error(repr(e))

    def stream_alert_create(self, timestamp: float, alert: Alert):
        if self._alert_streamer:
            try:
                self._alert_streamer.member('add-alert').update(self, alert, timestamp)
                self._alert_streamer.publish()
            except Exception as e:
                logger.error(repr(e))

    def stream_alert_remove(self, timestamp: float, alert_id: int):
        if self._alert_streamer:
            try:
                self._alert_streamer.member('rm-alert').update(self, alert_id, timestamp)
                self._alert_streamer.publish()
            except Exception as e:
                logger.error(repr(e))

    def stream_region_create(self, timestamp: float, region: Region):
        if self._region_streamer:
            try:
                self._region_streamer.member('add-region').update(self, region, timestamp)
                self._region_streamer.publish()
            except Exception as e:
                logger.error(repr(e))

    def stream_region_remove(self, timestamp: float, region_id: int):
        if self._region_streamer:
            try:
                self._region_streamer.member('rm-region').update(self, region_id, timestamp)
                self._region_streamer.publish()
            except Exception as e:
                logger.error(repr(e))
