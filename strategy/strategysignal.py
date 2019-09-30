# @date 2019-01-13
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy signal

from datetime import datetime
from notifier.signal import Signal

from trader.order import Order
from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')


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
    - ptp for partial TP from 0 to 1

    @todo remove ptp, let in in extra
    """

    __slots__ = 'timeframe', 'ts', 'signal', 'dir', 'p', 'sl', 'tp', 'alt_tp', 'ptp', '_extra', '_comment'

    SIGNAL_NONE = 0   # signal type undefined (must be entry or exit else its informal)
    SIGNAL_ENTRY = 1  # entry signal (this does not mean long. @see dir)
    SIGNAL_EXIT = -1  # exit signal (this does not mean short. @see dir)

    def __init__(self, timeframe, timestamp):
        self.timeframe = timeframe   # timeframe related to the signal
        self.ts = timestamp          # timestamps of the signal emit
        self.signal = StrategySignal.SIGNAL_NONE  # type of the signal : entry or exit

        self.dir = 0       # signal diretion

        self.p = 0.0       # signal price / possible entry-price
        self.sl = 0.0      # possible stop-loss pricce
        self.tp = 0.0      # primary possible take profit price
        self.alt_tp = 0.0  # secondary possible take profit price
        self.expiry = 0.0  # trade expiration if in profit after this delay

        self._comment = ""  # optional comment
        self._extra = {}

        self.ptp = 1.0  # partial TP ratio ]0.0..N]

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

    @property
    def alt_take_profit(self):
        return self.alt_tp

    @property
    def partial_tp(self):
        return self.ptp

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, comment):
        self._comment = comment

    #
    # helpers
    #

    def base_time(self) -> float:
        """
        Related candle base time of the timestamp of the signal.
        """
        return int(self.ts / self.timeframe) * self.timeframe

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

    def dup(self, _from):
        self.timeframe = _from.timeframe
        self.ts = _from.ts
        self.signal = _from.signal

        self.dir = _from.dir
        self.p = _from.p
        self.sl = _from.sl
        self.tp = _from.tp
        self.alt_tp = _from.alt_tp

    def compare(self, _to) -> bool:
        """
        Return true of the the signal have the same type in the same direction, no more.
        """
        return self.signal == _to.signal and self.dir == _to.dir

    def __str__(self):
        mydate = datetime.fromtimestamp(self.ts)
        date_str = mydate.strftime('%Y-%m-%d %H:%M:%S')

        return "tf=%s ts=%s signal=%s dir=%s p=%s sl=%s tp=%s %s" % (
                timeframe_to_str(self.timeframe), date_str, self.signal_type_str(), self.direction_str(),
                self.p, self.sl, self.tp, self.comment)

    #
    # extra
    #

    def set(self, key, value):
        """
        Add a key:value paire in the extra member dict of the signal.
        It allow to add you internal signal data, states you want to communicate to the orderer.
        """
        self._extra[key] = value

    def unset(self, key):
        """Remove a previously set extra key"""
        if key in self._extra:
            del self._extra[key]

    def get(self, key, default=None):
        """Return a value for a previously defined key or default value if not exists"""
        return self._extra.get(key, default)
