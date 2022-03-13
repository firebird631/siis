# @date 2019-06-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade range region.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from instrument.instrument import Instrument

from .region import Region


class RangeRegion(Region):
    """
    Rectangle region with two horizontal price limit (low/high).

    low Absolute low price
    high Absolute high price (high > low)
    trigger Absolute price if reached the region is deleted

    Trigger depends of the direction :
        - in long if the price goes below trigger then delete the region
        - in short if the price goes above trigger then delete the region
        - if no trigger is defined there is no such deletion
    """

    NAME = "range"
    REGION = Region.REGION_RANGE

    def __init__(self, created: float, stage: int, direction: int, timeframe: float):
        super().__init__(created, stage, direction, timeframe)

        self._low = 0.0
        self._high = 0.0

        self._cancellation = 0.0

    def init(self, parameters: dict):
        self._low = parameters.get('low', 0.0)
        self._high = parameters.get('high', 0.0)

        self._cancellation = parameters.get('cancellation', 0.0)

    def check(self) -> bool:
        return self._low > 0 and self._high > 0 and self._high >= self._low

    def test(self, timestamp: float, signal_price: float) -> bool:
        # signal price is in low / high range
        return self._low <= signal_price <= self._high

    def can_delete(self, timestamp: float, bid: float, ask: float) -> bool:
        if 0 < self._expiry <= timestamp:
            return True

        # trigger price reached in accordance with the direction
        if self._dir == Region.LONG and ask < self._cancellation:
            return True

        if self._dir == Region.SHORT and bid > self._cancellation:
            return True

        return False

    def str_info(self, instrument: Instrument) -> str:
        return "Range region from %s to %s, stage %s, direction %s, timeframe %s, expiry %s, cancellation %s" % (
                instrument.format_price(self._low), instrument.format_price(self._high),
                self.stage_to_str(), self.direction_to_str(),
                self.timeframe_to_str(), self.expiry_to_str(), instrument.format_price(self._cancellation))

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
        return "[%s - %s]" % (instrument.format_price(self._low), instrument.format_price(self._high))

    def parameters(self) -> dict:
        params = super().parameters()

        params['label'] = "Range region"

        params['low'] = self._low,
        params['high'] = self._high
        
        params['cancellation'] = self._cancellation

        return params

    def dumps(self) -> dict:
        data = super().dumps()
        
        data['low'] = self._low
        data['high'] = self._high
        
        data['cancellation'] = self._cancellation

        return data

    def loads(self, data: dict):
        super().loads(data)

        self._low = data.get('low', 0.0)
        self._high = data.get('high', 0.0)
        
        self._cancellation = data.get('cancellation', 0.0)
