# @date 2019-06-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade range region.

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

    def __init__(self, created, stage, direction, timeframe):
        super().__init__(created, stage, direction, timeframe)

        self._low = 0.0
        self._high = 0.0

        self._cancellation = 0.0

    def init(self, parameters):
        self._low = parameters.get('low', 0.0)
        self._high = parameters.get('high', 0.0)

        self._cancellation = parameters.get('cancellation', 0.0)

    def check(self):
        return self._low > 0 and self._high > 0 and self._high >= self._low

    def test(self, timestamp, signal):
        # signal price is in low / high range
        return self._low <= signal.price <= self._high

    def can_delete(self, timestamp, bid, ask):
        if self._expiry > 0 and timestamp >= self._expiry:
            return True

        # trigger price reached in accordance with the direction
        if self._dir == Region.LONG and ask < self._cancellation:
            return True

        if self._dir == Region.SHORT and bid > self._cancellation:
            return True

        return False

    def str_info(self):
        return "Range region from %s to %s, stage %s, direction %s, timeframe %s, expiry %s, cancellation %s" % (
                self._low, self._high, self.stage_to_str(), self.direction_to_str(),
                self.timeframe_to_str(), self.expiry_to_str(), self._cancellation)

    def parameters(self):
        params = super().parameters()

        params['label'] = "Range region"
        
        params['low'] = self._low,
        params['high'] = self._high
        
        params['cancellation'] = self._cancellation

        return params

    def dumps(self):
        data = super().dumps()
        
        data['low'] = self._low
        data['high'] = self._high
        
        data['cancellation'] = self._cancellation

        return data

    def loads(self, data):
        super().loads(data)

        self._low = data.get('low', 0.0)
        self._high = data.get('high', 0.0)
        
        self._cancellation = data.get('cancellation', 0.0)
