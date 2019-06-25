# @date 2019-06-21
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade region.

from datetime import datetime


class Region(object):
    """
    Startegy trade region base class.
    """

    REGION_UNDEFINED = 0
    REGION_RANGE = 1
    REGION_TREND = 2

    STAGE_ENTRY = 1
    STAGE_EXIT = -1
    STAGE_BOTH = 0

    LONG = 1
    SHORT = -1
    BOTH = 0

    NAME = "undefined"
    REGION = Region.REGION_UNDEFINED

    def __init__(self, type):
        self._id = -1        # operation unique identifier
        self._stage = stage  # apply on entry, exit or both signal stage
        self._dir = 0        # apply on long, short or both signal direction
        self._expiry = 0     # expiration timestamp (<=0 never)

    #
    # getters
    #

    @classmethod
    def name(cls):
        """
        String type name of the region.
        """
        return cls.NAME

    @classmethod
    def region(cls):
        """
        Integer type of region.
        """
        return cls.REGION

    @property
    def id(self):
        """
        Unique region identifier.
        """
        return self._id

    @property
    def stage(self):
        """
        Zone for entry, exit or both
        """
        return self._stage

    @property
    def direction(self):
        """
        Direction of the allowed signals, long, short of both.
        """
        return self._dir

    @property
    def dir(self):
        """
        Direction of the allowed signals, long, short of both.
        """
        return self._dir

    @property
    def expiry(self):
        """
        Expiry timestamp in second.
        """
        return self._expiry

    #
    # setters
    #

    def set_id(self, _id):
        self._id = _id

    def set_expiry(self, expiry):
        self._expiry = expiry

    #
    # processing
    #

    def can_delete(self, timestamp):
        return self._expiry and self._expiry <= timestamp

    def test_region(self, signal):
        """
        Each time the market price change perform to this test. If the test pass then
        it is executed and removed from the list or kept if its a persistent operation.

        @return True if the signal pass the test.
        """

        if self._stage == TradeOp.STAGE_EXIT and signal.signal > 0:
            # cannot validate an exit region on the entry signal
            return False

        if self._stage == TradeOp.STAGE_ENTRY and signal.signal < 0:
            # cannot validate an entry region on the exit signal
            return False

        return self.test(signal)

    #
    # overrides
    #

    def init(self, parameters):
        """
        Override this method to setup region parameters from the parameters dict.
        """
        pass

    def check(self):
        """
        Perform an integrity check on the data defined to the region.
        @return True if the check pass.
        """
        return True

    def test(self, signal):
        """
        Perform the test of the region on the signal data.
        """
        return False

    def str_info(self):
        """
        Override this method to implement the single line message info of the region.
        """
        return ""

    def parameters(self):
        """
        Override this method and add specific parameters to be displayed into an UI or a table.
        """
        return {
            'label': "undefined",
            'name': self.name(),
            'id': self.id(),
            'expiry': self._expiry
        }


class RangeRegion(Region):
    """
    Rectangle region with two horizontal price limit (low/high).
    """

    NAME = "range"
    REGION = Region.REGION_RANGE

    def __init__(self, stage):
        super().__init__(stage)

        self._low = 0.0
        self._high = 0.0

    def init(self, parameters):
        self._low = parameters.get('low', 0.0)
        self._high = parameters.get('high', 0.0)

    def check(self):
        return self._low > 0 and self._high > 0 and self._high >= self._low

    def test(self, signal):
        return self._low <= signal.p <= self._high

    def str_info(self):
        expiry = " until %s" % (datetime.fromtimestamp(self._expiry).strftime('%Y-%m-%d %H:%M:%S'),)
        return "Range region from %s to %s%s" % (self._low, self._high, expiry if self._expiry else "")

    def parameters(self):
        return {
            'label': "Range region",
            'name': self.name(),
            'id': self.id(),
            'expiry': self._expiry,
            'low': self._low,
            'high': self._high
        }


class TrendRegion(Region):
    """
    Trend channel region with two trends price limit (low/high).

    With ylow = ax + b and yhigh = a2x + b2 to produce non parallels channels.
    """

    NAME = "channel"
    REGION = Region.REGION_TREND

    def __init__(self, stage):
        super().__init__(stage)

    def init(self, parameters):
        self._low_a = parameters.get('low-a', 0.0)
        self._high_a = parameters.get('high-a', 0.0)
        self._low_b = parameters.get('low-b', 0.0)
        self._high_b = parameters.get('high-b', 0.0)

    def check(self):
        if self._low_a <= 0.0 or self._high_a <= 0.0 or self._low_b <= 0.0 or self._high_b <= 0.0
            # points must be greater than 0
            return False

        if (self._low_b > self._low_a and self._high_b < self._high_a) or (self._low_b < self._low_a and self._high_b > self._high_a):
            # different sign of the slope
            return False

        return True

    def test(self, signal):
        # higher than low
        # y = ax + b
        # @todo

        # lesser than high
        # @todo

        return False

    def str_info(self):
        expiry = " until %s" % (datetime.fromtimestamp(self._expiry).strftime('%Y-%m-%d %H:%M:%S'),)
        return "Trend region from low-a=%s low-b=%s to high-a=%s high-b=%s%s" % (
            self._low_a, self._low_b, self._high_a, self._high_b, expiry if self._expiry else "")

    def parameters(self):
        return {
            'label': "Range region",
            'name': self.name(),
            'id': self.id(),
            'expiry': self._expiry,
            'low-a': self._low_a,
            'low-b': self._low_b,
            'high-a': self._high_a,
            'high-b': self._high_b
        }
