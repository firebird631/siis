# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trader base class.

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Tuple, Dict, Union, Optional, List

if TYPE_CHECKING:
    from .strategy import Strategy
    from .strategybaseanalyser import StrategyBaseAnalyser
    from .alert.alert import Alert
    from .region.region import Region
    from .handler.handler import Handler
    from trader.trader import Trader
    from instrument.instrument import TickType, Candle
    from monitor.streamable import Streamable

import pathlib
import threading
import time
import traceback

from datetime import datetime, timedelta

from instrument.instrument import Instrument

from strategy.trade.strategyassettrade import StrategyAssetTrade
from strategy.trade.strategyindmargintrade import StrategyIndMarginTrade
from strategy.trade.strategymargintrade import StrategyMarginTrade
from strategy.trade.strategypositiontrade import StrategyPositionTrade
from strategy.trade.strategytrade import StrategyTrade

from .strategytradercontext import StrategyTraderContext
from .learning.trainer import Trainer

from .indicator.models import Limits

from common.utils import timeframe_to_str, UTC, check_yes_no_opt, yes_no_opt, integer_opt, check_integer_opt, \
    float_opt, check_float_opt
from strategy.strategysignal import StrategySignal
from terminal.terminal import Terminal

from database.database import Database
from trader.order import Order

from monitor.streamable import Streamable, StreamMemberBool, StreamMemberInt, StreamMemberFloat, StreamMemberDict, \
    StreamMemberTradeEntry, StreamMemberTradeUpdate, StreamMemberTradeExit, \
    StreamMemberFloatSerie, StreamMemberTradeSignal, \
    StreamMemberStrategyAlert, StreamMemberStrategyAlertCreate, StreamMemberStrategyAlertRemove, \
    StreamMemberStrategyRegion, StreamMemberStrategyRegionCreate, StreamMemberStrategyRegionRemove

import logging
logger = logging.getLogger('siis.strategy.trader')
error_logger = logging.getLogger('siis.error.strategy.trader')
traceback_logger = logging.getLogger('siis.traceback.strategy.trader')


