# @date 2019-06-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade region.

from datetime import datetime
from common.utils import timeframe_to_str, timeframe_from_str


class Region(object):
    """
    Startegy trade region base class.

    @todo Could use market price formatter here in dumps and parameters methods
    """

    VERSION = "1.0.0"

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

    def __init__(self, created, stage, direction, timeframe):
        self._id = -1                # operation unique identifier
        self._created = created      # creation timestamp (always defined)
        self._stage = stage          # apply on entry, exit or both signal stage
        self._dir = direction        # apply on long, short or both signal direction
        self._expiry = 0             # expiration timestamp (<=0 never)
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

    @classmethod
    def version(cls):
        return cls.VERSION

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
        """
        Timeframe to check for.
        """
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

    def test_region(self, timestamp, signal):
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

        if self._expiry > 0 and timestamp >= self._expiry:
            # region expired
            return False

        if self._timeframe > 0 and signal.timeframe != self._timeframe:
            # timeframe missmatch
            return False

        return self.test(timestamp, signal)

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

    def test(self, timestamp, signal):
        """
        Perform the test of the region on the signal data.
        """
        return False

    def can_delete(self, timestamp, bid, ask):
        """
        By default perform a test on expiration time, but more deletion cases can be added,
        like a cancelation price trigger.

        @param timestamp float Current timestamp
        @param bid float last bid price
        @param ask float last ask price
        """
        return self._expiry > 0 and timestamp >= self._expiry

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
            'id': self._id,
            'created': self.created_to_str(),
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
            'version': self.version(),  # str version (M.m.s)
            'region': self.region(),    # integer type
            'name': self.name(),        # str type
            'id': self._id,             # previous integer unique id
            'created': self._created,   # created timestamp datetime.utcfromtimestamp(self._created).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'stage': self._stage,  #  "entry" if self._stage == Region.STAGE_ENTRY else "exit" if self._stage == Region.STAGE_EXIT else "both",
            'direction': self._dir,  # "long" if self._dir == Region.LONG else "short" if self._dir == Region.SHORT else "both",
            'timeframe': self._timeframe,  # timeframe_to_str(self._timeframe),
            'expiry': self._expiry,  # datetime.utcfromtimestamp(self._expiry).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

    def loads(self, data):
        """
        Override this method and add specific parameters for loads parameters from persistance model.
        """
        self._id = data.get('id', -1)
        self._created = data.get('created', 0)  # datetime.strptime(data.get('created', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC()).timestamp()
        self._stage = data.get('stage', 0)  # self.stage_from_str(data.get('stage', ''))
        self._dir = data.get('direction', 0)  # self.direction_from_str(data.get('direction', ''))
        self._timeframe = data.get('timeframe')  # timeframe_from_str(data.get('timeframe', 't'))
        self._expiry = data.get('expiry', 0)  # datetime.strptime(data.get('expiry', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC()).timestamp()

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

    def created_to_str(self):
        """In local time"""
        return datetime.fromtimestamp(self._created).strftime('%Y-%m-%d %H:%M:%S')

    def expiry_to_str(self):
        """In local time"""
        if self._expiry > 0:
            return datetime.fromtimestamp(self._expiry).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return "never"
