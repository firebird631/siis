# @date 2019-01-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# streamable model

class Streamable(object):
    """
    Interface for an object having some variable to be monitored/streamed.

    't': target
    'c': command/category
    'g': group name (strategy name, trader name...)
    'd': data
    'T': timestamp
    'n': name
    'i': index for time-series
    't': data type
    'b': data timestamp for time-series
    'o': data look n feel (glyph...)
    """

    # command/category
    STREAM_UNDEFINED = 0
    STREAM_GENERAL = 1
    STREAM_TRADER = 2
    STREAM_STRATEGY = 3
    STREAM_STRATEGY_CHART = 4
    STREAM_STRATEGY_INFO = 5
    STREAM_STRATEGY_TRADE = 6
    STREAM_STRATEGY_ALERT = 7
    STREAM_STRATEGY_SIGNAL = 8
    STREAM_WATCHER = 9
    STREAM_STRATEGY_REGION = 10

    def __init__(self, monitor_service, stream_category, stream_group, stream_name):
        self._monitor_service = monitor_service
        self._activity = False

        self._stream_name = stream_name
        self._stream_category = stream_category
        self._stream_group = stream_group

        self._members = {}
        self._count = 0   # reference counter

        self._last_timestamp = 0.0

    def enable(self):
        self._activity = True

    def disable(self):
        self._activity = False

    @property
    def name(self) -> str:
        return self._stream_name

    @property
    def activity(self) -> bool:
        return self._activity

    def add_member(self, member):
        self._members[member.name] = member

    def remove_member(self, member_name: str):
        if member_name in self._members:
            del self._members[member_name]

    def member(self, member_name: str):
        return self._members.get(member_name)

    def publish(self):
        if self._monitor_service:
            for k, member in self._members.items():
                if member.has_update():
                    # publish and cleanup
                    self._monitor_service.publish(self._stream_category, self._stream_group,
                                                  self._stream_name, member.content())
                    member.clean()

    def use(self):
        self._count += 1

    def unuse(self):
        if self._count > 0:
            self._count -= 1

    def is_free(self) -> bool:
        return self._count == 0


class StreamMember(object):
    """
    Base class for a streamed member.
    """

    TYPE_UNDEFINED = None

    def __init__(self, name, member_type):
        self._name = name
        self._type = member_type
        self._updated = False

    @property
    def name(self):
        return self._name

    # def update(self, value):
    #     pass

    def has_update(self):
        return self._updated

    def clean(self):
        self._updated = False

    def content(self):
        """
        Dict formatted content.
        """
        return {'n': self._name, 't': None, 'v': None}


class StreamMemberBool(StreamMember):
    """
    Specialization for a boolean value.
    """

    TYPE_BOOL = "b"

    def __init__(self, name):
        super().__init__(name, StreamMemberBool.TYPE_BOOL)

        self._value = False

    def update(self, value):
        self._value = value
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self.TYPE_BOOL, 'v': self._value}


class StreamMemberInt(StreamMember):
    """
    Specialization for an integer value.
    """

    TYPE_INT = "i"

    def __init__(self, name):
        super().__init__(name, StreamMemberInt.TYPE_INT)

        self._value = 0

    def update(self, value):
        self._value = value
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._value}


class StreamMemberIntList(StreamMember):
    """
    Specialization for a list of integer.
    """

    TYPE_INT_LIST = "il"

    def __init__(self, name):
        super().__init__(name, StreamMemberIntList.TYPE_INT_LIST)

        self._value = 0

    def update(self, int_array):
        self._value = int_array
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._value}


class StreamMemberFloat(StreamMember):
    """
    Specialization for a signal float value.
    """

    TYPE_FLOAT = "f"

    def __init__(self, name):
        super().__init__(name, StreamMemberFloat.TYPE_FLOAT)

        self._value = 0.0

    def update(self, value):
        self._value = value
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._value}


class StreamMemberDict(StreamMember):
    """
    Specialization for a signal dict (object) value.
    """

    TYPE_DICT = "d"

    def __init__(self, name):
        super().__init__(name, StreamMemberDict.TYPE_DICT)

        self._value = {}

    def update(self, value):
        self._value = value
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._value}


class StreamMemberFloatTuple(StreamMember):
    """
    Specialization for a signal float tuple values.
    """

    TYPE_FLOAT_TUPLE = "ft"

    def __init__(self, name):
        super().__init__(name, StreamMemberFloatTuple.TYPE_FLOAT_TUPLE)
        self._values = []

    def update(self, array):
        self._values = array
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._values}


