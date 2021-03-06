# @date 2019-06-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade trend region.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from instrument.instrument import Instrument

from .region import Region


class TrendRegion(Region):
    """
    Trend channel region with two trends price limit (low/high).

    With ylow = ax + b and yhigh = a2x + b2 to produce non parallels channels.
    """

    NAME = "channel"
    REGION = Region.REGION_TREND

    def __init__(self, created, stage, direction, timeframe):
        super().__init__(created, stage, direction, timeframe)

        self.dl = 0.0  # delta low trend
        self.dh = 0.0  # delta high trend

        self._low_a = 0.0
        self._high_a = 0.0
        self._low_b = 0.0
        self._high_b = 0.0
        self._cancellation = 0.0

        self._dl = 0.0
        self._dh = 0.0

    def init(self, parameters):
        self._low_a = parameters.get('low-a', 0.0)
        self._high_a = parameters.get('high-a', 0.0)
        self._low_b = parameters.get('low-b', 0.0)
        self._high_b = parameters.get('high-b', 0.0)
        self._cancellation = parameters.get('cancellation', 0.0)

        self._dl = (self._low_b - self._low_a) / (self._expiry - self._created)
        self._dh = (self._high_b - self._high_a) / (self._expiry - self._created)

    def check(self):
        if self._low_a <= 0.0 or self._high_a <= 0.0 or self._low_b <= 0.0 or self._high_b <= 0.0:
            # points must be greater than 0
            return False

        if (self._low_a > self._high_a) or (self._low_b > self._high_b):
            # highs must be greater than lows
            return False

        if self._expiry <= self._created:
            # expiry must be defined and higher than its creation timestamp
            return False

        return True

    def test(self, timestamp, signal_price):
        # y = ax + b
        dt = timestamp - self._created

        low = dt * self._dl + self._low_a
        high = dt * self._dh + self._high_a

        return low <= signal_price <= high

    def can_delete(self, timestamp, bid, ask):
        if self._expiry > 0 and timestamp >= self._expiry:
            return True

        # trigger price reached in accordance with the direction
        if self._dir == Region.LONG and ask < self._cancellation:
            return True

        if self._dir == Region.SHORT and bid > self._cancellation:
            return True

        return False

    def str_info(self, instrument: Instrument) -> str:
        return "Trend region from [%s - %s] to [%s - %s], stage %s, direction %s, timeframe %s, expiry %s" % (
                instrument.format_price(self._low_a), instrument.format_price(self._high_a),
                instrument.format_price(self._low_b), instrument.format_price(self._high_b),
                self.stage_to_str(), self.direction_to_str(), self.timeframe_to_str(), self.expiry_to_str())

    def cancellation_str(self, instrument: Instrument) -> str:
        """
        Dump a string with short region cancellation str.
        """
        if self._dir == Region.LONG and self._cancellation > 0.0:
            return"if ask price < %s" % instrument.format_price(self._cancellation)
        elif self._dir == Region.SHORT and self._cancellation > 0.0:
            return "if bid price > %s" % instrument.format_price(self._cancellation)
        else:
            return "never"

    def condition_str(self, instrument: Instrument) -> str:
        return "[%s - %s] - [%s - %s]" % (instrument.format_price(self._low_a), instrument.format_price(self._high_a),
                                          instrument.format_price(self._low_b), instrument.format_price(self._high_b))

    def parameters(self) -> dict:
        params = super().parameters()

        params['label'] = "Trend region"

        params['low-a'] = self._low_a,
        params['high-a'] = self._high_a

        params['low-b'] = self._low_b,
        params['high-b'] = self._high_b

        params['cancellation'] = self._cancellation

        return params

    def dumps(self) -> dict:
        data = super().dumps()

        data['low-a'] = self._low_a
        data['high-a'] = self._high_a

        data['low-b'] = self._low_b
        data['high-b'] = self._high_b

        data['cancellation'] = self._cancellation

        return data

    def loads(self, data: dict):
        super().loads(data)

        self._low_a = data.get('low-a', 0.0)
        self._high_a = data.get('high-a', 0.0)

        self._low_b = data.get('low-b', 0.0)
        self._high_b = data.get('high-b', 0.0)

        self._cancellation = data.get('cancellation', 0.0)
