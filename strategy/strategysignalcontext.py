# @date 2019-01-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy signal context

from common.utils import timeframe_from_str


class StrategySignalContextBuilder(object):
    """
    To be implemented by strategy to have specific context trade persistence.
    """

    @classmethod
    def loads(cls, data, strategy_trader):
        return None


class StrategySignalContext(object):
    """
    Base model for any signal/trade context.
    """

    MODE_NONE = 0
    MODE_SIGNAL = 1
    MODE_TRADE = 2

    MODE = {
        'disabled': MODE_NONE,
        'none': MODE_NONE,
        'signal': MODE_SIGNAL,
        'enabled': MODE_TRADE,
        'trade': MODE_TRADE
    }

    def __init__(self):
        pass

    def dumps(self):
        return {}

    def loads(self, strategy_trader, params):
        pass


class EntryExit(object):

    EX_UNDEFINED = 0
    EX_ENTRY = 1
    EX_TAKE_PROFIT = 2
    EX_STOP_LOSS = 3
    EX_BREAKEVEN = 4

    @classmethod
    def ex(cls):
        return cls.EX_UNDEFINED

    @classmethod
    def name(cls):
        if cls.ex() == cls.EX_ENTRY:
            return "entry"
        elif cls.ex() == cls.EX_TAKE_PROFIT:
            return "take-profit"
        elif cls.ex() == cls.EX_STOP_LOSS:
            return "stop-loss"
        elif cls.ex() == cls.EX_BREAKEVEN:
            return "breakeven"
        else:
            return "undefined"

    def __init__(self):
        self.type = BaseSignal.PRICE_NONE
        self.timeframe = "15m"
        self.depth = 1
        self.multi = False
        self.orientation = BaseSignal.ORIENTATION_UP
        self.timeout = 0.0

        self.distance = 0.0
        self.distance_type = BaseSignal.PRICE_NONE

        self.timeout_distance = 0.0
        self.timeout_distance_type = BaseSignal.PRICE_NONE

    def loads(self, strategy_trader, params):
        if 'type' not in params or params.get('type') not in BaseSignal.PRICE:
            raise ValueError("Undefined or unsupported 'type' value for %s" % self.name())

        self.type = BaseSignal.PRICE.get(params['type'])
        self.timeframe = timeframe_from_str(params.get('timeframe', "t"))

        # ATR SR need orientation and depth parameters
        if self.type in (BaseSignal.PRICE_ATR_SR,):
            if 'orientation' not in params or params.get('orientation') not in BaseSignal.ORIENTATION:
                raise ValueError("Undefined or unsupported 'orientation' value for %s" % self.name())

            if 'depth' not in params:
                raise ValueError("Undefined 'depth' value for %s" % self.name())

        if self.timeframe < 0:
            raise ValueError("Undefined or unsupported 'timeframe' value for %s" % self.name())

        if params.get('timeout'):
            # optional timeout
            self.timeout = timeframe_from_str(params.get('timeout', ""))

        self.depth = params.get('depth', 1)
        self.multi = params.get('multi', False)
        self.orientation = BaseSignal.ORIENTATION.get(params.get('orientation', 'up'))

        distance = params.get('distance', "0.0")

        if distance.endswith('%'):
            # in percent from entry price or limit price
            self.distance = float(distance[:-1]) * 0.01
            self.distance_type = BaseSignal.PRICE_FIXED_PCT

        elif distance.endswith('pip'):
            # in pips from entry price or limit price
            self.distance = float(distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.distance_type = BaseSignal.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.distance = float(distance)
            self.distance_type = BaseSignal.PRICE_FIXED_DIST

        timeout_distance = params.get('timeout-distance', "0.0")

        if timeout_distance.endswith('%'):
            # in percent from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-1]) * 0.01
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_PCT

        elif timeout_distance.endswith('pip'):
            # in pips from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.timeout_distance = float(timeout_distance)
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_DIST

    def modify_distance(self, strategy_trader, distance):
        if type(distance) is str and distance.endswith('%'):
            # in percent from entry price or limit price
            self.distance = float(distance[:-1]) * 0.01
            self.distance_type = BaseSignal.PRICE_FIXED_PCT

        elif type(distance) is str and distance.endswith('pip'):
            # in pips from entry price or limit price
            self.distance = float(distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.distance_type = BaseSignal.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.distance = float(distance)
            self.distance_type = BaseSignal.PRICE_FIXED_DIST

    def modify_timeout_distance(self, strategy_trader, timeout_distance):
        if type(timeout_distance) is str and timeout_distance.endswith('%'):
            # in percent from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-1]) * 0.01
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_PCT

        elif type(timeout_distance) is str and timeout_distance.endswith('pip'):
            # in pips from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.timeout_distance = float(timeout_distance)
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_DIST

    def modify_orientation(self, orientation):
        self.orientation = BaseSignal.ORIENTATION.get(orientation, BaseSignal.ORIENTATION_UP)

    def distance_to_str(self, strategy_trader):
        if self.distance_type == BaseSignal.PRICE_FIXED_PCT:
            return "%.2f%%" % (self.distance * 100.0)
        elif self.distance_type == BaseSignal.PRICE_FIXED_DIST:
            return strategy_trader.instrument.format_price(self.distance)
        else:
            return strategy_trader.instrument.format_price(self.distance)

    def timeout_distance_to_str(self, strategy_trader):
        if self.timeout_distance_type == BaseSignal.PRICE_FIXED_PCT:
            return "%.2f%%" % (self.timeout_distance * 100.0)
        elif self.timeout_distance_type == BaseSignal.PRICE_FIXED_DIST:
            return strategy_trader.instrument.format_price(self.timeout_distance)
        else:
            return strategy_trader.instrument.format_price(self.timeout_distance)

    def orientation_to_str(self):
        return BaseSignal.ORIENTATION_FROM_STR_MAP.get(self.orientation)

    def type_to_str(self):
        return BaseSignal.PRICE_FROM_STR_MAP.get(self.type)

    def compile(self, strategy_trader):
        if strategy_trader.is_timeframes_based:
            self.timeframe = strategy_trader.timeframes.get(self.timeframe)
            if not self.timeframe:
                raise ValueError("Timeframe model not found for 'timeframe' for %s" % self.name())
        elif strategy_trader.is_tickbars_based:
            self.timeframe = None

    def dumps(self):
        result = {}

        # @todo

        return result


class EXEntry(EntryExit):

    @classmethod
    def ex(cls):
        return cls.EX_ENTRY

    def __init__(self):
        super().__init__()

        self.cautious = True
        
        self.risk = 0.0
        self.reward = 0.0
        self.max_spread = 0.0

    def loads(self, strategy_trader, params):
        super().loads(strategy_trader, params)

        # mandatory timeout
        if not self.timeout:
            raise ValueError("Undefined or unsupported 'timeout' value for %s" % self.name())

        # optional cautious, true by default
        self.cautious = params.get('cautious', True)

        # 0.0 mean no check
        self.risk = params.get('risk', 0.0)
        self.reward = params.get('reward', 0.0)
        self.max_spread = params.get('max-spread', 0.0)

    def dumps(self):
        result = super().dumps()

        # @todo

        return result


class EXTakeProfit(EntryExit):

    @classmethod
    def ex(cls):
        return cls.EX_TAKE_PROFIT

    def __init__(self):
        super().__init__()

    def loads(self, strategy_trader, params):
        super().loads(strategy_trader, params)

    def dumps(self):
        result = super().dumps()

        # @todo

        return result


class EXStopLoss(EntryExit):

    @classmethod
    def ex(cls):
        return cls.EX_STOP_LOSS

    def __init__(self):
        super().__init__()

    def loads(self, strategy_trader, params):
        super().loads(strategy_trader, params)

    def dumps(self):
        result = super().dumps()

        # @todo

        return result


class EXBreakeven(EntryExit):

    @classmethod
    def ex(cls):
        return cls.EX_BREAKEVEN

    def __init__(self):
        super().__init__()

    def loads(self, strategy_trader, params):
        super().loads(strategy_trader, params)

    def dumps(self):
        result = super().dumps()

        # @todo

        return result


class BaseSignal(StrategySignalContext):

    PRICE_NONE = 0
    PRICE_FIXED_PCT = 1
    PRICE_FIXED_DIST = 2
    PRICE_HL2 = 3
    PRICE_ICHIMOKU = 4
    PRICE_BOLLINGER = 5
    PRICE_ATR_SR = 6
    PRICE_LAST = 7
    PRICE_CUR_ATR_SR = 8
    PRICE_HMA = 9
    PRICE_VOL_SR = 10

    PRICE = {
        'none': PRICE_NONE,
        'fixed-pct': PRICE_FIXED_PCT,
        'fixed-dist': PRICE_FIXED_DIST,
        'hl2': PRICE_HL2,
        'bollinger': PRICE_BOLLINGER,
        'ichimoku': PRICE_ICHIMOKU,
        'atrsr': PRICE_ATR_SR,
        'last': PRICE_LAST,
        'cur-atrsr': PRICE_CUR_ATR_SR,
        'hma': PRICE_HMA,
        'vol-sr': PRICE_VOL_SR,
    }

    PRICE_FROM_STR_MAP = {v: k for k, v in PRICE.items()}

    ORIENTATION_UP = 1
    ORIENTATION_DN = -1
    ORIENTATION_BOTH = 0

    ORIENTATION = {
        'up': ORIENTATION_UP,
        'upper': ORIENTATION_UP,
        'high': ORIENTATION_UP,
        'higher': ORIENTATION_UP,
        'dn': ORIENTATION_DN,
        'down': ORIENTATION_DN,
        'low': ORIENTATION_DN,
        'lower': ORIENTATION_DN,
        'both': ORIENTATION_BOTH
    }

    ORIENTATION_FROM_STR_MAP = {
        ORIENTATION_UP: 'up',
        ORIENTATION_DN: 'down',
        ORIENTATION_BOTH: 'both'
    }

    TRADE_QUANTITY_NORMAL = 0                # use normal trade quantity from the instrument
    TRADE_QUANTITY_SPECIFIC = 1              # use the context defined quantity, not the one from the instrument
    TRADE_QUANTITY_REINVEST_MAX_LAST = 2     # reuse the last exited quantity for the next trades
    TRADE_QUANTITY_INC_STEP = 3              # at each exit increase the quantity of a fixed size
    # for any of the strategy-traders, share the total amount and increment by step of specified value
    TRADE_QUANTITY_GLOBAL_SHARE = 4

    TRADE_QUANTITY = {
        'normal': TRADE_QUANTITY_NORMAL,
        'specific': TRADE_QUANTITY_SPECIFIC,
        'reinvest-max-last': TRADE_QUANTITY_REINVEST_MAX_LAST,
        'increment-step': TRADE_QUANTITY_INC_STEP,
        'global-share': TRADE_QUANTITY_GLOBAL_SHARE
    }

    TRADE_QUANTITY_FROM_STR_MAP = {
        TRADE_QUANTITY_NORMAL: 'normal',
        TRADE_QUANTITY_SPECIFIC: 'specific',
        TRADE_QUANTITY_REINVEST_MAX_LAST: 'reinvest-max-last',
        TRADE_QUANTITY_INC_STEP: 'increment-step',
        TRADE_QUANTITY_GLOBAL_SHARE: 'global-share'
    }

    def __init__(self, name):
        super().__init__()

        self.name = name
        self.mode = BaseSignal.MODE_NONE
        self.min_profit = 0.0
        self.compiled = False

        self.entry = EXEntry()
        self.take_profit = EXTakeProfit()
        self.stop_loss = EXStopLoss()
        self.dynamic_take_profit = None
        self.dynamic_stop_loss = None
        self.breakeven = None

        self.pre_signal = None   # runtime current pullback pre-signal
        self.last_signal = None  # runtime last generated strategy signal

        self.disengagements = []  # @todo loads/compile

        self.long_call = None
        self.short_call = None

        self.max_trades = 0  # >0 limit the number of trade for the context

        self.trade_quantity_type = BaseSignal.TRADE_QUANTITY_NORMAL  # mode
        self.trade_quantity = 0.0       # last realized max trade exit quantity or specific value
        self.trade_quantity_step = 0.0  # step of increment

    def loads(self, strategy_trader, params):
        self.max_trades = max(0, params.get('max-trades', 0))

    def compile(self, strategy_trader):
        pass

    def dumps(self):
        result = {
            'name': self.name
        }

        return result

    def compute_quantity(self, instrument):
        if self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_NORMAL:
            return instrument.trade_quantity
        elif self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_SPECIFIC:
            return self.trade_quantity
        elif self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_REINVEST_MAX_LAST:
            return self.trade_quantity if self.trade_quantity > 0 else instrument.trade_quantity
        elif self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_INC_STEP:
            return self.trade_quantity if self.trade_quantity > 0 else instrument.trade_quantity
        elif self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_GLOBAL_SHARE:
            return self.trade_quantity if self.trade_quantity > 0 else instrument.trade_quantity
        else:
            return 0.0

    def update_quantity(self, instrument, trade_quantity):
        if self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_REINVEST_MAX_LAST:
            if self.trade_quantity <= 0.0:
                # initialize to instrument quantity
                self.trade_quantity = self.trade_quantity

            if trade_quantity > self.trade_quantity:
                self.trade_quantity = trade_quantity

        elif self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_INC_STEP:
            if self.trade_quantity <= 0.0:
                # initialize to instrument quantity
                self.trade_quantity = instrument.trade_quantity

            if self.trade_quantity_step > 0.0:
                # add the increment by one step
                self.trade_quantity += self.trade_quantity_step

        elif self.trade_quantity_type == BaseSignal.TRADE_QUANTITY_GLOBAL_SHARE:
            if self.trade_quantity <= 0.0:
                # initialize to instrument quantity
                self.trade_quantity = instrument.trade_quantity

            if trade_quantity > self.trade_quantity:
                # set the new trade global share quantity
                self.trade_quantity = trade_quantity

    def mode_to_str(self):
        if self.mode == BaseSignal.MODE_NONE:
            return 'none'
        elif self.mode == BaseSignal.MODE_SIGNAL:
            return 'signal'
        elif self.mode == BaseSignal.MODE_TRADE:
            return 'trade'
        
        return 'unknown'

    def trade_quantity_type_to_str(self):
        return BaseSignal.TRADE_QUANTITY_FROM_STR_MAP.get(self.trade_quantity_type)

    def modify_trade_quantity_type(self, trade_quantity_type, value=0.0):
        """
        @param trade_quantity_type str String trade quantity type.
        @param value trade quantity for specific type, or step value
        """
        trade_quantity_type = BaseSignal.TRADE_QUANTITY.get(trade_quantity_type)

        if trade_quantity_type == BaseSignal.TRADE_QUANTITY_NORMAL:
            self.trade_quantity = 0.0
            self.trade_quantity_step = 0.0

        elif trade_quantity_type == BaseSignal.TRADE_QUANTITY_SPECIFIC:
            if value >= 0.0:
                self.trade_quantity = value
                self.trade_quantity_step = 0.0

        elif trade_quantity_type == BaseSignal.TRADE_QUANTITY_INC_STEP:
            if value > 0.0:
                self.trade_quantity_step = value

        elif trade_quantity_type == BaseSignal.TRADE_QUANTITY_GLOBAL_SHARE:
            if value > 0.0:
                self.trade_quantity_step = value

        self.trade_quantity_type = trade_quantity_type