class StreamMemberFloatSerie(StreamMember):
    """
    Specialization for a signal float series value.
    """

    TYPE_FLOAT_SERIE = "fs"

    def __init__(self, name, index):
        super().__init__(name, StreamMemberFloatSerie.TYPE_FLOAT_SERIE)

        self._index = index
        self._base = 0.0
        self._timestamp = 0.0
        self._value = 0.0

    def update(self, value, timestamp):
        self._value = value
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 'i': self._index, 't': self._type, 'v': self._value, 'b': self._timestamp}


class StreamMemberFloatBarSerie(StreamMember):
    """
    Specialization for a signal float bar series value.
    """

    TYPE_FLOAT_BAR_SERIE = "fbs"

    def __init__(self, name, index):
        super().__init__(name, StreamMemberFloatBarSerie.TYPE_FLOAT_BAR_SERIE)

        self._index = index
        self._base = 0.0
        self._timestamp = 0.0
        self._value = 0.0

    def update(self, value, timestamp):
        self._value = value
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 'i': self._index, 't': self._type, 'v': self._value, 'b': self._timestamp}


class StreamMemberStrList(StreamMember):
    """
    Specialization for a list of str.
    """

    TYPE_STRING_LIST = "sl"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrList.TYPE_STRING_LIST)

        self._value = 0.0

    def update(self, str_list):
        self._value = str_list
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._value}


class StreamMemberTradeEntry(StreamMember):
    """
    Specialization for a trade entry.
    """

    TYPE_TRADE_ENTRY = "to"

    def __init__(self, name):
        super().__init__(name, StreamMemberTradeEntry.TYPE_TRADE_ENTRY)

        self._timestamp = 0.0
        self._trade = {}

    def update(self, strategy_trader, trade, timestamp):
        self._trade = trade.dumps_notify_entry(timestamp, strategy_trader)
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._trade, 'b': self._timestamp}


class StreamMemberTradeUpdate(StreamMember):
    """
    Specialization for a trade update.
    """

    TYPE_TRADE_UPDATE = "tu"

    def __init__(self, name):
        super().__init__(name, StreamMemberTradeUpdate.TYPE_TRADE_UPDATE)

        self._timestamp = 0.0
        self._trade = {}

    def update(self, strategy_trader, trade, timestamp):
        self._trade = trade.dumps_notify_update(timestamp, strategy_trader)
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._trade, 'b': self._timestamp}


class StreamMemberTradeExit(StreamMember):
    """
    Specialization for a trade exit.
    """

    TYPE_TRADE_EXIT = "tx"

    def __init__(self, name):
        super().__init__(name, StreamMemberTradeExit.TYPE_TRADE_EXIT)

        self._timestamp = 0.0
        self._trade = {}

    def update(self, strategy_trader, trade, timestamp):
        self._trade = trade.dumps_notify_exit(timestamp, strategy_trader)
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._trade, 'b': self._timestamp}


class StreamMemberTradeSignal(StreamMember):
    """
    Specialization for a trade signal.
    """

    TYPE_TRADE_SIGNAL = "ts"

    def __init__(self, name):
        super().__init__(name, StreamMemberTradeSignal.TYPE_TRADE_SIGNAL)

        self._timestamp = 0.0
        self._trade_signal = {}

    def update(self, strategy_trader, trade_signal, timestamp):
        self._trade_signal = trade_signal.dumps_notify(timestamp, strategy_trader)
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._trade_signal, 'b': self._timestamp}


class StreamMemberStrategyAlert(StreamMember):
    """
    Specialization for a strategy triggered alert signal.
    """

    TYPE_STRATEGY_ALERT = "sa"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrategyAlert.TYPE_STRATEGY_ALERT)

        self._timestamp = 0.0
        self._alert = {}

    def update(self, strategy_trader, alert, result, timestamp):
        self._alert = alert.dumps_notify(timestamp, result, strategy_trader)
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._alert, 'b': self._timestamp}


class StreamMemberStrategyAlertCreate(StreamMember):
    """
    Specialization for a strategy active alert creation.
    """

    TYPE_STRATEGY_ALERT_CREATE = "ca"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrategyAlertCreate.TYPE_STRATEGY_ALERT_CREATE)

        self._timestamp = 0.0
        self._alert_data = {}

    def update(self, strategy_trader, active_alert, timestamp):
        self._alert_data = active_alert.dumps()
        self._alert_data['market-id'] = strategy_trader.instrument.market_id
        self._alert_data['symbol'] = strategy_trader.instrument.symbol

        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._alert_data, 'b': self._timestamp}


class StreamMemberStrategyAlertRemove(StreamMember):
    """
    Specialization for a strategy active alert removed.
    """

    TYPE_STRATEGY_ALERT_REMOVE = "ra"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrategyAlertRemove.TYPE_STRATEGY_ALERT_REMOVE)

        self._timestamp = 0.0
        self._active_alert_id = -1

    def update(self, strategy_trader, active_alert_id, timestamp):
        self._active_alert_id = active_alert_id
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._active_alert_id, 'b': self._timestamp}