class StrategyTraderBase(object):
    """
    A strategy can manage multiple instrument. Strategy trader is on of the managed instruments.
    """
    TRADE_TYPE_MAP = {
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

    STATE_NORMAL = 0
    STATE_WAITING = 1
    STATE_PROGRESSING = 2

    PREPROCESSING_STATE_NORMAL = 0
    PREPROCESSING_STATE_WAITING = 1
    PREPROCESSING_STATE_BEGIN = 2
    PREPROCESSING_STATE_LOAD = 3
    PREPROCESSING_STATE_UPDATE = 4
    PREPROCESSING_STATE_COMPLETE = 5

    strategy: Strategy
    instrument: Instrument

    _activity: bool
    _affinity: int
    _max_trades: int
    _min_price: float
    _min_vol24h: float
    _hedging: bool
    _reversal: bool
    _trade_short: bool
    _allow_short: bool

    _initialized: int
    _check: int
    _limits: Limits

    _preprocessing: int
    _preprocess_depth: int
    _preprocess_streamer: Union[Streamable, None]
    _preprocess_from_timestamp: float
    _bootstrapping: int
    _processing: bool

    _trade_mutex: threading.RLock
    _trades: List[StrategyTrade]
    _next_trade_id: int
    _regions: List[Region]
    _next_region_id: int
    _alerts: List[Alert]
    _next_alert_id: int
    _global_handler: Union[Handler, None]
    _handlers: Dict[str, Handler]

    _global_streamer: Union[Streamable, None]
    _trade_entry_streamer: Union[Streamable, None]
    _trade_update_streamer: Union[Streamable, None]
    _trade_exit_streamer: Union[Streamable, None]
    _signal_streamer: Union[Streamable, None]
    _alert_streamer: Union[Streamable, None]
    _region_streamer: Union[Streamable, None]

    _trade_contexts: Dict[str, StrategyTraderContext]

    _analysers_registry: Dict[str, Any]
    _analysers: Dict[str, StrategyBaseAnalyser]
    _analysers_streamers: Dict[int, Streamable]

    _reporting: int
    _report_filename: Union[str, None]

    _stats: Dict[str, Union[int, float, List, Tuple]]
    _trainer: Union[Trainer, None]

    _initials_parameters = Dict

    def __init__(self, strategy: Strategy, instrument: Instrument, params: dict = None):
        self.strategy = strategy
        self.instrument = instrument

        self._mutex = threading.RLock()  # activity, global locker, region locker, instrument locker

        #
        # options
        #

        self._max_trades = params.get('max-trades', 1)  # total max trades for this strategy trader

        self._min_price = params.get('min-price', 0.0)
        self._min_vol24h = params.get('min-vol24h', 0.0)

        self._region_allow = params.get('region-allow', True)
        self._hedging = params.get('hedging', False)
        self._reversal = params.get('reversal', True)

        self._activity = params.get('activity', True)  # auto trading
        self._affinity = params.get('affinity', 5)     # based on a linear scale [0..100]

        self._allow_short = params.get('allow-short', True)

        #
        # states
        #

        self._initialized = StrategyTraderBase.STATE_WAITING  # initiate data before running
        self._checked = StrategyTraderBase.STATE_WAITING      # check trades/orders/positions

        self._limits = Limits()     # price and timestamp ranges

        self._preprocessing = StrategyTraderBase.PREPROCESSING_STATE_WAITING  # 2 to 5 in progress
        self._preprocess_depth = 0  # in second, need of preprocessed data depth of history
        self._preprocess_streamer = None       # current tick or quote streamer
        self._preprocess_from_timestamp = 0.0  # preprocessed date from this timestamp to limit last timestamp

        self._bootstrapping = StrategyTraderBase.STATE_WAITING

        self._processing = False   # True during processing
        self._trade_short = False  # short are supported by market/strategy

        self._trade_mutex = threading.RLock()   # trades locker
        self._trades = []
        self._next_trade_id = 1

        self._regions = []
        self._next_region_id = 1

        self._alerts = []
        self._next_alert_id = 1

        self._global_handler = None   # installed handler for any contexts (some can be shared)
        self._handlers = {}           # installed handlers per context (some can be shared)

        self._global_streamer = None
        self._trade_entry_streamer = None
        self._trade_update_streamer = None
        self._trade_exit_streamer = None
        self._signal_streamer = None
        self._alert_streamer = None
        self._region_streamer = None

        self._default_trader_context_class = None
        self._trade_contexts = {}  # contexts registry

        self._reporting = StrategyTraderBase.REPORTING_NONE
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
            'rpnl': 0.0,       # realize profit and loss
            'tp-win': 0,       # number of trades closed at TP in profit
            'tp-loss': 0,      # number of trades closed at TP in loss
            'sl-win': 0,       # number of trades closed at SL in profit
            'sl-loss': 0,      # number of trades closed at SL in loss
            'time-deviation': 0.0  # difference between query update time and last tick/candle time
        }

        if self.instrument:
            self.instrument.loads_session(params.get('sessions', {}))

        # specific to learning update
        self._trainer = None

        # not in backtesting to avoid recursive except if --training flag is specified
        if not self.strategy.service.backtesting or self.strategy.service.training:
            self._trainer = Trainer.create_trainer(self, params) if 'learning' in params else None

        # keep a copy of the initial parameters
        self._initials_parameters = copy.deepcopy(params)

        # analyser specifics
        self._analysers_registry = {}
        self._analysers = {}
        self._analysers_streamers = {}

    def update_parameters(self, params: dict):
        """
        Called after changes occurs into the existing contexts or timeframes. Reload and rebuild contexts and
        timeframes.
        """
        # reloads any contexts
        contexts_params = params.get('contexts', {})

        for name, context in self._trade_contexts.items():
            context_params = contexts_params.get(name, {})
            context.compiled = False
            context.loads(self, context_params)

        # and then compiles
        self.compiles_all_contexts()

    #
    # strategy trade context
    #

    def set_default_trader_context(self, model_class):
        if not issubclass(model_class, StrategyTraderContext):
            error_logger.error("Default trader context must be subclass of StrategyTraderContext")
            return

        self._default_trader_context_class = model_class

    def register_context(self, ctx: Union[StrategyTraderContext, list[StrategyTraderContext]]):
        """
        Each trade context must be registered.
        @param ctx: Single or list|tuple of trade contexts.
        """
        if ctx is None:
            return

        if type(ctx) in (list, tuple):
            for ct in ctx:
                if ct.name in self._trade_contexts:
                    logger.warning("Strategy trade context %s already registered" % ct.name)
                    return

                self._trade_contexts[ct.name] = ct
        else:
            if ctx.name in self._trade_contexts:
                logger.warning("Strategy trade context %s already registered" % ctx.name)
                return

            self._trade_contexts[ctx.name] = ctx

    def unregister_context(self, name: str):
        """
        Each trade context must be registered. If necessary it can be unregistered.
        @param name:
        """
        if name in self._trade_contexts:
            del(self._trade_contexts[name])

    def loads_contexts(self, params: dict, class_model=None):
        contexts = []

        context_class = self._default_trader_context_class
        if class_model:
            context_class = class_model

        for name, data in params.get("contexts", {}).items():
            if data is None:
                continue

            try:
                # retrieve or instantiate
                ma_adx = self.retrieve_context(name) or context_class(name)
                ma_adx.loads(self, data)

                if ma_adx.mode != ma_adx.MODE_NONE:
                    contexts.append(ma_adx)
                    self.register_context(ma_adx)

            except Exception as e:
                error_logger.error("Unable to validate context %s : %s" % (name, str(e)))
                traceback_logger.error(traceback.format_exc())

        return contexts

    def compiles_all_contexts(self):
        rm_list = []

        for name, ctx in self._trade_contexts.items():
            try:
                ctx.compile(self)
            except Exception as e:
                error_logger.error("Unable to compile context %s, remove it : %s" % (name, str(e)))
                traceback_logger.error(traceback.format_exc())
                rm_list.append(name)

        for rm in rm_list:
            del(self._trade_contexts[rm])

    def retrieve_context(self, name: str) -> Union[StrategyTraderContext, None]:
        """
        Return a trade context object. Used by set_trade_context.
        @param name:
        @return:
        """
        return self._trade_contexts.get(name)

    def contexts_ids(self) -> List[str]:
        """
        Returns the list of registered context ids.
        """
        return list(self._trade_contexts.keys())

    def apply_trade_context(self, trade: StrategyTrade, context: StrategyTraderContext) -> bool:
        """
        Apply a trade context to a valid trade.
        Overridden by subclasses TimeframeStrategyTrader and BarStrategyTrader.
        """
        if not trade or not context:
            return False

        return True

    def set_trade_context(self, trade: StrategyTrade, name: str) -> bool:
        """
        Apply a trade context to a valid trade.
        """
        if not trade or not name:
            return False

        context = self.retrieve_context(name)

        if not context:
            return False

        return self.apply_trade_context(trade, context)

    def dumps_context(self, context_id: str) -> Optional[dict]:
        """
        Returns a dict with the normalized contexts details or None if it doesn't exist.
        Must be overridden.
        """
        return None

    #
    # analysers
    #

    def register_analyser(self, type_name: str, class_model: Any):
        """Declare an analyser model class with its unique type name"""
        if type_name and class_model:
            self._analysers_registry[type_name] = class_model

    def has_analyser(self, name: str) -> bool:
        """Does contain an analyser for name"""
        return name in self._analysers

    def find_analyser(self, name: str) -> Optional[StrategyBaseAnalyser]:
        """Retrieve an instance of analyser according its name"""
        return self._analysers.get(name, None)

    def cleanup_analyser(self, timestamp):
        for k, analyser in self._analysers.items():
            analyser.cleanup(timestamp)

    def analysers(self):
        return self._analysers.values()

    #
    # properties
    #

    def ready(self):
        """Return True if any analyser are ready and the instrument too"""
        for k, analyser in self._analysers.items():
            if analyser.need_initial_data():
                return False

        return True

    @property
    def is_timeframes_based(self):
        return False

    @property
    def is_tickbars_based(self):
        return False

    @property
    def base_timeframe(self) -> float:
        return 0.0

    @property
    def mutex(self):
        return self._mutex

    def check_option(self, option: Union[str, None],
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

        if keys[0] not in ('max-trades', 'context', 'mode', 'allow-short', 'region-allow'):
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
                    if not check_integer_opt(value, 0, 999):
                        return "Value must be an integer between 0 and 999"

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
                        if not check_yes_no_opt(value):
                            return "Value must be one of : 0, 1, false, true, yes, no"

                    elif keys[3] == "depth":
                        if not check_integer_opt(value, 1, 20):
                            return "Depth must be an integer between 1 and 20"

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
                        if not check_float_opt(value, 0.0, 10000000.0):
                            return "Value must be a decimal greater than 0"

                    elif keys[3] == 'step':
                        if not check_float_opt(value, 0.0, 10000000.0):
                            return "Value must be a decimal greater than 0"

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
            if not check_integer_opt(value, 0, 999):
                return "Value must be an integer between 0 and 999"

        elif keys[0] in ('allow-short', 'region-allow'):
            if not check_yes_no_opt(value):
                return "Value must be one of : 0, 1, false, true, yes, no"

        return None

    def set_option(self, option: Union[str, None],
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

        if keys[0] not in ('max-trades', 'context', 'mode', 'allow-short', 'region-allow'):
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
                    v = integer_opt(value, 0, 999)
                    if v is None:
                        return False

                    context.max_trades = v
                    return True

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

                    elif keys[3] == "depth":
                        v = integer_opt(value, 0, 20)
                        if v is None:
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
                        quantity = float_opt(value, 0.0, 10000000.0)
                        if quantity is None:
                            return False

                        return context.modify_trade_quantity(quantity)

                    elif keys[3] == 'step':
                        qty_step = float_opt(value, 0.0, 10000000.0)
                        if qty_step is None:
                            return False

                        return context.modify_trade_step(qty_step)

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

                        quantity = float_opt(value, 0.0, 10000000.0)
                        if quantity is None:
                            return False

                        return context.modify_trade_quantity_type(self.instrument, keys[4], quantity)

        elif keys[0] == 'max-trades':
            v = integer_opt(value, 0, 999)
            if v is None:
                return False

            self._max_trades = v
            return True

        elif keys[0] == 'allow-short':
            v = yes_no_opt(value)
            if v is None:
                return False

            self._allow_short = v
            return True

        elif keys[0] == 'region-allow':
            v = yes_no_opt(value)
            if v is None:
                return False

            self._region_allow = v
            return True

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
        if self._activity != status:
            self._activity = status

            if self._global_streamer:
                self._global_streamer.member('activity').update(self._activity)

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
        if self._affinity != affinity:
            self._affinity = affinity

            if self._global_streamer:
                self._global_streamer.member('affinity').update(self._affinity)

    @property
    def max_trades(self) -> int:
        return self._max_trades

    @max_trades.setter
    def max_trades(self, max_trades: int):
        if self._max_trades != max_trades:
            self._max_trades = max_trades

            if self._global_streamer:
                self._global_streamer.member('max-trades').update(self._max_trades)

    @property
    def min_price(self) -> float:
        return self._min_price

    @property
    def min_vol24h(self) -> float:
        return self._min_vol24h

    @property
    def hedging(self) -> bool:
        return self._hedging

    @property
    def reversal(self) -> bool:
        return self._reversal

    @property
    def allow_short(self) -> bool:
        return self._allow_short

    @property
    def trade_short(self) -> bool:
        return self._trade_short

    @property
    def region_allow(self) -> bool:
        return self._region_allow

    def restart(self):
        """
        Needed on a reconnection to reset some states.
        """
        with self._mutex:
            self._initialized = StrategyTraderBase.STATE_WAITING
            self._checked = StrategyTraderBase.STATE_WAITING
            self._preprocessing = StrategyTraderBase.STATE_WAITING
            self._bootstrapping = StrategyTraderBase.STATE_WAITING

    def recheck(self):
        """
        Query for recheck any trades of the trader.
        """
        with self._mutex:
            self._checked = StrategyTraderBase.STATE_WAITING

    @property
    def initialized(self) -> int:
        return self._initialized

    def set_initialized(self, state: int):
        """Set state to : 0, 1 or 2."""
        self._initialized = state

    @property
    def checked(self) -> int:
        return self._checked

    def set_checked(self, state: int):
        """Set state to : 0, 1 or 2."""
        self._checked = state

    @property
    def trainer(self) -> Union[Trainer, None]:
        return self._trainer

    @property
    def has_trainer(self) -> bool:
        return self._trainer is not None

    def get_stat(self, key: str) -> Union[float, int, None]:
        """
        Return a statistic value from key.
        """
        if key in self._stats:
            return self._stats[key]

        return None

    #
    # pre-processing
    #

    @property
    def preprocessing(self) -> int:
        return self._preprocessing

    def set_preprocessing(self, state: int):
        self._preprocessing = state

    def preprocess_load_cache(self, from_date: datetime, to_date: datetime):
        """
        Override this method to load the cached data before performing preprocess.
        """
        pass

    def preprocess(self, trade: TickType):
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

    @property
    def bootstrapping(self) -> int:
        return self._bootstrapping

    def set_bootstrapping(self, state: int):
        self._bootstrapping = state

    @property
    def processing(self) -> bool:
        return self._processing

    def set_processing(self, state: bool):
        self._processing = state

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

    def update_time_deviation(self, timestamp):
        if self.strategy.timestamp - timestamp > self._stats['time-deviation']:
            self._stats['time-deviation'] = self.strategy.timestamp - timestamp

            logger.debug("Higher time deviation of %g seconds for %s" % (self._stats['time-deviation'],
                                                                         self.instrument.market_id))

    def check_trades(self, timestamp: float):
        """
        Recheck actives or pending trades. Useful after a reconnection.
        """
        with self._mutex:
            if self._checked != StrategyTraderBase.STATE_WAITING:
                # only if waiting to check trades
                return

            # process
            self._checked = StrategyTraderBase.STATE_PROGRESSING

        trader = self.strategy.trader()

        if not trader.paper_mode and self.strategy.service.check_trades_at_start:
            # do not process in paper-mode neither if option is disabled
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
            self._checked = StrategyTraderBase.STATE_NORMAL

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
        Trader and trades persistence (might occur only for live mode on real accounts).
        @note Must be called only after terminate.
        @note Would need a transaction from clear to the last store
        """
        trader = self.strategy.trader()

        with self._mutex:
            # clear DB before
            Database.inst().clear_user_trades(trader.name, trader.account.name, self.strategy.identifier)

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

        trade.loads(data, self)

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
        An order signal can affect only one trade.
        """
        with self._trade_mutex:
            remove_trade = None

            try:
                for trade in self._trades:
                    # update each trade relating the order (might be a unique)
                    order_id = data[1]['id'] if type(data[1]) is dict else data[1]
                    ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                    if trade.is_target_order(order_id, ref_order_id):
                        trade.order_signal(signal_type, data[1], data[2] if len(data) > 2 else None, self.instrument)

                        # notify update only if trade is not closed by the signal else let's do finalize_trade method
                        if trade.can_delete():
                            self.finalize_trade(self.strategy.timestamp, trade)
                            remove_trade = trade
                        else:
                            self.notify_trade_update(self.strategy.timestamp, trade)

                        break

                # remove trade immediately
                if remove_trade:
                    self._trades.remove(remove_trade)

            except Exception as e:
                error_logger.error(traceback.format_exc())
                error_logger.error(repr(e))

    def position_signal(self, signal_type: int, data: dict):
        """
        Update quantity/filled on a trade, delete or cancel.
        A position signal can affect many trades.
        """
        with self._trade_mutex:
            remove_trades = []

            try:
                for trade in self._trades:
                    # update each trade relating the position (could be many)
                    position_id = data[1]['id'] if type(data[1]) is dict else data[1]
                    ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                    if trade.is_target_position(position_id, ref_order_id):
                        trade.position_signal(signal_type, data[1], data[2] if len(data) > 2 else None, self.instrument)

                        # notify update only if trade is not closed by the signal else let's do finalize_trade method
                        if trade.is_closed():
                            self.finalize_trade(self.strategy.timestamp, trade)
                            remove_trades.append(trade)
                        else:
                            self.notify_trade_update(self.strategy.timestamp, trade)

                # remove trade(s) immediately
                if remove_trades:
                    for trade in remove_trades:
                        self._trades.remove(trade)

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

    def dumps_regions(self) -> List[dict]:
        """
        Dumps the regions. Not sorted.
        """
        results = []

        with self._mutex:
            for region in self._regions:
                region_dumps = region.dumps()
                region_dumps['market-id'] = self.instrument.market_id
                region_dumps['symbol'] = self.instrument.symbol

                results.append(region_dumps)

        return results

    #
    # trades processing
    #

    def update_trades(self, timestamp: float):
        """
        Update active trades when price change or a volume is traded.
        Trades are closed at stop or limit price when reached if there is no external orders.
        It also processes operations on each trade having operations.
        And also process trades handlers if one or many are configured.
        Another responsibility is to update the stop and limit orders in way to reflect the changes of quantity.
        @note This is only called at each traded volume (or price change depending on the configured mode).
        """
        if not self._trades:
            return

        trader = self.strategy.trader()

        #
        # for each trade check if the TP or SL is reached and trigger if necessary
        #

        mutated = False

        with self._trade_mutex:
            for trade in self._trades:

                # cannot manage a trade in state error
                if trade.is_error():
                    continue

                if trade.can_delete():
                    mutated = True

                #
                # managed operation
                #

                if trade.has_operations():
                    op_mutated = False

                    for operation in trade.operations:
                        op_mutated |= operation.test_and_operate(trade, self, trader)

                    if op_mutated:
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

            if mutated:
                # recreate the list of trades because a trade stay buy might not be here
                trades_list = []

                for trade in self._trades:
                    if not trade.can_delete():
                        # keep only active and pending trades
                        trades_list.append(trade)

                self._trades = trades_list

                self.cleanup_trades(timestamp)

        self.process_handlers()

    def cleanup_trades(self, timestamp):
        """Remove terminated, rejected, canceled and empty trades."""
        mutated = False

        with self._trade_mutex:
            for trade in self._trades:
                if trade.can_delete():
                    # self.finalize_trade(timestamp, trade)
                    mutated = True

            # recreate the list of trades
            if mutated:
                trades_list = []

                for trade in self._trades:
                    if not trade.can_delete():
                        # keep only active and pending trades
                        trades_list.append(trade)

                self._trades = trades_list

    def finalize_trade(self, timestamp: float, trade: StrategyTrade):
        """
        Cleanup a trade, finalize its state and statistics before removing it from manager.
        @param timestamp: epoch timestamp in second
        @param trade: Valid trade
        """
        if not trade:
            return

        trader = self.strategy.trader()

        # cleanup if necessary before deleting the trade related refs
        # but there might be no order or position remaining at this level
        trade.remove(trader, self.instrument)

        # record the trade for analysis and study
        if not trade.is_canceled():
            # last update of stats before logging (useless because no longer active and done before)
            trade.update_stats(self.instrument, timestamp)

            # realized profit/loss
            net_profit_loss_rate = trade.net_profit_loss_rate()

            best_pl = (trade.best_price() - trade.entry_price if trade.direction > 0 else
                       trade.entry_price - trade.best_price()) / trade.entry_price

            worst_pl = (trade.worst_price() - trade.entry_price if trade.direction > 0 else
                        trade.entry_price - trade.worst_price()) / trade.entry_price

            # perf summed here it means that it is not done during partial closing
            if net_profit_loss_rate != 0.0:
                self._stats['perf'] += net_profit_loss_rate  # total profit/loss percent
                self._stats['best'] = max(self._stats['best'], net_profit_loss_rate)  # retains the best win
                self._stats['worst'] = min(self._stats['worst'], net_profit_loss_rate)  # retain the worst loss
                self._stats['high'] += best_pl  # sum like as all trades was closed at best price
                self._stats['low'] += worst_pl  # sum like as all trades was closed at worst price
                self._stats['closed'] += 1
                self._stats['rpnl'] += trade.unrealized_profit_loss

            # notification exit reason if not reported assume closed at market
            if not trade.exit_reason:
                trade.exit_reason = trade.REASON_CLOSE_MARKET

            record = trade.dumps_notify_exit(timestamp, self)

            if net_profit_loss_rate < 0.0:
                self._stats['cont-loss'] += 1
                self._stats['cont-win'] = 0

                if trade.exit_reason in (trade.REASON_TAKE_PROFIT_LIMIT, trade.REASON_TAKE_PROFIT_MARKET):
                    self._stats['tp-loss'] += 1
                elif trade.exit_reason in (trade.REASON_STOP_LOSS_MARKET, trade.REASON_STOP_LOSS_LIMIT):
                    self._stats['sl-loss'] += 1

            elif net_profit_loss_rate >= 0.0:
                self._stats['cont-loss'] = 0
                self._stats['cont-win'] += 1

                if trade.exit_reason in (trade.REASON_TAKE_PROFIT_LIMIT, trade.REASON_TAKE_PROFIT_MARKET):
                    self._stats['tp-win'] += 1
                elif trade.exit_reason in (trade.REASON_STOP_LOSS_MARKET, trade.REASON_STOP_LOSS_LIMIT):
                    self._stats['sl-win'] += 1

            if round(net_profit_loss_rate * 1000) == 0.0:
                self._stats['roe'].append(record)
            elif net_profit_loss_rate < 0:
                self._stats['failed'].append(record)
            elif net_profit_loss_rate > 0:
                self._stats['success'].append(record)
            else:
                self._stats['roe'].append(record)

            if self._reporting == StrategyTraderBase.REPORTING_VERBOSE:
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

    def on_received_initial_bars(self, analyser: str):
        """
        Slot called once the initial bulk of candles are received for each analyser.
        """
        pass

    def check_spread(self, signal: StrategySignal) -> bool:
        """Compare spread from entry signal max allowed spread value, only if max-spread parameters is valid"""
        if not signal or not signal.context:
            return True

        if signal.context.entry.max_spread <= 0.0:
            return True

        return self.instrument.market_spread <= signal.context.entry.max_spread

    def check_min_profit(self, signal: StrategySignal) -> bool:
        """Check for a minimal profit based on context parameters"""
        if not signal or not signal.context:
            return True

        if signal.context.min_profit <= 0.0:
            return True

        return signal.profit() >= signal.context.min_profit

    #
    # trade method handler (uses this method, not directly them from the trade class
    #

    def trade_modify_take_profit(self, trade: StrategyTrade, limit_price: float, hard=True):
        """
        Modify the take-profit limit or market price of a trade.
        @param trade: Valid trade
        @param limit_price: Limit price if hard else market price once reached
        @param hard: True create an order if possible depending on the market type else software order at market
            with possible slippage and at market price
        @return: A StrategyTrade status code.

        @node On spot market either a take-profit limit or a market stop-loss order can be defined. One of them
            will be a soft order (meaning managed by strategy when the market will reach the price).

        @note If the trade is not active (not full or partially realized) a hard order cannot be created.
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
        @param trade: Valid trade
        @param stop_price: Stop market price if hard else market price once reached
        @param hard: True create an order if possible depending on the market type else software order at market
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

        @param trade: Valid trade
        @param limit_price: Limit price if hard else market price once reached
        @param stop_price: Stop market price if hard else market price once reached
        @param hard: True create an order if possible depending on the market type else software order at market
            with possible slippage and at market price
        @return: A StrategyTrade status code.

        @note If the trade is not active (not full or partially realized) a hard order cannot be created.
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

    def trade_reduce_quantity(self, trade: StrategyTrade, reduce_quantity: float):
        """
        Reduce the quantity of a trade or position.
        @param trade: Valid trade
        @param reduce_quantity: Quantity to reduce from the active trade
        """
        if trade:
            if trade.is_active():
                trade.reduce(self.strategy.trader(), self.instrument, reduce_quantity)

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

            # one or many region, have to pass at least one test
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

    def check_alerts(self, timestamp, bid, ask):
        """
        Compare timeframes indicators values to defined alerts if some are defined.
        @param timestamp Current timestamp.
        @param bid float Last instrument bid price
        @param ask float Last instrument ask price

        @note Thread-safe method.
        @note If the alert is triggered, it still keeps alive until the next check_alerts call,
              even if it is a one shot alert.
        """
        if self._alerts:
            mutated = False

            # one or many alert, have to pass at least one test
            with self._mutex:
                results = []

                for alert in self._alerts:
                    if alert.can_delete(timestamp, bid, ask):
                        mutated |= True
                    else:
                        result = alert.test_alert(timestamp, bid, ask)
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

                if self._global_handler:
                    try:
                        self._global_handler.process(self)
                    except Exception as e:
                        error_logger.error(repr(e))

    def retrieve_handler(self, context_id: str) -> Union[Handler, None]:
        with self._mutex:
            return self._handlers.get(context_id)

    @property
    def global_handler(self) -> Handler:
        return self._global_handler

    def dumps_handlers(self) -> List[Dict[str, str]]:
        """
        Dumps of any installed per context handler and of the global handler.
        @return:
        """
        results = []

        if self._global_handler:
            try:
                results.append(self._global_handler.dumps(self))
            except Exception as e:
                error_logger.error(repr(e))

        if self._handlers:
            with self._mutex:
                for context_id, handler in self._handlers.items():
                    try:
                        results.append(handler.dumps(self))
                    except Exception as e:
                        error_logger.error(repr(e))

        return results

    #
    # misc
    #

    def check_entry_canceled(self, trade: StrategyTrade) -> bool:
        """
        Cancel entry if take-profit price is reached before filling the entry.
        """
        if trade is None:
            return False

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

    def check_entry_timeout(self, trade: StrategyTrade, timestamp: float, timeout: float) -> bool:
        """
        Timeout then can cancel a non-filled trade if exit signal occurs before timeout (timeframe).
        """
        if trade is None:
            return False

        if timeout <= 0.0 or timestamp <= 0.0:
            return False

        if trade.is_entry_timeout(timestamp, timeout):
            trader = self.strategy.trader()
            if trade.cancel_open(trader, self.instrument) > 0:
                trade.exit_reason = trade.REASON_CANCELED_TIMEOUT
                return True

        return False

    def check_trade_timeout(self, trade: StrategyTrade, timestamp: float) -> bool:
        """
        Close a profitable trade that has passed its expiry.
        """
        if not trade:
            return False

        if timestamp <= 0.0:
            return False

        trade_profit_loss = trade.estimate_profit_loss_rate(self.instrument)

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

    #
    # signal data streaming and monitoring
    #

    def create_chart_streamer(self, strategy_sub: StrategyBaseAnalyser) -> Union[Streamable, None]:
        """
        Create a streamer for the chart at a specific timeframe.
        Must be overridden.
        """
        return None

    def subscribe_stream(self, timeframe: float) -> bool:
        """
        Use or create a specific streamer.
        Must be overridden.
        """
        return False

    def unsubscribe_stream(self, timeframe: float) -> bool:
        """
        Delete a specific streamer when no more subscribers.
        Must be overridden.
        """
        return False

    def subscribe_info(self) -> bool:
        return False

    def unsubscribe_info(self) -> bool:
        return False

    def report_state(self, mode=0) -> dict:
        """
        Collect the state of the strategy trader (instant) and return a dataset.
        Default only return a basic dataset, it must be overridden per strategy.

        Default as 5 modes :
            - 0: Data-series (sub)
            - 1: General states and parameters of strategy trader
            - 2: General states and parameters of each strategy context
            - 3: Computation parameters of each strategy context
            - 4: Computation states of each strategy context

        Mode 0 must be common to any data-series of the strategy.
        Mode 1 and 2 can be extended by adding members rows tuple(name:value) per row.
        Mode 3 must be common to any contexts of the strategy.
        Mode 4 must be common to any contexts of the strategy.

        The field num-modes must be incremented as many others necessary modes.
        Some tables are row oriented (0, 3 & 4) other are column oriented (1 & 2)

        @param mode integer Additional report context.
        """
        result = {
            'market-id': self.instrument.market_id,
            'activity': self._activity,
            'affinity': self._affinity,
            'initialized': self._initialized == StrategyTraderBase.STATE_NORMAL,
            'checked': self._checked == StrategyTraderBase.STATE_NORMAL,
            'ready': self._initialized == StrategyTraderBase.STATE_NORMAL and self._checked == StrategyTraderBase.STATE_NORMAL and self.ready(),
            'bootstrapping': self._bootstrapping > StrategyTraderBase.STATE_WAITING,
            'preprocessing': self._preprocessing > StrategyTraderBase.PREPROCESSING_STATE_WAITING,
            'training': self._trainer.working if self._trainer else False,
            'members': [],
            'data': [],
            'num-modes': 5
        }

        # mode 0 is reserved to data-series sub
        if mode == 0:
            pass

        elif mode == 1:
            # General strategy trader states
            result['members'] = (
                ("price", "Name"),
                ("price", "Value"),
            )

            result['data'].append((
                "Bid", self.instrument.format_price(self.instrument.market_bid)))

            result['data'].append((
                "Ask", self.instrument.format_price(self.instrument.market_ask)))

            result['data'].append((
                "Spread", self.instrument.format_price(self.instrument.market_spread)))

            if hasattr(self, "price_epsilon"):
                result['data'].append((
                    "Epsilon", self.instrument.format_price(getattr(self, "price_epsilon"))))

            result['data'].append(("----", "----"))

            result['data'].append(("Hedging", "Yes" if self.hedging else "No"))
            result['data'].append(("Reversal", "Yes" if self.reversal else "No"))
            result['data'].append(("Allow-Short", "Yes" if self.allow_short else "No"))
            result['data'].append(("Trade-Short", "Yes" if self.trade_short else "No"))
            result['data'].append(("Region-Allow", "Yes" if self.region_allow else "No"))

            handlers = self.dumps_handlers()
            if handlers:
                result['data'].append(("----", "----"))

                for handler in handlers:
                    result['data'].append(("----", "----"))
                    result['data'] += ([(k, v) for k, v in handler.items()])

        elif mode == 2:
            # General context states
            contexts_ids = ["Context"] + self.contexts_ids()

            # two columns
            result['members'] = tuple(("str", ctx_name) for ctx_name in contexts_ids)

            # 15 initials rows
            result['data'].append(["Mode"])

            result['data'].append(["----"])

            result['data'].append(["Max-Trades"])
            result['data'].append(["Quantity-Mode"])
            result['data'].append(["Quantity-Type"])
            result['data'].append(["Quantity-Size"])
            result['data'].append(["Quantity-Step"])
            result['data'].append(["Max-Amount"])

            result['data'].append(["----"])

            result['data'].append(["Entry"])
            result['data'].append(["Stop-Loss"])
            result['data'].append(["Take-Profit"])
            result['data'].append(["Dynamic Stop-Loss"])
            result['data'].append(["Dynamic Take-Profit"])
            result['data'].append(["Breakeven"])

            for ctx_id in contexts_ids:
                ctx = self.retrieve_context(ctx_id)

                if not ctx:
                    continue

                def print_ex(context, ex):
                    if hasattr(context, ex):
                        ex = getattr(context, ex)
                        if ex:
                            content = []

                            if hasattr(ex, 'type_to_str'):
                                content.append(ex.type_to_str())

                            if ex.timeframe:
                                content.append("tf=%s" % timeframe_to_str(ex.timeframe))

                            if ex.num_bars:
                                content.append("bar=%i" % ex.num_bars)

                            if ex.depth != 0 and hasattr(ex, 'orientation_to_str'):
                                content.append("orientation=%s" % ex.orientation_to_str())

                            if ex.distance and hasattr(ex, 'distance_to_str'):
                                content.append("dist=%s" % ex.distance_to_str(self))

                            if ex.offset and hasattr(ex, 'offset_to_str'):
                                content.append("ofs=%s" % ex.offset_to_str(self))

                            if hasattr(ex, 'timeout_distance_to_str'):
                                if ex.timeout and ex.timeout_distance:
                                    content.append("timeout=%s@%s" % (timeframe_to_str(ex.timeout),
                                                                      ex.timeout_distance_to_str(self)))
                                elif ex.timeout:
                                    content.append("timeout=%s" % timeframe_to_str(ex.timeout))

                            return " ".join(content)

                    return "-"

                trade_quantity = ctx.compute_quantity(self)
                max_amount = trade_quantity * ctx.max_trades

                result['data'][0].append(ctx.mode_to_str())

                result['data'][1].append("----")

                result['data'][2].append("%i" % ctx.max_trades)
                result['data'][3].append(self.instrument.trade_quantity_mode_to_str())
                result['data'][4].append(ctx.trade_quantity_type_to_str())
                result['data'][5].append("%g" % trade_quantity)
                result['data'][6].append("%g" % ctx.trade_quantity_step)
                result['data'][7].append("%g" % max_amount)

                result['data'][8].append("----")

                result['data'][9].append(print_ex(ctx, 'entry'))
                result['data'][10].append(print_ex(ctx, 'stop_loss'))
                result['data'][11].append(print_ex(ctx, 'take_profit'))
                result['data'][12].append(print_ex(ctx, 'dynamic_stop_loss'))
                result['data'][13].append(print_ex(ctx, 'dynamic_take_profit'))
                result['data'][14].append(print_ex(ctx, 'breakeven'))

        elif mode == 3:
            pass

        elif mode == 4:
            pass

        return result

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
            msg = "Not enough free margin in %s, has %s but need %s" % (
                self.instrument.settlement, self.instrument.format_quantity(trader.account.margin_balance),
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
        @param same_timeframe_num 0 mean Allow multiple trade of the same timeframe, else it defines the max allowed.
        """
        result = None

        if self._trades:
            with self._trade_mutex:
                total_num = 0

                for trade in self._trades:
                    # only active and pending trade
                    if trade.is_closed() or trade.is_closing():
                        continue

                    total_num += 1

                if total_num >= max_trades:
                    result = "Total max trades of %s reached for %s" % (max_trades, self.instrument.symbol)

                elif same_timeframe > 0 and same_timeframe_num > 0:
                    for trade in self._trades:
                        # only active and pending trade
                        if trade.is_closed() or trade.is_closing():
                            continue

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
                total_num = 0

                for trade in self._trades:
                    # only active and pending trade
                    if trade.is_closed() or trade.is_closing():
                        continue

                    total_num += 1

                if total_num >= max_trades:
                    result = "Total max trades of %s reached for %s" % (max_trades, self.instrument.symbol)

                elif same_context:
                    if same_context.max_trades <= 0:
                        result = "No trades allowed for context %s for %s" % (same_context.name, self.instrument.symbol)
                    else:
                        # count trade base on the same context
                        same_context_num = 0

                        for trade in self._trades:
                            # only active and pending trade
                            if trade.is_closed() or trade.is_closing():
                                continue

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

    def allowed_trading_session(self, timestamp: float, same_context: Optional[StrategyTraderContext] = None) -> bool:
        """
        @param timestamp Current UTC timestamp in seconds
        @param same_context Context to check with
        @return True if trading is allowed during the session.
        """
        result = None

        if same_context:
            pass

        if self.instrument.has_trading_sessions():
            # compute daily offset in seconds
            today = datetime.utcfromtimestamp(timestamp).replace(tzinfo=UTC()) + timedelta(
                hours=self.instrument.timezone)

            today_time = today.hour * 3600 + today.minute * 60 + today.second

            # monday 1..7
            day_of_week = today.isoweekday()

            allow = False

            for trading_session in self.instrument.trading_sessions:
                # monday is 0
                if trading_session.day_of_week == day_of_week:
                    if trading_session.from_time <= today_time <= trading_session.to_time:
                        allow = True
                        break

            if not allow:
                result = "No trading allowed outside of sessions for %s" % self.instrument.symbol

        if result:
            # logger.warning(result)
            Terminal.inst().notice(result, view='status')
            return False

        return True

    #
    # notification helpers
    #

    def notify_signal(self, timestamp: float, signal: StrategySignal):
        if signal:
            try:
                # system notification
                self.strategy.notify_signal(timestamp, signal, self)
            except Exception as e:
                logger.error(repr(e))

            # stream
            if self._signal_streamer:
                try:
                    self._signal_streamer.member('signal').update(self, signal, timestamp)
                    self._signal_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    def notify_trade_entry(self, timestamp: float, trade: StrategyTrade):
        if trade:
            try:
                # system notification
                self.strategy.notify_trade_entry(timestamp, trade, self)
            except Exception as e:
                logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

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

            # inform handlers
            if self._global_handler:
                with self._mutex:
                    self._global_handler.on_trade_opened(self, trade)

            if self._handlers and trade.context is not None and trade.context.name in self._handlers:
                with self._mutex:
                    self._handlers[trade.context.name].on_trade_opened(self, trade)

    def notify_trade_update(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            try:
                self.strategy.notify_trade_update(timestamp, trade, self)
            except Exception as e:
                logger.error(repr(e))

            # stream
            if self._trade_update_streamer:
                try:
                    self._trade_update_streamer.member('trade-update').update(self, trade, timestamp)
                    self._trade_update_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

            # inform handlers
            if self._global_handler:
                with self._mutex:
                    self._global_handler.on_trade_updated(self, trade)

            if self._handlers and trade.context is not None and trade.context.name in self._handlers:
                with self._mutex:
                    self._handlers[trade.context.name].on_trade_updated(self, trade)

    def notify_trade_exit(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            try:
                self.strategy.notify_trade_exit(timestamp, trade, self)
            except Exception as e:
                logger.error(repr(e))

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

            # inform handlers
            if self._global_handler:
                with self._mutex:
                    self._global_handler.on_trade_exited(self, trade)

            if self._handlers and trade.context is not None and trade.context.name in self._handlers:
                with self._mutex:
                    self._handlers[trade.context.name].on_trade_exited(self, trade)

    def notify_trade_error(self, timestamp: float, trade: StrategyTrade):
        if trade:
            # system notification
            try:
                self.strategy.notify_trade_error(timestamp, trade.id, self)
            except Exception as e:
                logger.error(repr(e))

            # @todo could have a stream

    def notify_alert(self, timestamp: float, alert: Alert, result: dict):
        if alert and result:
            # system notification
            try:
                self.strategy.notify_alert(timestamp, alert, result, self)
            except Exception as e:
                logger.error(repr(e))

            # stream
            if self._alert_streamer:
                try:
                    self._alert_streamer.member('alert').update(self, alert, result, timestamp)
                    self._alert_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    #
    # alerts
    #

    def process_alerts(self, timestamp):
        # check for alert triggers
        if self.alerts:
            alerts = self.check_alerts(timestamp, self.instrument.market_bid, self.instrument.market_ask)

            if alerts:
                for alert, result in alerts:
                    self.notify_alert(timestamp, alert, result)

    #
    # stream helpers
    #
    def setup_streaming(self):
        # global stream about compute status, once per compute frame
        self._global_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_INFO,
                                           self.strategy.identifier, self.instrument.market_id)
        self._global_streamer.add_member(StreamMemberBool('activity'))
        self._global_streamer.add_member(StreamMemberInt('affinity'))
        self._global_streamer.add_member(StreamMemberInt('max-trades'))
        self._global_streamer.add_member(StreamMemberInt('trade-mode'))
        self._global_streamer.add_member(StreamMemberFloat('trade-quantity'))
        self._global_streamer.add_member(StreamMemberDict('context'))

        # trade streams
        self._trade_entry_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_TRADE,
                                                self.strategy.identifier, self.instrument.market_id)
        self._trade_entry_streamer.add_member(StreamMemberTradeEntry('trade-entry'))

        self._trade_update_streamer = Streamable(self.strategy.service.monitor_service,
                                                 Streamable.STREAM_STRATEGY_TRADE,
                                                 self.strategy.identifier, self.instrument.market_id)
        self._trade_update_streamer.add_member(StreamMemberTradeUpdate('trade-update'))

        self._trade_exit_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_TRADE,
                                               self.strategy.identifier, self.instrument.market_id)
        self._trade_exit_streamer.add_member(StreamMemberTradeExit('trade-exit'))

        # signal stream
        self._signal_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_SIGNAL,
                                           self.strategy.identifier, self.instrument.market_id)
        self._signal_streamer.add_member(StreamMemberTradeSignal('signal'))

        # alert stream
        self._alert_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_ALERT,
                                          self.strategy.identifier, self.instrument.market_id)
        self._alert_streamer.add_member(StreamMemberStrategyAlert('alert'))
        self._alert_streamer.add_member(StreamMemberStrategyAlertCreate('add-alert'))
        self._alert_streamer.add_member(StreamMemberStrategyAlertRemove('rm-alert'))

        # region stream
        self._region_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_REGION,
                                           self.strategy.identifier, self.instrument.market_id)
        self._region_streamer.add_member(StreamMemberStrategyRegion('region'))
        self._region_streamer.add_member(StreamMemberStrategyRegionCreate('add-region'))
        self._region_streamer.add_member(StreamMemberStrategyRegionRemove('rm-region'))

    def stream(self):
        # only once per compute frame
        with self._mutex:
            if self._global_streamer:
                self._global_streamer.publish()

    def stream_trade_update(self, timestamp: float, trade: StrategyTrade):
        # not during backtesting to do not flood stream and save CPU
        if self.strategy.service.backtesting:
            return

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
