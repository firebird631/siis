# @date 2019-06-21
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade region.

from datetime import datetime
from common.utils import timeframe_to_str, timeframe_from_str


class Region(object):
    """
    Startegy trade region base class.

    @todo Could use market price formatter here in dumps and parameters methods
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
    REGION = REGION_UNDEFINED

    def __init__(self, stage, direction, timeframe):
        self._id = -1          # operation unique identifier
        self._stage = stage    # apply on entry, exit or both signal stage
        self._dir = direction  # apply on long, short or both signal direction
        self._expiry = 0       # expiration timestamp (<=0 never)
        self._timeframe = timeframe  # specific timeframe or 0 for any

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

    @property
    def timeframe(self):
        return self._timeframe

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

        if self._stage == Region.STAGE_EXIT and signal.signal > 0:
            # cannot validate an exit region on the entry signal
            return False

        if self._stage == Region.STAGE_ENTRY and signal.signal < 0:
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
            'id': self.id,
            'stage': self.stage_to_str(),
            'direction': self.direction_to_str(),
            'timeframe': self.timeframe_to_str(),
            'expiry': self.expiry_to_str()
        }

    def dumps(self):
        """
        Override this method and add specific parameters for dumps parameters for persistance model.
        """
        return {
            'id': self.id,
            'type': self.name(),
            'stage': self._stage,  #  "entry" if self._stage == Region.STAGE_ENTRY else "exit" if self._stage == Region.STAGE_EXIT else "both",
            'direction': self._dir,  # "long" if self._dir == Region.LONG else "short" if self._dir == Region.SHORT else "both",
            'timeframe': self._timeframe,  # timeframe_to_str(self._timeframe),
            'expiry': self._expiry,  # datetime.fromtimestamp(self._expiry).strftime('%Y-%m-%dT%H:%M:%S'),
        }

    def loads(self, data):
        """
        Override this method and add specific parameters for loads parameters from persistance model.
        """
        self._id = data.get('id', -1)
        self._stage = data.get('stage', 0)  # self.stage_from_str(data.get('stage', ''))
        self._dir = data.get('direction', 0)  # self.direction_from_str(data.get('direction', ''))
        self._timeframe = data.get('timeframe')  # timeframe_from_str(data.get('timeframe', 't'))
        self._expiry = data.get('expiry', 0)  # datetime.strptime(data.get('expiry', '1970-01-01T00:00:00'), '%Y-%m-%dT%H:%M:%S').timestamp()

    def stage_to_str(self):
        if self._stage == Region.STAGE_ENTRY:
            return "entry"
        elif self._stage == Region.STAGE_EXIT:
            return "exit"
        elif self._stage == Region.STAGE_BOTH:
            return "both"
        else:
            return "both"

    def stage_from_str(self, stage_str):
        if stage_str == "entry":
            return Region.STAGE_ENTRY
        elif stage_str == "exit":
            return Region.STAGE_EXIT
        elif stage_str == "both":
            return Region.STAGE_BOTH
        else:
            return Region.STAGE_BOTH

    def direction_to_str(self):
        if self._dir == Region.LONG:
            return "long"
        elif self._dir == Region.SHORT:
            return "short"
        elif self._dir == Region.BOTH:
            return "both"
        else:
            return "both"

    def direction_from_str(self, direction_str):
        if stage_str == "long":
            return Region.LONG
        elif stage_str == "short":
            return Region.SHORT
        elif stage_str == "both":
            return Region.BOTH
        else:
            return Region.BOTH

    def timeframe_to_str(self):
        if self._timeframe > 0:
            return timeframe_to_str(self._timeframe)
        else:
            return "any"

    def expiry_to_str(self):
        if self._expiry > 0:
            return datetime.fromtimestamp(self._expiry).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return "never"


class RangeRegion(Region):
    """
    Rectangle region with two horizontal price limit (low/high).
    """

    NAME = "range"
    REGION = Region.REGION_RANGE

    def __init__(self, stage, direction, timeframe):
        super().__init__(stage, direction, timeframe)

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
        return "Range region from %s to %s, stage %s, direction %s, timeframe %s, expiry %s" % (
                self._low, self._high, self.stage_to_str(), self.direction_to_str(), self.timeframe_to_str(), self.expiry_to_str())

    def parameters(self):
        return {
            'label': "Range region",
            'name': self.name(),
            'id': self.id,
            'stage': self.stage_to_str(),
            'direction': self.direction_to_str(),
            'timeframe': self.timeframe_to_str(),
            'expiry': self.expiry_to_str(),
            'low': self._low,
            'high': self._high
        }

    def dumps(self):
        data = super().dumps()
        
        data['low'] = self._low
        data['high'] = self._high

        return data

    def loads(self, data):
        super().loads(data)

        self._low = data.get('low', 0.0)
        self._high = data.get('high', 0.0)


class TrendRegion(Region):
    """
    Trend channel region with two trends price limit (low/high).

    With ylow = ax + b and yhigh = a2x + b2 to produce non parallels channels.
    """

    NAME = "channel"
    REGION = Region.REGION_TREND

    def __init__(self, stage, direction, timeframe):
        super().__init__(stage, direction, timeframe)

    def init(self, parameters):
        self._low_a = parameters.get('low-a', 0.0)
        self._high_a = parameters.get('high-a', 0.0)
        self._low_b = parameters.get('low-b', 0.0)
        self._high_b = parameters.get('high-b', 0.0)

    def check(self):
        if self._low_a <= 0.0 or self._high_a <= 0.0 or self._low_b <= 0.0 or self._high_b <= 0.0:
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
        return "Range region from %s/%s to %s/%s, stage %s, direction %s, timeframe %s, expiry %s" % (
                self._low_a, self._high_a, self._low_b, self._high_b,
                self.stage_to_str(), self.direction_to_str(), self.timeframe_to_str(), self.expiry_to_str())

    def parameters(self):
        return {
            'label': "Range region",
            'name': self.name(),
            'id': self.id,
            'stage': self.stage_to_str(),
            'direction': self.direction_to_str(),
            'timeframe': self.timeframe_to_str(),
            'expiry': self.expiry_to_str(),
            'low-a': self._low_a,
            'low-b': self._low_b,
            'high-a': self._high_a,
            'high-b': self._high_b
        }

    def dumps(self):
        data = super().dumps()
        
        data['low-a'] = self._low_a
        data['high-a'] = self._high_a

        data['low-b'] = self._low_b
        data['high-b'] = self._high_b

        return data

    def loads(self, data):
        super().loads(data)

        self._low_a = data.get('low-a', 0.0)
        self._high_a = data.get('high-a', 0.0)

        self._low_b = data.get('low-b', 0.0)
        self._high_b = data.get('high-b', 0.0)
