# @date 2019-01-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy signal

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .strategytrader import StrategyTrader

from datetime import datetime

from trader.order import Order, order_type_to_str
from common.utils import timeframe_to_str, direction_to_str, direction_from_str

from instrument.instrument import Instrument

import logging
logger = logging.getLogger('siis.strategy.signal')


class StrategySignal(object):
    """
    Strategy signal.
    The signal is either an entry, either an exit.
    The direction of the signal is complementary to its type.

    Means a long entry or exit always return a long direction (1).
    And so a short entry or exit always return a short direction (-1).

    The order direction can be determined by condition or by multiplying signal * dir.
    Example a short exit signal is -1 * -1 = 1 (a long order).

    But note the proper way to exit a trade/position is to use the trade.close method, and
    not to directly create an order.

    - p is the price of the signal
    - sl for stop-loss price
    - tp for take-profit price
    - tp2 for second optional (if tp defined and tp2>tp) take-profit price
    - tp3 for third optional (if tp2 defined and tp3>tp2) take-profit price
    - ts for timestamp (UTC)
    """

    __slots__ = 'timeframe', 'ts', 'signal', 'dir', 'p', 'sl', 'tp', 'entry_timeout', 'expiry', 'label', \
        'context', '_extra', 'order_type', 'quantity', 'tp2', 'tp3'

    VERSION = "1.0.0"

    SIGNAL_NONE = 0   # signal type undefined (must be entry or exit else its informal)
    SIGNAL_ENTRY = 1  # entry signal (this does not mean long. @see dir)
    SIGNAL_EXIT = -1  # exit signal (this does not mean short. @see dir)

    def __init__(self, timeframe: float, timestamp: float):
        self.timeframe = timeframe   # timeframe related to the signal
        self.ts = timestamp          # timestamps of the signal emit
        self.signal = StrategySignal.SIGNAL_NONE  # type of the signal : entry or exit

        self.dir = 0       # signal direction

        self.p = 0.0       # signal price / possible entry-price
        self.sl = 0.0      # possible stop-loss price
        self.tp = 0.0      # primary possible take profit price (max TP if sec and mid are defined)

        self.tp2 = 0.0     # optional second take profit price. must be greater than first take profit
        self.tp3 = 0.0     # optional third take profit price. must be greater than second take profit

        self.quantity = 0  # define quantity, if 0 default configured value is used

        self.entry_timeout = 0.0   # trade entry expiration in seconds
        self.expiry = 0.0          # trade expiration if in profit after this delay

        self.label = ""      # signal label
        self.context = None  # can be any object inherited from StrategySignalContext (will be set as ref to trade)

        self.order_type = Order.ORDER_MARKET

        self._extra = {}

    @classmethod
    def version(cls) -> str:
        return cls.VERSION

    @property
    def direction(self) -> int:
        return self.dir

    @property
    def price(self) -> float:
        return self.p

    @property
    def stop_loss(self) -> float:
        return self.sl
    
    @property
    def timestamp(self) -> float:
        return self.ts    

    @property
    def take_profit(self) -> float:
        return self.tp

    @property
    def second_take_profit(self) -> float:
        return self.tp2

    @property
    def third_take_profit(self) -> float:
        return self.tp3

    @property
    def avg_take_profit(self) -> float:
        avg_tp = self.tp + self.tp2 + self.tp3
        if self.tp2 and self.tp3:
            return avg_tp / 3
        elif self.tp2:
            return avg_tp / 2

        return avg_tp

    @direction.setter
    def direction(self, direction: int):
        self.dir = direction

    @price.setter
    def price(self, price: float):
        self.p = price

    @stop_loss.setter
    def stop_loss(self, stop_loss: float):
        self.sl = stop_loss

    @take_profit.setter
    def take_profit(self, take_profit: float):
        self.tp = take_profit

    @second_take_profit.setter
    def second_take_profit(self, take_profit: float):
        self.tp2 = take_profit

    @third_take_profit.setter
    def third_take_profit(self, take_profit: float):
        self.tp3 = take_profit

    #
    # helpers
    #

    def basetime(self) -> float:
        """
        Related candle base time of the timestamp of the signal.
        """
        return Instrument.basetime(self.timeframe, self.ts)

    def as_exit(self) -> Union[StrategySignal, None]:
        """
        If the signal is an entry signal, negate it as an exit signal on the opposite direction else return None.
        Stop-loss and take-profit are swapped.
        """
        if self.signal == StrategySignal.SIGNAL_ENTRY:
            exit_signal = StrategySignal(self.timeframe, self.ts)
            exit_signal.signal = StrategySignal.SIGNAL_EXIT

            exit_signal.dir = -self.dir
            exit_signal.p = self.p
            exit_signal.sl = self.tp
            exit_signal.tp = self.sl

            return exit_signal

        return None

    def signal_type_str(self) -> str:
        if self.signal == StrategySignal.SIGNAL_ENTRY:
            return "entry"
        elif self.signal == StrategySignal.SIGNAL_EXIT:
            return "exit"

        return "none"

    def direction_str(self) -> str:
        if self.dir > 0:
            return "long"
        elif self.dir < 0:
            return "short"
        else:
            return ""

    def dup(self, _from: StrategySignal):
        self.timeframe = _from.timeframe
        self.ts = _from.ts
        self.signal = _from.signal

        self.dir = _from.dir
        self.p = _from.p
        self.sl = _from.sl
        self.tp = _from.tp
        self.tp2 = _from.tp2
        self.tp3 = _from.tp3

        self.label = _from.label
        self.context = _from.context

    def compare(self, _to: StrategySignal):
        """
        Return true of the the signal have the same type in the same direction, no more.
        """
        return self.signal == _to.signal and self.dir == _to.dir

    def __str__(self) -> str:
        my_date = datetime.fromtimestamp(self.ts)
        date_str = my_date.strftime('%Y-%m-%d %H:%M:%S')

        tp2 = " tp2=%s" % self.tp2
        tp3 = " tp3=%s" % self.tp3

        result = "ctx=%s tf=%s ts=%s signal=%s dir=%s p=%s sl=%s tp=%s" % (
            self.label, timeframe_to_str(self.timeframe), date_str, self.signal_type_str(),
            self.direction_str(), self.p, self.sl, self.tp)

        if self.tp2:
            result += tp2
        if self.tp3:
            result += tp3

        return result

    #
    # profit/loss
    #

    def profit(self) -> float:
        if self.dir > 0:
            return ((self.tp - self.p) / self.p) if self.p > 0.0 else 0.0
        elif self.dir < 0:
            return ((self.p - self.tp) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def second_profit(self) -> float:
        if self.dir > 0:
            return ((self.tp2 - self.p) / self.p) if self.p > 0.0 else 0.0
        elif self.dir < 0:
            return ((self.p - self.tp2) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def third_profit(self) -> float:
        if self.dir > 0:
            return ((self.tp3 - self.p) / self.p) if self.p > 0.0 else 0.0
        elif self.dir < 0:
            return ((self.p - self.tp3) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def avg_profit(self) -> float:
        avg_tp = self.avg_take_profit

        if self.dir > 0:
            return ((avg_tp - self.p) / self.p) if self.p > 0.0 else 0.0
        elif self.dir < 0:
            return ((self.p - avg_tp) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def loss(self) -> float:
        if self.dir > 0:
            return ((self.p - self.sl) / self.p) if self.p > 0.0 else 0.0
        elif self.dir < 0:
            return ((self.sl - self.p) / self.p) if self.p > 0.0 else 0.0

        return 0.0

    def risk_reward(self) -> float:
        profit = self.profit()
        loss = self.loss()

        return loss / profit if profit > 0.0 else 0.0

    def profit_dist(self) -> float:
        if self.dir > 0:
            return self.tp - self.p
        elif self.dir < 0:
            return self.p - self.tp

        return 0.0

    def avg_profit_dist(self) -> float:
        avg_tp = self.avg_take_profit

        if self.dir > 0:
            return avg_tp - self.p
        elif self.dir < 0:
            return self.p - avg_tp

        return 0.0

    def loss_dist(self) -> float:
        if self.dir > 0:
            return self.p - self.sl
        elif self.dir < 0:
            return self.sl - self.p

        return 0.0

    #
    # extra
    #

    def set(self, key: str, value):
        """
        Add a key:value pair in the extra member dict of the signal.
        It allow to add you internal trade data, states you want to keep during the live of the trade and
        even in persistence
        """
        self._extra[key] = value

    def unset(self, key: str):
        """Remove a previously set extra key"""
        if key in self._extra:
            del self._extra[key]

    def get(self, key: str, default=None):
        """Return a value for a previously defined key or default value if not exists"""
        return self._extra.get(key, default)

    #
    # helpers
    #

    def timeframe_to_str(self) -> str:
        return timeframe_to_str(self.timeframe)

    def direction_to_str(self) -> str:
        return direction_to_str(self.dir)

    def direction_from_str(self, direction: str) -> int:
        return direction_from_str(direction)

    #
    # dumps for notify/history
    #

    @staticmethod
    def dump_timestamp(timestamp: float, v1: bool = False) -> str:
        if v1:
            return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def dumps_notify(self, timestamp: float, strategy_trader: StrategyTrader) -> dict:
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
                'market-id': strategy_trader.instrument.market_id,
                'symbol': strategy_trader.instrument.symbol,
                'way': "entry",
                "order-type": order_type_to_str(self.order_type),
                'entry-timeout': timeframe_to_str(self.entry_timeout),
                'expiry': self.expiry,
                'timeframe': timeframe_to_str(self.timeframe),
                'is-user-trade': False,
                'label': self.label,
                'direction': self.direction_to_str(),
                'order-price': strategy_trader.instrument.format_price(self.p),
                'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
                'take-profit-price': strategy_trader.instrument.format_price(self.tp),
                'second-profit-price': strategy_trader.instrument.format_price(self.tp2),
                'third-profit-price': strategy_trader.instrument.format_price(self.tp3),
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
                'market-id': strategy_trader.instrument.market_id,
                'symbol': strategy_trader.instrument.symbol,
                'way': "exit",
                "order-type": order_type_to_str(self.order_type),
                'entry-timeout': timeframe_to_str(self.entry_timeout),
                'expiry': self.expiry,
                'timeframe': timeframe_to_str(self.timeframe),
                'is-user-trade': False,
                'label': self.label,
                'direction': self.direction_to_str(),
                'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
                'take-profit-price': strategy_trader.instrument.format_price(self.tp),
                'second-take-profit-price': strategy_trader.instrument.format_price(self.tp2),
                'third-take-profit-price': strategy_trader.instrument.format_price(self.tp3),
                'exit-open-time': self.dump_timestamp(self.ts),
            }
