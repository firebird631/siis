# @date 2020-02-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Strategy alert base model

from datetime import datetime
from common.signal import Signal

from trader.order import Order, order_type_to_str
from common.utils import timeframe_to_str, direction_to_str

from instrument.instrument import Instrument

import logging
logger = logging.getLogger('siis.strategy.alert')


class Alert(object):
    """
    Strategy alert.
    The alert is any event possible from a strategy, and user configurable.
    The direction of the alert is optional.
    """

    __slots__ = '_timeframe', '_id', '_created', '_dir', '_expiry', '_countdown', '_message'

    VERSION = "1.0.0"

    ALERT_UNDEFINED = 0
    ALERT_PRICE_CROSS = 1
    ALERT_PRICE_CROSS_UP = 2
    ALERT_PRICE_CROSS_DOWN = 3
    ALERT_PRICE_PCT_CHANGE = 4
    ALERT_PRICE_PCT_CHANGE_UP = 5
    ALERT_PRICE_PCT_CHANGE_DOWN = 6

    PRICE_SRC_BID = 0
    PRICE_SRC_ASK = 1
    PRICE_SRC_MID = 2

    NAME = "undefined"
    REGION = ALERT_UNDEFINED

    def __init__(self, created, timeframe):
        self._id = -1                # alert unique identifier
        self._created = created      # creation timestamp (always defined)
        self._expiry = 0             # expiration timestamp (<=0 never)
        self._countdown = -1         # max trigger occurences, -1 mean forever (until expiry)
        self._timeframe = timeframe  # specific timeframe or 0 for any
        self._message = ""           # optional user short message

    @classmethod
    def name(cls):
        """
        String type name of the alert.
        """
        return cls.NAME

    @classmethod
    def alert(cls):
        """
        Integer type of alert.
        """
        return cls.ALERT

    @classmethod
    def version(cls):
        return cls.VERSION

    @property
    def id(self):
        """
        Unique alert identifier.
        """
        return self._id

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

    @property
    def countdown(self):
        """
        Expiry countdown integer. -1 for infinite. 0 means terminated.
        """
        return self._countdown

    @property
    def message(self):
        return self._message

    #
    # setters
    #

    def set_id(self, _id):
        self._id = _id

    def set_expiry(self, expiry):
        self._expiry = expiry

    def set_countdown(self, countdown):
        self._countdown = countdown
  
    @message.setter
    def message(self, message):
        self.message = message

    #
    # processing
    #

    def test_alert(self, timestamp, bid, ask, timeframes):
        """
        Each time the market price change perform to this test. If the test pass then
        it is executed and removed from the list or kept if its a persistent alert (until its expiry).

        @return True if the signal pass the test.
        """
        if self._expiry > 0 and timestamp >= self._expiry:
            # alerte expired
            return None

        if self._timeframe > 0 and self._timeframe not in timeframes:
            # missing timeframe
            return None

        if self._countdown == 0:
            # countdown reached 0 previously
            return None

        result = self.test(timestamp, bid, ask, timeframes)

        if result and self._countdown > 0:
            # dec countdown
            self._countdown -= 1

        return result

    #
    # overrides
    #

    def init(self, parameters):
        """
        Override this method to setup alert parameters from the parameters dict.
        """
        pass

    def check(self):
        """
        Perform an integrity check on the data defined to the alert.
        @return True if the check pass.
        """
        return True

    def test(self, timestamp, bid, ask, timeframes):
        """
        Perform the test of the alert on the last price and timeframes data.

        @return A valid dict with trigger condition if trigger, else None
        """
        return None

    def can_delete(self, timestamp, bid, ask):
        """
        By default perform a test on expiration time, but more deletion cases can be added,
        like a cancellation price trigger.

        @param timestamp float Current timestamp
        @param bid float last bid price
        @param ask float last ask price
        """
        return (self._expiry > 0 and timestamp >= self._expiry) or self._countdown == 0

    def str_info(self):
        """
        Override this method to implement the single line message info of the alert.
        """
        return ""

    #
    # helpers
    #

    def basetime(self, timestamp):
        """
        Related candle base time of the timestamp of the signal.
        """
        return Instrument.basetime(self._timeframe, timestamp)

    #
    # helpers
    #

    def timeframe_to_str(self):
        return timeframe_to_str(self._timeframe)

    def created_to_str(self):
        return datetime.fromtimestamp(self._created).strftime('%Y-%m-%d %H:%M:%S')

    def expiry_to_str(self):
        if self._expiry > 0:
            return datetime.fromtimestamp(self._expiry).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return "never"

    def countdown_to_str(self):
        if self._countdown >= 0:
            return str(self._countdown)
        else:
            return "inf"

    def condition_str(self):
        """
        Dump a string with alert condition details.
        """
        return ""

    def cancellation_str(self):
        """
        Dump a string with alert cancellation details.
        """
        return ""

    #
    # dumps for notify/history
    #

    def dump_timestamp(self, timestamp, v1=False):
        if v1:
            return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def dumps_notify(self, timestamp, alert_result, strategy_trader):
        """
        Dumps to dict for notify/history.
        """
        return {
            'version': self.version(),
            'alert': self.alert(),
            'name': self.name(),
            'id': self._id,
            'app-name': strategy_trader.strategy.name,
            'app-id': strategy_trader.strategy.identifier,
            'timestamp': timestamp,
            'symbol': strategy_trader.instrument.market_id,
            'timeframe': timeframe_to_str(self._timeframe),
            'message': self._message,
            'trigger': 0,  # 1 for up, -1 for down
            'last-price': strategy_trader.instrument.format_price((strategy_trader.instrument.market_price)),
            'reason': "",  # alert specific detail of the trigger
        }

    #
    # persistance
    #

    def parameters(self):
        """
        Override this method and add specific parameters to be displayed into an UI or a table.
        """
        return {
            'name': self.name(),
            'id': self._id,
            'created': self.created_to_str(),
            'timeframe': self.timeframe_to_str(),
            'expiry': self.expiry_to_str(),
            'countdown': self.countdown_to_str(),
            'message': self._message
        }

    def dumps(self):
        """
        Override this method and add specific parameters for dumps parameters for persistance model.
        """
        return {
            'version': self.version(),  # str version (M.m.s)
            'alert': self.alert(),      # integer type
            'name': self.name(),        # str type
            'id': self._id,             # previous integer unique id
            'created': self._created,   # created timestamp datetime.utcfromtimestamp(self._created).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'timeframe': self._timeframe,  # timeframe_to_str(self._timeframe),
            'expiry': self._expiry,  # datetime.utcfromtimestamp(self._expiry).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'countdown': self._countdown,  # integer countdown
            'message': self._message       # str user message
        }

    def loads(self, data):
        """
        Override this method and add specific parameters for loads parameters from persistance model.
        """
        self._id = data.get('id', -1)
        self._created = data.get('created', 0)  # datetime.strptime(data.get('created', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC()).timestamp()
        self._timeframe = data.get('timeframe')  # timeframe_from_str(data.get('timeframe', 't'))
        self._expiry = data.get('expiry', 0)  # datetime.strptime(data.get('expiry', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC())..timestamp()
        self._countdown = data.get('countdown', -1)
        self._message = data.get('message', "")
