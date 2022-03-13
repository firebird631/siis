# @date 2018-08-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Instrument symbol

import math

from datetime import datetime, timedelta
from common.utils import UTC, timeframe_to_str, truncate, decimal_place

import logging
logger = logging.getLogger('siis.instrument.instrument')


class Candle(object):
    """
    Candle for an instrument.

    @note 8 floats + 1 bool
    """

    __slots__ = '_timestamp', '_timeframe', '_open', '_high', '_low', '_close', '_spread', '_volume', '_ended'

    def __init__(self, timestamp, timeframe):
        self._timestamp = timestamp
        self._timeframe = timeframe
        
        self._open = 0.000000001
        self._high = 0.000000001
        self._low = 0.000000001
        self._close = 0.000000001

        self._spread = 0.0
        self._volume = 0
        self._ended = True

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def timeframe(self):
        return self._timeframe

    @property
    def open(self):
        return self._open

    @property
    def high(self):
        return self._high

    @property
    def low(self):
        return self._low

    @property
    def close(self):
        return self._close

    @property
    def spread(self):
        return self._spread

    @property
    def ended(self):
        return self._ended

    @property
    def volume(self):
        return self._volume

    @property
    def height(self):
        return self.high - self.low
    
    def set(self, last): 
        self._open = last
        self._high = last
        self._low = last
        self._close = last

    def set_ohlc(self, o, h, l, c): 
        self._open = o
        self._high = h
        self._low = l
        self._close = c

    def set_volume(self, ltv):
        self._volume = ltv

    def set_ohlc_s_v(self, o, h, l, c, s, v):
        self._open = o
        self._high = h
        self._low = l
        self._close = c
        self._spread = s
        self._volume = v

    def set_spread(self, spread):
        self._spread = spread

    def set_consolidated(self, cons):
        self._ended = cons

    def copy(self, dup):
        self._open = dup._open
        self._high = dup._high
        self._low = dup._low
        self._close = dup._close
        self._spread = dup._spread

    def __repr__(self):
        return "%s %s %s/%s/%s/%s" % (
            timeframe_to_str(self._timeframe),
            self._timestamp,
            self._open,
            self._high,
            self._low,
            self._close)


class BuySellSignal(object):

    ORDER_ENTRY = 0
    ORDER_EXIT = 1

    __slots__ = '_timestamp', '_timeframe', '_strategy', '_order_type', '_direction', '_exec_price', '_params'

    def __init__(self, timestamp, timeframe):
        self._timestamp = timestamp
        self._timeframe = timeframe
        self._strategy = None
        self._order_type = BuySellSignal.ORDER_ENTRY
        self._direction = None
        self._exec_price = 0
        self._params = {}

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def timeframe(self):
        return self._timeframe

    @property
    def strategy(self):
        return self._strategy
    
    @property
    def direction(self):
        return self._direction
    
    @property
    def order_type(self):
        return self._order_type

    @property
    def exec_price(self):
        return self._exec_price

    def set_data(self, strategy, order_type, direction, exec_price, timeframe):
        self._strategy = strategy
        self._order_type = order_type
        self._direction = direction
        self._exec_price = exec_price
        self._timeframe = timeframe

    @property
    def params(self):
        return self._params
    
    @params.setter
    def params(self, params):
        self._params = params


