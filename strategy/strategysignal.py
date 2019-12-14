# @date 2019-01-13
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy signal

from datetime import datetime
from common.signal import Signal

from trader.order import Order
from common.utils import timeframe_to_str, direction_to_str

from instrument.instrument import Instrument

import logging
logger = logging.getLogger('siis.strategy.signal')


class StrategySignal(object):
    """
    Strategy signal.
    The signal is either an entry, either an exit.
    The direction of the signal is complementary to its type.

    Thats mean a long entry or exit always return a long direction (1).
    And so a short entry or exit always return a short direction (-1).

    The order direction can be determined by condition or by multiplying signal * dir.
    Exemple a short exit signal is -1 * -1 = 1 (a long order).

    But note the proper way to exit a trade/position is to use the trade.close method, and
    not to directly create an order.

    - p is the price of the signal
    - sl for stop-loss price
    - tp for take-profit price
    - ts for timestamp (UTC)
    """

    __slots__ = 'timeframe', 'ts', 'signal', 'dir', 'p', 'sl', 'tp', 'entry_timeout', 'expiry', 'label', 'context', '_extra'

    VERSION = "1.0.0"

    SIGNAL_NONE = 0   # signal type undefined (must be entry or exit else its informal)
    SIGNAL_ENTRY = 1  # entry signal (this does not mean long. @see dir)
    SIGNAL_EXIT = -1  # exit signal (this does not mean short. @see dir)

    def __init__(self, timeframe, timestamp):
        self.timeframe = timeframe   # timeframe related to the signal
        self.ts = timestamp          # timestamps of the signal emit
        self.signal = StrategySignal.SIGNAL_NONE  # type of the signal : entry or exit

        self.dir = 0       # signal direction

        self.p = 0.0       # signal price / possible entry-price
        self.sl = 0.0      # possible stop-loss pricce
        self.tp = 0.0      # primary possible take profit price
        self.entry_timeout = 0.0   # trade entry expiration in seconds
        self.expiry = 0.0          # trade expiration if in profit after this delay

        self.label = ""      # signal label
        self.context = None  # can be any object inherited from StrategySignalContext (will be setted as reference to the trade)

        self._extra = {}

    @classmethod
    def version(cls):
        return cls.VERSION

    @property
    def direction(self):
        return self.dir

    @property
    def price(self):
        return self.p

    @property
    def stop_loss(self):
        return self.sl
    
    @property
    def timestamp(self):
        return self.ts    

    @property
    def take_profit(self):
        return self.tp

    #
    # helpers
    #

    def basetime(self):
        """
        Related candle base time of the timestamp of the signal.
        """
        return Instrument.basetime(self.timeframe, self.ts)

    def as_exit(self):
        """
        If the signal is an entry signal, negate it as an exit signal on the opposite direction else return None.
        Stop-loss and take-profit are swapped.
        """
        if self.signal == StrategySignal.SIGNAL_ENTRY:
            negged = StrategySignal(self.timeframe, self.ts)
            negged.signal = StrategySignal.SIGNAL_EXIT

            negged.dir = -self.dir
            negged.p = self.p
            negged.sl = self.tp
            negged.tp = self.sl

            return negged

        return None

    def signal_type_str(self):
        if self.signal == StrategySignal.SIGNAL_ENTRY:
            return "entry"
        elif self.signal == StrategySignal.SIGNAL_EXIT:
            return "exit"

        return "none"

    def direction_str(self):
        if self.dir > 0:
            return "long"
        elif self.dir < 0:
            return "short"
        else:
            return ""

    def dup(self, _from):
        self.timeframe = _from.timeframe
        self.ts = _from.ts
        self.signal = _from.signal

        self.dir = _from.dir
        self.p = _from.p
        self.sl = _from.sl
        self.tp = _from.tp
        
        self.label = _from.label
        self.context = _from.context

    def compare(self, _to):
        """
        Return true of the the signal have the same type in the same direction, no more.
        """
        return self.signal == _to.signal and self.dir == _to.dir

    def __str__(self):
        mydate = datetime.fromtimestamp(self.ts)
        date_str = mydate.strftime('%Y-%m-%d %H:%M:%S')

        return "tf=%s ts=%s signal=%s dir=%s p=%s sl=%s tp=%s %s" % (
                timeframe_to_str(self.timeframe), date_str, self.signal_type_str(), self.direction_str(),
                self.p, self.sl, self.tp, self.label)

    #
    # profit/loss
    #

    def profit(self):
        if self.dir > 0:
            return ((self.tp - self.p) / self.p) if self.p > 0.0 else 0.0
        elif self.dir < 0:
            return ((self.p - self.tp) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def loss(self):
        if self.dir > 0:
            return ((self.p - self.sl) / self.p) if self.p > 0.0 else 0.0
        elif self.dir > 0:
            return ((self.sl - self.p) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def risk_reward(self):
        profit = self.profit()
        loss = self.loss()

        return loss / profit if profit > 0.0 else 0.0

    #
    # extra
    #

    def set(self, key, value):
        """
        Add a key:value paire in the extra member dict of the signal.
        It allow to add you internal trade data, states you want to keep during the live of the trade and even in persistency
        """
        self._extra[key] = value

    def unset(self, key):
        """Remove a previously set extra key"""
        if key in self._extra:
            del self._extra[key]

    def get(self, key, default=None):
        """Return a value for a previously defined key or default value if not exists"""
        return self._extra.get(key, default)

    #
    # helpers
    #

    def timeframe_to_str(self):
        return timeframe_to_str(self.timeframe)

    def direction_to_str(self):
        return direction_to_str(self.dir)

    def direction_from_str(self, direction):
        return direction_from_str(direction)

    #
    # dumps for notify/history
    #


    def dump_timestamp(self, timestamp, v1=False):
        if v1:
            return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def dumps_notify(self, timestamp, strategy_trader):
        """
        Dumps to dict for notify/history, same format as for StrategyTrade.
        """
        if self.signal == StrategySignal.SIGNAL_ENTRY:
            return {
                'version': self.version(),
                'trade': "signal",
                'id': -1,
                'app-name': strategy_trader.strategy.name,
                'app-id': strategy_trader.strategy.identifier,
                'timestamp': timestamp,
                'symbol': strategy_trader.instrument.market_id,
                'way': "entry",
                'entry-timeout': timeframe_to_str(self.entry_timeout),
                'expiry': self.expiry,
                'timeframe': timeframe_to_str(self.timeframe),
                'is-user-trade': False,
                'label': self.label,
                'direction': self.direction_to_str(),
                'order-price': strategy_trader.instrument.format_price(self.p),
                'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
                'take-profit-price': strategy_trader.instrument.format_price(self.tp),
                'entry-open-time': self.dump_timestamp(self.ts),
            }
        elif self.signal == StrategySignal.SIGNAL_EXIT:
            return {
                'version': self.version(),
                'trade': "signal",
                'id': -1,
                'app-name': strategy_trader.strategy.name,
                'app-id': strategy_trader.strategy.identifier,
                'timestamp': timestamp,
                'symbol': strategy_trader.instrument.market_id,
                'way': "exit",
                'entry-timeout': timeframe_to_str(self.entry_timeout),
                'expiry': self.expiry,
                'timeframe': timeframe_to_str(self.timeframe),
                'is-user-trade': False,
                'label': self.label,
                'direction': self.direction_to_str(),
                'take-profit-price': strategy_trader.instrument.format_price(self.tp),
                'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
                'exit-open-time': self.dump_timestamp(self.ts),
            }
