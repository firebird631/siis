# @date 2019-02-20
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# History indicator.

from strategy.indicator.indicator import Indicator

import logging
logger = logging.getLogger('siis.strategy')


class HistoryIndicator(Indicator):
    """
    History indicator allow to store max N last value of any other indicator,
    The others indicator only store theirs previous and latest value, and some other cache
    and computations data.
    They does not store more to avoid the cost of the array managing, very costly in Python (slow slicing).

    An example of usage, could be using this indicator on an RSi or a SMA, and use the SlopeIndicator over this
    values.
    """

    __slots__ = '_length', '_values'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, length=9):
        super().__init__("history", timeframe)

        self._length = length   # number of stored values
        self._values = np.array([0.0]*length)

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def previous(self):
        return self._values[-2]

    @property
    def last(self):
        return self._values[-1]

    @property
    def values(self):
        return self._values

    def compute(self, timestamp, values):
        # no more delta than capacity
        delta = min(self._length, int((timestamp - self._last_timestamp) / self._timeframe))

        # temporal coherency, fill left withmissing samples, assume the first value
        if delta > len(values):
            v = np.append([values[0]]*(delta-len(values)), values)
        else:
            v = values

        if delta == self._length:
            # simply copy
            self._values = np.array(v)
        elif delta > 0:
            # shift left by delta and append the new values or just replace the current
            self._values = np.append(self._values[-self._length+delta:], values[-delta:])
        elif delta == 0:
            # only replace the current
            self._values[-1] = values[-1]

        self._last_timestamp = timestamp

        return self._values