class Instrument(object):
    """
    Instrument is the strategy side of the market model.
    Its a denormalized model because it duplicate some members used during strategy processing,
    to avoid dealing with the trader thread/process.

    @member symbol str Common usual name (ex: EURUSD, BTCUSD).
    @member market_id str Unique broker identifier.
    @member alias str A secondary or display name.

    @todo may we need hedging, leverage limits, contract_size, lot_size ?
    """

    TF_TICK = 0
    TF_TRADE = TF_TICK
    TF_T = TF_TICK
    TF_SEC = 1
    TF_1S = TF_SEC
    TF_10SEC = 10
    TF_10S = TF_10SEC
    TF_15SEC = 15
    TF_15S = TF_15SEC
    TF_30SEC = 30
    TF_30S = TF_30SEC
    TF_MIN = 60
    TF_1M = TF_MIN
    TF_2MIN = 60*2
    TF_2M = TF_2MIN
    TF_3MIN = 60*3
    TF_3M = TF_3MIN
    TF_5MIN = 60*5
    TF_5M = TF_5MIN
    TF_10MIN = 60*10
    TF_10M = TF_10MIN
    TF_15MIN = 60*15
    TF_15M = TF_15MIN
    TF_30MIN = 60*30
    TF_30M = TF_30MIN
    TF_HOUR = 60*60
    TF_1H = TF_HOUR
    TF_2HOUR = 60*60*2
    TF_2H = TF_2HOUR
    TF_3HOUR = 60*60*3
    TF_3H = TF_3HOUR
    TF_4HOUR = 60*60*4
    TF_4H = TF_4HOUR
    TF_6HOUR = 60*60*6
    TF_6H = TF_6HOUR
    TF_8HOUR = 60*60*8
    TF_8H = TF_8HOUR
    TF_12HOUR = 60*60*12
    TF_12H = TF_12HOUR
    TF_DAY = 60*60*24
    TF_1D = TF_DAY
    TF_2DAY = 60*60*24*2
    TF_2D = TF_2DAY
    TF_3DAY = 60*60*24*3
    TF_3D = TF_3DAY
    TF_WEEK = 60*60*24*7
    TF_1W = TF_WEEK
    TF_MONTH = 60*60*24*30

    PRICE_OPEN = 0
    PRICE_HIGH = 1
    PRICE_LOW = 2
    PRICE_CLOSE = 3

    CONTRACT_UNDEFINED = 0
    CONTRACT_CFD = 1
    CONTRACT_FUTURE = 2

    TYPE_UNKNOWN = 0
    TYPE_CURRENCY = 1
    TYPE_CRYPTO = 2
    TYPE_STOCK = 3
    TYPE_COMMODITY = 4
    TYPE_INDICE = 5

    UNIT_UNDEFINED = 0
    UNIT_CONTRACT = 1     # amount is in contract size
    UNIT_CURRENCY = 2     # amount is in currency (quote)
    UNIT_LOT = 3          # unit of one lot, with 1 lot = 100000 of related currency

    MAKER = 0
    TAKER = 1

    TRADE_BUY_SELL = 1     # no margin no short, only buy (hold) and sell
    TRADE_ASSET = 1        # synonym for buy-sell/spot
    TRADE_SPOT = 1         # synonym for buy-sell/asset
    TRADE_MARGIN = 2       # margin, long and short
    TRADE_IND_MARGIN = 4   # indivisible position, margin, long and short
    TRADE_FIFO = 8         # positions are closed in FIFO order
    TRADE_POSITION = 16    # individual position on the broker side

    ORDER_MARKET = 0
    ORDER_LIMIT = 1
    ORDER_STOP_MARKET = 2
    ORDER_STOP_LIMIT = 4
    ORDER_TAKE_PROFIT_MARKET = 8
    ORDER_TAKE_PROFIT_LIMIT = 16
    ORDER_ALL = 32-1

    TRADE_QUANTITY_DEFAULT = 0
    TRADE_QUANTITY_QUOTE_TO_BASE = 1

    __slots__ = '_watchers', '_market_id', '_symbol', '_alias', '_tradeable', '_currency', \
                '_trade_quantity', '_trade_quantity_mode', '_leverage', \
                '_market_bid', '_market_ask', '_last_update_time', \
                '_vol24h_base', '_vol24h_quote', '_fees', \
                '_size_limits', '_price_limits', '_notional_limits', \
                '_ticks', '_tickbars', '_candles', '_buy_sells', '_wanted', \
                '_base', '_quote', '_trade', '_orders', \
                '_hedging', '_expiry', '_value_per_pip', '_one_pip_means', \
                '_evening_session', '_overnight_session', '_week_session'

    def __init__(self, market_id, symbol, alias=None):
        self._watchers = {}
        self._market_id = market_id
        self._symbol = symbol
        self._alias = alias
        self._tradeable = True
        self._expiry = "-"

        self._base = ""
        self._quote = ""

        self._trade = 0
        self._orders = 0

        self._hedging = False

        self._currency = "USD"

        self._trade_quantity = 0.0
        self._trade_quantity_mode = Instrument.TRADE_QUANTITY_DEFAULT

        self._leverage = 1.0  # 1 / margin_factor

        self._market_bid = 0.0
        self._market_ask = 0.0
        self._last_update_time = 0.0

        self._vol24h_base = None
        self._vol24h_quote = None

        self._fees = ([0.0, 0.0], [0.0, 0.0])  # ((maker fee, taker fee), (maker commission, taker commission))

        self._size_limits = (0.0, 0.0, 0.0, 0)
        self._price_limits = (0.0, 0.0, 0.0, 0)
        self._notional_limits = (0.0, 0.0, 0.0, 0)

        self._ticks = []      # list of tuple(timestamp, bid, ask, last, volume, direction)
        self._candles = {}    # list per timeframe
        self._buy_sells = {}  # list per timeframe
        self._tickbars = []   # list of TickBar

        self._one_pip_means = 1.0
        self._value_per_pip = 1.0

        # evening session from 00h00m00s000ms to 23h59m59s999ms in UTC
        self._evening_session = (0.0, 24*60*60.0-0.001)

        # no overnight session by default else a tuple of two durations in seconds
        self._overnight_session = None

        # no week session mean every day markets, else a tuple of two float timedelta in seconds
        self._week_session = None

        self._wanted = []  # list of wanted timeframe before be ready (its only for initialization)

    def add_watcher(self, watcher_type, watcher):
        if watcher:
            self._watchers[watcher_type] = watcher

    def watcher(self, watcher_type):
        return self._watchers.get(watcher_type)

    @property
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, symbol):
        self._symbol = symbol

    @property
    def alias(self):
        return self._alias

    @alias.setter
    def alias(self, alias):
        self._alias = alias

    @property
    def market_id(self):
        return self._market_id

    @property
    def tradeable(self):
        return self._tradeable

    @tradeable.setter
    def tradeable(self, status):
        self._tradeable = status

    #
    # instrument trade type
    #

    @property
    def trade(self):
        return self._trade

    @trade.setter
    def trade(self, trade):
        self._trade = trade

    @property
    def has_spot(self):
        return self._trade & Instrument.TRADE_SPOT == Instrument.TRADE_SPOT

    @property
    def has_margin(self):
        return self._trade & Instrument.TRADE_MARGIN == Instrument.TRADE_MARGIN

    @property
    def indivisible_position(self):
        return self._trade & Instrument.TRADE_IND_MARGIN == Instrument.TRADE_IND_MARGIN

    @property
    def fifo_position(self):
        return self._trade & Instrument.TRADE_FIFO == Instrument.TRADE_FIFO

    @property
    def has_position(self):
        return self._trade & Instrument.TRADE_POSITION == Instrument.TRADE_POSITION

    @property
    def orders(self):
        return self._orders

    @orders.setter
    def orders(self, flags):
        self._orders = flags

    def set_quote(self, symbol):
        self._quote = symbol

    @property
    def quote(self):
        return self._quote

    def set_base(self, symbol):
        self._base = symbol

    @property
    def base(self):
        return self._base

    @property
    def hedging(self):
        return self._hedging
    
    @hedging.setter
    def hedging(self, hedging):
        self._hedging = hedging

    @property
    def currency(self):
        return self._currency

    @currency.setter
    def currency(self, currency):
        self._currency = currency

    @property
    def expiry(self):
        return self._expiry
    
    @expiry.setter
    def expiry(self, expiry):
        self._expiry = expiry

    #
    # options
    #

    @property
    def trade_quantity(self):
        return self._trade_quantity

    @trade_quantity.setter
    def trade_quantity(self, quantity):
        if quantity > 0.0:
            self._trade_quantity = quantity

    @property
    def trade_quantity_mode(self):
        return self._trade_quantity_mode

    @trade_quantity_mode.setter
    def trade_quantity_mode(self, trade_quantity_mode):
        self._trade_quantity_mode = trade_quantity_mode

    def trade_quantity_mode_to_str(self):
        if self._trade_quantity_mode == Instrument.TRADE_QUANTITY_DEFAULT:
            return "default"
        elif self._trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            return "quote-to-base"
        else:
            return "unknown"

    #
    # market session
    #

    @property
    def evening_session(self):
        return self._evening_session

    @property
    def overnight_session(self):
        return self._overnight_session

    @property
    def has_overnight_session(self):
        return self._overnight_session is not None

    @property
    def session_offset(self):
        return -self._evening_session[0]

    @property
    def week_session(self):
        return self._week_session

    @property
    def has_week_session(self):
        return self._week_session is not None

    #
    # price/volume
    #

    @property
    def market_bid(self):
        return self._market_bid

    @market_bid.setter
    def market_bid(self, bid):
        self._market_bid = bid

    @property
    def market_ask(self):
        return self._market_ask

    @market_ask.setter
    def market_ask(self, ask):
        self._market_ask = ask

    @property
    def market_price(self):
        return (self._market_bid + self._market_ask) * 0.5

    @property
    def market_spread(self):
        return self._market_ask - self._market_bid

    @property
    def last_update_time(self):
        return self._last_update_time

    @last_update_time.setter
    def last_update_time(self, last_update_time):
        self._last_update_time = last_update_time

    @property
    def vol24h_base(self):
        return self._vol24h_base
    
    @property
    def vol24h_quote(self):
        return self._vol24h_quote
    
    @vol24h_base.setter
    def vol24h_base(self, v):
        self._vol24h_base = v

    @vol24h_quote.setter
    def vol24h_quote(self, v):
        self._vol24h_quote = v
 
    #
    # limits
    #

    @property
    def size_limits(self):
        return self._size_limits

    @property
    def min_size(self):
        return self._size_limits[0]

    @property
    def max_size(self):
        return self._size_limits[1]

    @property
    def step_size(self):
        return self._size_limits[2]

    @property
    def size_precision(self):
        return self._size_limits[3]

    @property
    def notional_limits(self):
        return self._notional_limits

    @property
    def min_notional(self):
        return self._notional_limits[0]

    @property
    def max_notional(self):
        return self._notional_limits[1]

    @property
    def step_notional(self):
        return self._notional_limits[2]

    @property
    def notional_precision(self):
        return self._notional_limits[3]

    @property
    def price_limits(self):
        return self._price_limits

    @property
    def min_price(self):
        return self._price_limits[0]

    @property
    def max_price(self):
        return self._price_limits[1]

    @property
    def step_price(self):
        return self._price_limits[2]

    @property
    def tick_price(self):
        return self._price_limits[2]

    @property
    def price_precision(self):
        return self._price_limits[3]

    @property
    def value_per_pip(self):
        return self._value_per_pip

    @property
    def one_pip_means(self):
        return self._one_pip_means

    @property
    def leverage(self):
        """
        Account and instrument related leverage.
        """
        return self._leverage
    
    @leverage.setter
    def leverage(self, leverage):
        self._leverage = leverage

    def set_size_limits(self, min_size, max_size, step_size):
        size_precision = max(0, decimal_place(step_size) if step_size > 0 else 0)
        self._size_limits = (min_size, max_size, step_size, size_precision)

    def set_notional_limits(self, min_notional, max_notional, step_notional):
        notional_precision = max(0, decimal_place(step_notional) if step_notional > 0 else 0)
        self._notional_limits = (min_notional, max_notional, step_notional, notional_precision)

    def set_price_limits(self, min_price, max_price, step_price):
        price_precision = max(0, decimal_place(step_price) if step_price > 0 else 0)
        self._price_limits = (min_price, max_price, step_price, price_precision)

    @value_per_pip.setter
    def value_per_pip(self, value_per_pip):
        self._value_per_pip = value_per_pip

    @one_pip_means.setter
    def one_pip_means(self, one_pip_means):
        self._one_pip_means = one_pip_means

    #
    # ticks or candles
    #

    def check_temporal_coherency(self, tf):
        """
        Check temporal coherency of the candles and return the list of incoherence.
        """
        issues = []

        for tf, candles in self._candles.items():
            candles = self._candles.get(tf)
            number = len(candles)
            if candles:
                for i in range(len(candles)-1, max(-1, len(candles)-number-1), -1):
                    if candles[i].timestamp - candles[i-1].timestamp != tf:
                        logger.error("Timestamp inconsistency from %s and %s candles at %s delta=(%s)" % (
                            i, i-1, candles[i-1].timestamp, candles[i].timestamp - candles[i-1].timestamp))

                        issues.append(('ohlc', tf, i, i-1, candles[i-1].timestamp,
                                       candles[i].timestamp - candles[i-1].timestamp))

        for tf, buy_sells in self._buy_sells.items():
            if buy_sells:
                number = len(buy_sells)
                for i in range(len(buy_sells)-1, max(-1, len(buy_sells)-number-1), -1):
                    if buy_sells[i].timestamp - buy_sells[i-1].timestamp != tf:
                        logger.error("Timestamp inconsistency from %s and %s buy/sell signals at %s delta=(%s)" % (
                            i, i-1, buy_sells[i-1].timestamp, buy_sells[i].timestamp - buy_sells[i-1].timestamp))

                        issues.append(('buysell', tf, i, i-1, buy_sells[i-1].timestamp,
                                       buy_sells[i].timestamp - buy_sells[i-1].timestamp))

        ticks = self._ticks
        if ticks:
            number = len(ticks)
            for i in range(len(ticks)-1, max(-1, len(ticks)-number-1), -1):
                if ticks[i][0] - ticks[i-1][0] != tf:                    
                    logger.error("Timestamp inconsistency from %s and %s ticks at %s delta=(%s)" % (
                        i, i-1, ticks[i-1][0], ticks[i][0] - ticks[i-1][0]))

                    issues.append(('tick', 0, i, i-1, ticks[i-1][0], ticks[i][0] - ticks[i-1][0]))
        
        return issues

    #
    # candles OHLC
    #

    def add_candles(self, candles_list, max_candles=-1):
        """
        Append an array of new candle.
        @param candles_list
        @param max_candles Pop candles until num candles > max_candles.
        """
        if not candles_list:
            return

        # array of candles
        tf = candles_list[0]._timeframe

        if self._candles.get(tf):
            candles = self._candles[tf]

            if len(candles) > 0:
                for c in candles_list:
                    # for each candle only add it if more recent or replace a non consolidated
                    if c.timestamp > candles[-1].timestamp:
                        if not candles[-1].ended:
                            # remove the last candle if was not consolidated
                            # candles.pop(-1)
                            candles[-1].set_consolidated(True)

                        candles.append(c)

                    elif c.timestamp == candles[-1].timestamp and not candles[-1].ended:
                        # replace the last candle if was not consolidated
                        candles[-1] = c
            else:
                # initiate array
                candles.extend(candles_list)
        else:
            self._candles[tf] = candles_list

        # keep safe size
        if max_candles > 1:
            candles = self._candles[tf]
            if candles:
                while(len(candles)) > max_candles:
                    candles.pop(0)

    def add_candle(self, candle, max_candles=-1):
        """
        Append a new candle.
        @param candle
        @param max_candles Pop candles until num candles > max_candles.
        """
        if not candle:
            return

        # single candle
        if self._candles.get(candle._timeframe):
            candles = self._candles[candle._timeframe]

            if len(candles) > 0:
                # ignore the candle if older than the latest
                if candle.timestamp > candles[-1].timestamp:
                    if not candles[-1].ended:
                        # replace the last candle if was not consolidated
                        # candles[-1] = candle
                        candles[-1].set_consolidated(True)
                        candles.append(candle)
                    else:
                        candles.append(candle)

                elif candle.timestamp == candles[-1].timestamp and not candles[-1].ended:
                    # replace the last candle if was not consolidated
                    candles[-1] = candle
            else:
                candles.append(candle)
        else:
            self._candles[candle._timeframe] = [candle]

        # keep safe size
        if max_candles > 1:
            candles = self._candles[candle._timeframe]
            if candles:
                while(len(candles)) > max_candles:
                    candles.pop(0)

    def last_candles(self, tf, number):
        """
        Return as possible last n candles with a fixed step of time unit.
        """
        results = [Candle(0, tf)] * number

        candles = self._candles.get(tf)
        if candles:
            j = number - 1
            for i in range(len(candles)-1, max(-1, len(candles)-number-1), -1):
                results[j] = candles[i]
                j -= 1

        return results

    def candle(self, tf):
        """
        Return as possible the last candle.
        """
        candles = self._candles.get(tf)
        if candles:
            return candles[-1]

        return None

    def candles(self, tf):
        """
        Returns candles list for a specific timeframe.
        @param tf Timeframe
        """
        return self._candles.get(tf)

    def reduce_candles(self, timeframe, max_candles):
        """
        Reduce the number of candle to max_candles.
        """
        if not max_candles or not timeframe:
            return

        if self._candles.get(timeframe):
            candles = self._candles[timeframe][-max_candles:]

    def last_ended_timestamp(self, tf):
        """
        Returns the timestamp of the last consolidated candle for a specific time unit.
        """
        candles = self._candles.get(tf)
        if candles:
            if candles[-1].ended:
                return candles[-1].timestamp
            elif not candles[-1].ended and len(candles) > 1:
                return candles[-2].timestamp

        return 0.0

    def candles_from(self, tf, from_ts):
        """
        Returns candle having timestamp >= from_ts in seconds.
        @param tf Timeframe
        @param from_ts In second timestamp from when to get candles

        @note this is not really a good idea to fill the gap and to have this extra cost of processing because :
            for market closing weekend or night we don't, but on another side candles must be adjacent to have
            further calculations corrects
        """
        results = []

        candles = self._candles.get(tf)
        if candles:
            # process for most recent to the past
            for c in reversed(candles):
                if c.timestamp >= from_ts:
                    # is there a gap between the prev and current candles, introduce missing ones
                    if len(results) and (results[0].timestamp - c.timestamp > tf):
                        ts = results[0].timestamp - tf

                        while ts > c.timestamp:
                            filler = Candle(ts, tf)

                            # same as previous
                            filler.copy(results[-1])

                            # empty volume
                            filler._volume = 0

                            results.insert(0, filler)
                            ts -= tf

                    results.insert(0, c)
                else:
                    break

        return results

    def candles_after(self, tf, after_ts):
        """
        Returns candle having timestamp >= after_ts in seconds.
        @param tf Timeframe
        @param after_ts In second timestamp after when to get candles
        """
        results = []

        candles = self._candles.get(tf)
        if candles:
            # process for most recent to the past
            for c in reversed(candles):
                if c.timestamp > after_ts:
                    # is there a gap between the prev and current candles, introduce missing ones
                    if len(results) and (results[0].timestamp - c.timestamp > tf):
                        ts = results[0].timestamp - tf

                        while ts > c.timestamp:
                            filler = Candle(ts, tf)

                            # same as previous
                            filler.copy(results[-1])

                            # empty volume
                            filler._volume = 0

                            results.insert(0, filler)
                            ts -= tf

                    results.insert(0, c)
                else:
                    break

        return results

    #
    # ticks
    #

    def add_ticks(self, ticks_list):
        if not ticks_list:
            return

        ticks = self._ticks

        if len(ticks) > 0:
            for t in ticks_list:
                # for each tick only add it if more recent
                if t[0] > ticks[-1][0]:
                    ticks.append(t)
        else:
            # initiate array
            self._ticks = ticks_list

    def add_tick(self, tick):
        if not tick:
            return

        ticks = self._ticks

        if len(ticks) > 0:
            # ignore the tick if older than the last one
            if tick[0] > ticks[-1][0]:
                ticks.append(tick)
        else:
            ticks.append(tick)

    def clear_ticks(self):
        self._ticks.clear()

    def ticks(self):
        return self._ticks

    def detach_ticks(self):
        """
        Detach the array of tick and setup a new empty for the instrument.
        """
        ticks = self._ticks
        self._ticks = []
        return ticks

    def ticks_after(self, after_ts):
        """
        Returns ticks having timestamp > from_ts in seconds.
        """
        results = []

        ticks = self._ticks
        if ticks:
            # process for more recent to the past
            for t in reversed(ticks):
                if t[0] > after_ts:
                    results.insert(0, t)
                else:
                    break

        return results

    #
    # tick-bar
    #
    
    def add_tickbars(self, tickbars_list, max_tickbars=-1):
        """
        Append an array of new tickbars.
        @param tickbars_list
        @param max_tickbars Pop tickbars until num tickbars > max_tickbars.
        """
        if not tickbars_list:
            return

        tickbars = self._tickbars

        # array of tickbar
        if len(tickbars) > 0:
            for t in tickbars_list:
                # for each tickbar only add it if more recent or replace a non consolidated
                if t.timestamp > tickbars[-1].timestamp:
                    if not tickbars[-1].ended:
                        # remove the last tickbar if was not consolidated
                        tickbars.pop(-1)

                    tickbars.append(t)

                elif t.timestamp == tickbars[-1].timestamp and not tickbars[-1].ended:
                    # replace the last tickbar if was not consolidated
                    tickbars[-1] = t
        else:
            # initiate array
            self._tickbars = tickbars_list

        # keep safe size
        if max_tickbars > 1:
            while(len(tickbars)) > max_tickbars:
                tickbars.pop(0)

    def add_tickbar(self, tickbar, max_tickbars=-1):
        """
        Append a new tickbar.
        @param tickbar
        @param max_tickbars Pop tickbars until num tickbars > max_tickbars.
        """
        if not tickbar:
            return

        tickbars = self._tickbars

        # single tickbar
        if len(self._tickbars) > 0:
            # ignore the tickbar if older than the latest
            if tickbar.timestamp > tickbars[-1].timestamp:
                if not tickbars[-1].ended:
                    # replace the last tickbar if was not consolidated
                    tickbars[-1] = tickbar
                else:
                    tickbars.append(tickbar)

            elif tickbar.timestamp == tickbars[-1].timestamp and not tickbars[-1].ended:
                # replace the last tickbar if was not consolidated
                tickbars[-1] = tickbar
        else:
            tickbars.append(tickbar)

        # keep safe size
        if max_tickbars > 1:
            while(len(tickbars)) > max_tickbars:
                tickbars.pop(0)

    def tickbar(self):
        """
        Return as possible the last tickbar.
        """
        if self._tickbars:
            return self._tickbars[-1]

        return None

    def tickbars(self):
        """
        Returns tickbars list.
        """
        return self._tickbars

    #
    # sync
    #

    def ready(self):
        """
        Return true when ready to process.
        """
        return not self._wanted

    def want_timeframe(self, timeframe):
        """
        Add a required candles for a specific timeframe.
        """
        self._wanted.append(timeframe)

    def is_want_timeframe(self, timeframe):
        """
        Check if a timeframe is wanted.
        """
        return timeframe in self._wanted

    def ack_timeframe(self, timeframe):
        """
        Clear wanted timeframe status and returns true if it was wanted.
        """
        if timeframe in self._wanted:
            self._wanted.remove(timeframe)
            return True

        return False

    def open_exec_price(self, direction, maker=False):
        """
        Return the execution price if an order open a position.
        It depend of the direction of the order and the market bid/ask prices.
        If position is long, then returns the market ask price.
        If position is short, then returns the market bid price.
        """
        if direction > 0:
            return self._market_ask if not maker else self._market_bid
        elif direction < 0:
            return self._market_bid if not maker else self._market_ask
        else:
            return (self._market_ask + self._market_bid) * 0.5

    def close_exec_price(self, direction, maker=False):
        """
        Return the execution price if an order/position is closing.
        It depend of the direction of the order and the market bid/ask prices.
        If position is long, then returns the market bid price.
        If position is short, then returns the market ask price.
        """
        if direction > 0:
            return self._market_bid if not maker else self._market_ask
        elif direction < 0:
            return self._market_ask if not maker else self._market_bid
        else:
            return (self._market_bid * self._market_ask) * 0.5

    #
    # format/adjust
    #

    def adjust_price(self, price):
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        precision = self._price_limits[3] or 8
        tick_size = self._price_limits[2] or 0.00000001

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / tick_size) * tick_size, precision)

    def adjust_quote(self, quote):
        """
        Format the quote according to the precision.
        """
        if quote is None:
            quote = 0.0

        precision = self._notional_limits[3] or 2
        tick_size = self._notional_limits[2] or 0.01

        # adjusted quote price at precision and by step of pip meaning
        return truncate(round(quote / tick_size) * tick_size, precision)

    def format_price(self, price):
        """
        Format the price according to the precision.
        """
        if price is None or math.isnan(price):
            price = 0.0

        precision = self._price_limits[3] or 8
        tick_size = self._price_limits[2] or 0.00000001

        adjusted_price = truncate(round(price / tick_size) * tick_size, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove trailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def format_quote(self, quote):
        """
        Format the quote according to the precision.
        """
        if quote is None or math.isnan(quote):
            quote = 0.0

        precision = self._notional_limits[3] or 2
        tick_size = self._notional_limits[2] or 0.01

        adjusted_quote = truncate(round(quote / tick_size) * tick_size, precision)
        formatted_quote = "{:0.0{}f}".format(adjusted_quote, precision)

        # remove trailing 0s and dot
        if '.' in formatted_quote:
            formatted_quote = formatted_quote.rstrip('0').rstrip('.')

        return formatted_quote

    def adjust_quantity(self, quantity, min_is_zero=True):
        """
        From quantity return the floor tradeable quantity according to min, max and rounded to step size.
        To make a precise value for trade use format_value from this returned value.

        @param quantity float Quantity to adjust
        @param min_is_zero boolean Default True. If quantity is lesser than min returns 0 else return min size.
        """
        if quantity is None:
            quantity = 0.0

        if self.min_size > 0.0 and quantity < self.min_size:
            if min_is_zero:
                return 0.0

            return self.min_size

        if 0.0 < self.max_size < quantity:
            return self.max_size

        if self.step_size > 0:
            precision = self._size_limits[3]
            inv_step_size = 1.0 / self.step_size

            # return max(round(int(quantity / self.step_size) * self.step_size, precision), self.min_size)
            # return max(round(self.step_size * round(quantity / self.step_size), precision), self.min_size)
            # return max(round(self.step_size * math.floor(quantity / self.step_size), precision), self.min_size)
            return max(truncate(round(quantity * inv_step_size) * self.step_size, precision), self.min_size)

        return quantity

    def format_quantity(self, quantity):
        """
        Return a quantity as str according to the precision of the step size.
        """
        if quantity is None:
            quantity = 0.0

        precision = self._size_limits[3] or 8
        qty = "{:0.0{}f}".format(truncate(quantity, precision), precision)

        if '.' in qty:
            qty = qty.rstrip('0').rstrip('.')

        return qty

    #
    # fee/commission
    #

    def set_fees(self, maker, taker):
        self._fees[Instrument.MAKER][0] = maker
        self._fees[Instrument.TAKER][0] = taker

    def set_commissions(self, maker, taker):
        self._fees[Instrument.MAKER][1] = maker
        self._fees[Instrument.TAKER][1] = taker

    @property
    def maker_fee(self):
        return self._fees[Instrument.MAKER][0]

    @property
    def taker_fee(self):
        return self._fees[Instrument.TAKER][0]

    @property
    def maker_commission(self):
        return self._fees[Instrument.MAKER][1]

    @property
    def taker_commission(self):
        return self._fees[Instrument.TAKER][1]

    #
    # static
    #

    @staticmethod
    def basetime(tf: float, timestamp: float) -> float:
        if tf <= 0.0:
            return timestamp
        elif tf < 7*24*60*60:
            # simplest
            return int(timestamp / tf) * tf
        elif tf == 7*24*60*60:
            # must find the UTC first day of week
            dt = datetime.utcfromtimestamp(timestamp)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC()) - timedelta(days=dt.weekday())
            return dt.timestamp()
        elif tf == 30*24*60*60:
            # replace by first day of month at 00h00 UTC
            dt = datetime.utcfromtimestamp(timestamp)
            dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC())
            return dt.timestamp()

        return 0.0
