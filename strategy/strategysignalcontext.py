# @date 2019-01-13
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy signal context

from common.utils import timeframe_from_str


class StrategySignalContextBuilder(object):
    """
    To be implemented by strategy to have specific context trade persistence.
    """

    @classmethod
    def loads(cls, data):
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

    def loads(self, data):
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

        if 'orientation' not in params or params.get('orientation') not in BaseSignal.ORIENTATION:
            raise ValueError("Undefined or unsupported 'orientation' value for %s" % self.name())

        self.type = BaseSignal.PRICE.get(params['type'])
        self.timeframe = timeframe_from_str(params.get('timeframe', ""))

        if params.get('timeout'):
            # optionnal timeout
            self.timeout = timeframe_from_str(params.get('timeout', ""))
            if not self.timeframe:
                raise ValueError("Undefined or unsupported 'timeframe' value for %s" % self.name())

        self.depth = params.get('depth', 1)
        self.multi = params.get('multi', False)
        self.orientation = BaseSignal.ORIENTATION.get(params['orientation'])

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
            self.timeout_distance = float(timeout_distance[:-3]) * strategy.instrument.one_pip_means
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.timeout_distance = float(timeout_distance)
            self.timeout_distance_type = BaseSignal.PRICE_FIXED_DIST

    def compile(self, strategy_trader):
        self.timeframe = strategy_trader.timeframes.get(self.timeframe)
        if not self.timeframe:
            raise ValueError("Timeframe model not found for 'timeframe' for %s" % self.name())

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
    }

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

    def __init__(self, name):
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

    def loads(self, strategy_trader, params):
        pass

    def compile(self, strategy_trader):
        pass

    def dumps(self):
        result = {}

        # @todo

        return result