class StreamMemberStrategyRegion(StreamMember):
    """
    Specialization for a strategy region.
    """

    TYPE_STRATEGY_REGION = "sr"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrategyRegion.TYPE_STRATEGY_REGION)

        self._timestamp = 0.0
        self._region = {}

    def update(self, strategy_trader, region, result, timestamp):
        self._region = region.dumps_notify(timestamp, result, strategy_trader)
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._region, 'b': self._timestamp}


class StreamMemberStrategyRegionCreate(StreamMember):
    """
    Specialization for a strategy active region creation.
    """

    TYPE_STRATEGY_REGION_CREATE = "cr"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrategyRegionCreate.TYPE_STRATEGY_REGION_CREATE)

        self._timestamp = 0.0
        self._region_data = {}

    def update(self, strategy_trader, region, timestamp):
        self._region_data = region.dumps()
        self._region_data['market-id'] = strategy_trader.instrument.market_id
        self._region_data['symbol'] = strategy_trader.instrument.symbol

        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._region_data, 'b': self._timestamp}


class StreamMemberStrategyRegionRemove(StreamMember):
    """
    Specialization for a strategy active region removed.
    """

    TYPE_STRATEGY_REGION_REMOVE = "rr"

    def __init__(self, name):
        super().__init__(name, StreamMemberStrategyRegionRemove.TYPE_STRATEGY_REGION_REMOVE)

        self._timestamp = 0.0
        self._region_id = -1

    def update(self, strategy_trader, region_id, timestamp):
        self._region_id = region_id
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._region_id, 'b': self._timestamp}


class StreamMemberSerie(StreamMember):
    """
    Specialization for a serie begin/end. Value is a float second timestamp.
    """

    TYPE_SERIE = "se"

    def __init__(self, name):
        super().__init__(name, StreamMemberSerie.TYPE_SERIE)

        self._timestamp = 0.0
        self._value = 0.0

    def update(self, timestamp):
        self._value = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._value}


class StreamMemberFloatScatter(StreamMember):
    """
    Specialization for a signal float scatter value.
    """

    TYPE_FLOAT_SCATTER = "fsc"

    def __init__(self, name, index, glyph):
        super().__init__(name, StreamMemberFloatScatter.TYPE_FLOAT_SCATTER)

        self._index = index
        self._base = 0.0
        self._timestamp = 0.0
        self._value = 0.0
        self._glyph = glyph

    def update(self, value, timestamp):
        self._value = value
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 'i': self._index, 't': self._type, 'v': self._value, 'b': self._timestamp, 'o': self._glyph}


class StreamMemberOhlcSerie(StreamMember):
    """
    Specialization for a signal OHLC value.
    """

    TYPE_OHLC_SERIE = "os"

    def __init__(self, name):
        super().__init__(name, StreamMemberOhlcSerie.TYPE_OHLC_SERIE)

        self._index = 0
        self._timestamp = 0.0
        self._value = (0.0, 0.0, 0.0, 0.0)

    def update(self, v, timestamp):
        self._value = v  # quadruplet
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 'i': self._index, 't': self._type, 'v': self._value, 'b': self._timestamp}


class StreamMemberWatcherTicker(StreamMember):
    """
    Specialization for a watcher ticker.
    """

    TYPE_WATCHER_TICKER = "tk"

    def __init__(self, name):
        super().__init__(name, StreamMemberWatcherTicker.TYPE_WATCHER_TICKER)

        self._timestamp = 0.0
        self._ticker = {}

    def update(self, ticker, timestamp):
        self._ticker = ticker
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._ticker, 'b': self._timestamp}


class StreamMemberTraderBalance(StreamMember):
    """
    Specialization for a trader asset or margin balance.

    balance is a dict with field :
    for margin balance : {
        'asset': 'balance',
        'type': 'margin',
        'free': free,
        'locked': locked,
        'total': total,
        'upnl': upnl,
        'margin-level': margin_level
    }

    for an asset : {
        'asset': symbol,
        'type': 'asset',
        'free': free,
        'locked': locked,
        'total': total
    }
    """

    TYPE_TRADER_BALANCE = "ab"

    def __init__(self, name):
        super().__init__(name, StreamMemberTraderBalance.TYPE_TRADER_BALANCE)

        self._timestamp = 0.0
        self._balance = {}

    def update(self, balance, timestamp):
        self._balance = balance
        self._timestamp = timestamp
        self._updated = True

    def content(self):
        return {'n': self._name, 't': self._type, 'v': self._balance, 'b': self._timestamp}
