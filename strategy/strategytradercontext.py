# @date 2019-01-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy trader context

from common.utils import timeframe_from_str


class StrategyTraderContextBuilder(object):
    """
    To be implemented by strategy to have specific context trade persistence.
    """

    @classmethod
    def loads(cls, data, strategy_trader):
        return None


class StrategyTraderContextBase(object):
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

    def dumps(self) -> dict:
        return {}

    def loads(self, strategy_trader, params: dict):
        pass


class EntryExit(object):

    EX_UNDEFINED = 0
    EX_ENTRY = 1
    EX_TAKE_PROFIT = 2
    EX_STOP_LOSS = 3
    EX_BREAKEVEN = 4

    @classmethod
    def ex(cls) -> int:
        return cls.EX_UNDEFINED

    @classmethod
    def name(cls) -> str:
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
        self.type = StrategyTraderContext.PRICE_NONE
        self.timeframe = "15m"
        self.depth = 1
        self.multi = False
        self.orientation = StrategyTraderContext.ORIENTATION_UP
        self.timeout = 0.0

        self.distance = 0.0  # usage depends of distance_type, could be a fixed distance or a max distance
        self.distance_type = StrategyTraderContext.PRICE_NONE

        self.timeout_distance = 0.0
        self.timeout_distance_type = StrategyTraderContext.PRICE_NONE

    def loads(self, strategy_trader, params: dict):
        if 'type' not in params or params.get('type') not in StrategyTraderContext.PRICE:
            raise ValueError("Undefined or unsupported 'type' value for %s" % self.name())

        self.type = StrategyTraderContext.PRICE.get(params['type'])
        self.timeframe = timeframe_from_str(params.get('timeframe', "t"))

        # ATR SR need orientation and depth parameters
        if self.type in (StrategyTraderContext.PRICE_ATR_SR,):
            if 'orientation' not in params or params.get('orientation') not in StrategyTraderContext.ORIENTATION:
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
        self.orientation = StrategyTraderContext.ORIENTATION.get(params.get('orientation', 'up'))

        # standard distance
        distance = params.get('distance', "0.0")
        if type(distance) is not str:
            raise ValueError("Invalid format 'distance' must be string for %s" % self.name())

        if distance.endswith('%'):
            # in percent from entry price or limit price
            self.distance = float(distance[:-1]) * 0.01
            self.distance_type = StrategyTraderContext.PRICE_FIXED_PCT

        elif distance.endswith('pip'):
            # in pips from entry price or limit price
            self.distance = float(distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.distance_type = StrategyTraderContext.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.distance = float(distance)
            self.distance_type = StrategyTraderContext.PRICE_FIXED_DIST

        # timeout distance
        timeout_distance = params.get('timeout-distance', "0.0")
        if type(timeout_distance) is not str:
            raise ValueError("Invalid format 'timeout-distance' must be string for %s" % self.name())

        if timeout_distance.endswith('%'):
            # in percent from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-1]) * 0.01
            self.timeout_distance_type = StrategyTraderContext.PRICE_FIXED_PCT

        elif timeout_distance.endswith('pip'):
            # in pips from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.timeout_distance_type = StrategyTraderContext.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.timeout_distance = float(timeout_distance)
            self.timeout_distance_type = StrategyTraderContext.PRICE_FIXED_DIST

    def modify_distance(self, strategy_trader, distance):
        if type(distance) is str and distance.endswith('%'):
            # in percent from entry price or limit price
            self.distance = float(distance[:-1]) * 0.01
            self.distance_type = StrategyTraderContext.PRICE_FIXED_PCT

        elif type(distance) is str and distance.endswith('pip'):
            # in pips from entry price or limit price
            self.distance = float(distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.distance_type = StrategyTraderContext.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.distance = float(distance)
            self.distance_type = StrategyTraderContext.PRICE_FIXED_DIST

    def modify_timeout_distance(self, strategy_trader, timeout_distance: str):
        if type(timeout_distance) is str and timeout_distance.endswith('%'):
            # in percent from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-1]) * 0.01
            self.timeout_distance_type = StrategyTraderContext.PRICE_FIXED_PCT

        elif type(timeout_distance) is str and timeout_distance.endswith('pip'):
            # in pips from entry price or limit price
            self.timeout_distance = float(timeout_distance[:-3]) * strategy_trader.instrument.one_pip_means
            self.timeout_distance_type = StrategyTraderContext.PRICE_FIXED_DIST

        else:
            # in price from entry price or limit price
            self.timeout_distance = float(timeout_distance)
            self.timeout_distance_type = StrategyTraderContext.PRICE_FIXED_DIST

    def modify_orientation(self, orientation: str):
        self.orientation = StrategyTraderContext.ORIENTATION.get(orientation, StrategyTraderContext.ORIENTATION_UP)

    def distance_to_str(self, strategy_trader) -> str:
        if self.distance_type == StrategyTraderContext.PRICE_FIXED_PCT:
            return "%.2f%%" % (self.distance * 100.0)
        elif self.distance_type == StrategyTraderContext.PRICE_FIXED_DIST:
            return strategy_trader.instrument.format_price(self.distance)
        else:
            return strategy_trader.instrument.format_price(self.distance)

    def timeout_distance_to_str(self, strategy_trader) -> str:
        if self.timeout_distance_type == StrategyTraderContext.PRICE_FIXED_PCT:
            return "%.2f%%" % (self.timeout_distance * 100.0)
        elif self.timeout_distance_type == StrategyTraderContext.PRICE_FIXED_DIST:
            return strategy_trader.instrument.format_price(self.timeout_distance)
        else:
            return strategy_trader.instrument.format_price(self.timeout_distance)

    def orientation_to_str(self) -> str:
        return StrategyTraderContext.ORIENTATION_FROM_STR_MAP.get(self.orientation)

    def type_to_str(self):
        return StrategyTraderContext.PRICE_FROM_STR_MAP.get(self.type)

    def compile(self, strategy_trader):
        if strategy_trader.is_timeframes_based:
            self.timeframe = strategy_trader.timeframes.get(self.timeframe)
            if not self.timeframe:
                raise ValueError("Timeframe model not found for 'timeframe' for %s" % self.name())
        elif strategy_trader.is_tickbars_based:
            self.timeframe = None

    def dumps(self) -> dict:
        result = {}

        # @todo

        return result


class EXEntry(EntryExit):

    @classmethod
    def ex(cls) -> int:
        return cls.EX_ENTRY

    def __init__(self):
        super().__init__()

        self.cautious = True
        
        self.risk = 0.0
        self.reward = 0.0
        self.max_spread = 0.0

    def loads(self, strategy_trader, params: dict):
        super().loads(strategy_trader, params)

        # mandatory timeout
        if not self.timeout:
            raise ValueError("Undefined or unsupported 'timeout' value for %s" % self.name())

        # optional cautious, true by default
        self.cautious = params.get('cautious', True)

        # risk, 0.0 mean no check
        risk = params.get('risk', 0.0)
        if type(risk) in (float, int):
            # value in delta price
            self.risk = risk
        elif type(risk) is not str:
            raise ValueError("Invalid format 'risk' must be string, int or float for %s" % self.name())

        if risk.endswith('pip'):
            # value in pips
            self.risk = float(risk[:-3]) * strategy_trader.instrument.one_pip_means

        # reward
        reward = params.get('reward', 0.0)
        if type(reward) in (float, int):
            # value in delta price
            self.risk = reward
        elif type(reward) is not str:
            raise ValueError("Invalid format 'reward' must be string, int or float for %s" % self.name())

        if reward.endswith('pip'):
            # value in pips
            self.reward = float(reward[:-3]) * strategy_trader.instrument.one_pip_means

        # max-spread
        max_spread = params.get('max-spread', 0.0)
        if type(max_spread) in (float, int):
            # value in delta price
            self.max_spread = max_spread
        elif type(max_spread) is not str:
            raise ValueError("Invalid format 'max-spread' must be string, int or float for %s" % self.name())

        if max_spread.endswith('pip'):
            # value in pips
            self.max_spread = float(max_spread[:-3]) * strategy_trader.instrument.one_pip_means

    def dumps(self) -> dict:
        result = super().dumps()

        # @todo

        return result


class EXTakeProfit(EntryExit):

    @classmethod
    def ex(cls) -> int:
        return cls.EX_TAKE_PROFIT

    def __init__(self):
        super().__init__()

    def loads(self, strategy_trader, params: dict):
        super().loads(strategy_trader, params)

    def dumps(self) -> dict:
        result = super().dumps()

        # @todo

        return result


class EXStopLoss(EntryExit):

    @classmethod
    def ex(cls):
        return cls.EX_STOP_LOSS

    def __init__(self):
        super().__init__()

    def loads(self, strategy_trader, params: dict):
        super().loads(strategy_trader, params)

    def dumps(self) -> dict:
        result = super().dumps()

        # @todo

        return result


class EXBreakeven(EntryExit):

    @classmethod
    def ex(cls):
        return cls.EX_BREAKEVEN

    def __init__(self):
        super().__init__()

    def loads(self, strategy_trader, params: dict):
        super().loads(strategy_trader, params)

    def dumps(self) -> dict:
        result = super().dumps()

        # @todo

        return result


class StrategyTraderContext(StrategyTraderContextBase):

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
    TRADE_QUANTITY_MANAGED = 4               # managed by a handler

    TRADE_QUANTITY = {
        'normal': TRADE_QUANTITY_NORMAL,
        'specific': TRADE_QUANTITY_SPECIFIC,
        'reinvest-max-last': TRADE_QUANTITY_REINVEST_MAX_LAST,
        'increment-step': TRADE_QUANTITY_INC_STEP,
        'managed': TRADE_QUANTITY_MANAGED
    }

    TRADE_QUANTITY_FROM_STR_MAP = {
        TRADE_QUANTITY_NORMAL: 'normal',
        TRADE_QUANTITY_SPECIFIC: 'specific',
        TRADE_QUANTITY_REINVEST_MAX_LAST: 'reinvest-max-last',
        TRADE_QUANTITY_INC_STEP: 'increment-step',
        TRADE_QUANTITY_MANAGED: 'managed'
    }

    def __init__(self, name: str):
        super().__init__()

        self.name = name
        self.mode = StrategyTraderContext.MODE_NONE
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

        self.long_call = None
        self.short_call = None

        self.max_trades = 0  # >0 limit the number of trade for the context

        self.trade_quantity_type = StrategyTraderContext.TRADE_QUANTITY_NORMAL  # mode
        self.trade_quantity = 0.0       # last realized max trade exit quantity or specific value
        self.trade_quantity_step = 0.0  # step of increment

    def loads(self, strategy_trader, params: dict):
        self.max_trades = max(0, params.get('max-trades', 0))

    def compile(self, strategy_trader):
        pass

    def dumps(self) -> dict:
        # @todo others members (and specializations)
        result = {
            'name': self.name
        }

        return result

    def compute_quantity(self, strategy_trader) -> float:
        if self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_NORMAL:
            # quantity is defined by instrument
            return strategy_trader.instrument.trade_quantity
        elif self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_MANAGED:
            # quantity is defined by context, else by instrument
            return self.trade_quantity if self.trade_quantity > 0 else strategy_trader.instrument.trade_quantity
        elif self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_SPECIFIC:
            # quantity is defined by context
            return self.trade_quantity
        elif self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_REINVEST_MAX_LAST:
            # quantity is defined by context, else by instrument
            return self.trade_quantity if self.trade_quantity > 0 else strategy_trader.instrument.trade_quantity
        elif self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_INC_STEP:
            # quantity is defined by context, else by instrument
            return self.trade_quantity if self.trade_quantity > 0 else strategy_trader.instrument.trade_quantity

        return 0.0

    def mode_to_str(self) -> str:
        if self.mode == StrategyTraderContext.MODE_NONE:
            return 'none'
        elif self.mode == StrategyTraderContext.MODE_SIGNAL:
            return 'signal'
        elif self.mode == StrategyTraderContext.MODE_TRADE:
            return 'trade'

        return 'unknown'

    def trade_quantity_type_to_str(self) -> str:
        return StrategyTraderContext.TRADE_QUANTITY_FROM_STR_MAP.get(self.trade_quantity_type)

    def modify_trade_quantity_type(self, instrument, trade_quantity_type: str, value: float = 0.0) -> bool:
        """
        @param instrument
        @param trade_quantity_type str String trade quantity type.
        @param value trade quantity for specific type, or step value
        """
        trade_quantity_type = StrategyTraderContext.TRADE_QUANTITY.get(trade_quantity_type)

        if trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_NORMAL:
            self.trade_quantity = 0.0
            self.trade_quantity_step = 0.0
            self.trade_quantity_type = trade_quantity_type

            return True

        elif trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_SPECIFIC:
            if value >= 0.0:
                self.trade_quantity = value
                self.trade_quantity_step = 0.0
                self.trade_quantity_type = trade_quantity_type

                return True

        elif trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_INC_STEP:
            if value > 0.0:
                if self.trade_quantity <= 0.0:
                    # initialize
                    self.trade_quantity = instrument.trade_quantity

                self.trade_quantity_step = value
                self.trade_quantity_type = trade_quantity_type

                return True

        elif trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_MANAGED:
            if value > 0.0:
                self.trade_quantity_step = value
                self.trade_quantity_type = trade_quantity_type

                return True

        elif trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_REINVEST_MAX_LAST:
            if self.trade_quantity <= 0.0:
                # initialize
                self.trade_quantity = instrument.trade_quantity

            self.trade_quantity_step = 0.0
            self.trade_quantity_type = trade_quantity_type

            return True

        return False

    def modify_trade_quantity(self, value: float = 0.0) -> bool:
        """
        Only if TRADE_QUANTITY_SPECIFIC is the current trade_quantity_type.
        @param value trade quantity for specific type, or step value
        @return True if value is greater or equal to zero and current trade quantity mode is set to specific.
        """
        if self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_SPECIFIC:
            if value >= 0.0:
                self.trade_quantity = value
                return True

        return False

    def modify_trade_step(self, value: float = 0.0) -> bool:
        """
        Only if TRADE_QUANTITY_INC_STEP is the current trade_quantity_type.
        @param value trade quantity step for specific type, or step value
        """
        if self.trade_quantity_type == StrategyTraderContext.TRADE_QUANTITY_INC_STEP:
            if value >= 0.0:
                self.trade_quantity_step = value
                return True

        return False
