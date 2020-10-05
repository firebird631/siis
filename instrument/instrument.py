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
    @note Ofr is a synonym for ask.

    @note 11 floats + 1 bool
    """

    __slots__ = '_timestamp', '_timeframe', '_bid_open', '_bid_high', '_bid_low', '_bid_close', '_ofr_open', '_ofr_high', '_ofr_low', '_ofr_close', '_volume', '_ended'

    def __init__(self, timestamp, timeframe):
        self._timestamp = timestamp
        self._timeframe = timeframe
        
        self._bid_open = 0.000000001
        self._bid_high = 0.000000001
        self._bid_low = 0.000000001
        self._bid_close = 0.000000001

        self._ofr_open = 0.000000001
        self._ofr_high = 0.000000001
        self._ofr_low = 0.000000001
        self._ofr_close = 0.000000001

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
        return (self._bid_open + self._ofr_open) * 0.5

    @property
    def high(self):
        return (self._bid_high + self._ofr_high) * 0.5  

    @property
    def low(self):
        return (self._bid_low + self._ofr_low) * 0.5

    @property
    def close(self):
        return (self._bid_close + self._ofr_close) * 0.5

    @property
    def spread(self):
        return abs(self._ofr_close - self._bid_close)

    @property
    def ended(self):
        return self._ended

    def bid(self, price_type):
        if price_type == 0:
            return self._bid_open
        if price_type == 1:
            return self._bid_high
        if price_type == 2:
            return self._bid_low
        
        return self._bid_close

    def ofr(self, price_type):
        if price_type == 0:
            return self._ofr_open
        if price_type == 1:
            return self._ofr_high
        if price_type == 2:
            return self._ofr_low

        return self._ofr_close

    @property
    def bid_open(self):
        return self._bid_open
    
    @property
    def bid_high(self):
        return self._bid_high
    
    @property
    def bid_low(self):
        return self._bid_low
    
    @property
    def bid_close(self):
        return self._bid_close
    
    @property
    def ofr_open(self):
        return self._ofr_open
    
    @property
    def ofr_high(self):
        return self._ofr_high
    
    @property
    def ofr_low(self):
        return self._ofr_low
    
    @property
    def ofr_close(self):
        return self._ofr_close

    @property
    def volume(self):
        return self._volume

    @property
    def height(self):
        return self.high - self.low

    def set_bid(self, bid):
        self._bid_open = bid
        self._bid_high = bid
        self._bid_low = bid
        self._bid_close = bid

    def set_ofr(self, ofr):
        self._ofr_open = ofr
        self._ofr_high = ofr
        self._ofr_low = ofr
        self._ofr_close = ofr

    def set_bid_ohlc(self, o, h, l, c): 
        self._bid_open = o
        self._bid_high = h
        self._bid_low = l
        self._bid_close = c

    def set_ofr_ohlc(self, o, h, l, c): 
        self._ofr_open = o
        self._ofr_high = h
        self._ofr_low = l
        self._ofr_close = c

    def set_volume(self, ltv):
        self._volume = ltv

    def set_consolidated(self, cons):
        self._ended = cons

    def copy_bid(self, dup):
        self._bid_open = dup._bid_open
        self._bid_high = dup._bid_high
        self._bid_low = dup._bid_low
        self._bid_close = dup._bid_close

    def copy_ofr(self, dup):
        self._ofr_open = dup._ofr_open
        self._ofr_high = dup._ofr_high
        self._ofr_low = dup._ofr_low
        self._ofr_close = dup._ofr_close

    def __repr__(self):
        return "%s %s bid %s/%s/%s/%s ofr %s/%s/%s/%s" % (
            timeframe_to_str(self._timeframe),
            self._timestamp,
            self._bid_open,
            self._bid_high,
            self._bid_low,
            self._bid_close,
            self._ofr_open,
            self._ofr_high,
            self._ofr_low,
            self._ofr_close)


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

    def set_data(strategy, order, direction, exec_price, timeframe):
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


class Tick(object):
    """
    A tick is a 4 floats tuple with (timestamp, bid, ofr, volume).
    Because class instance take extra memory an CPU cost we uses a simple tuple.
    Those constant of index are helpers/reminders.

    @note ofr is a synonym for ask.
    """

    TIMESTAMP = 0
    BID = 1
    OFR = 2
    VOLUME = 3

    TS = 0
    ASK = 2
    VOL = 3

    T = 0
    B = 1
    O = 2
    V = 3

    @staticmethod
    def timestamp(tick):
        return tick[TS]

    @staticmethod
    def bid(tick):
        return tick[BID]

    @staticmethod
    def ofr(tick):
        return tick[OFR]

    @staticmethod
    def volume(tick):
        return tick[VOL]

    @staticmethod
    def price(tick):
        return (tick[BID] + tick[OFR]) * 0.5

    @staticmethod
    def spread(tick):
        return tick[OFR] - tick[BID]


class Instrument(object):
    """
    Instrument is the strategy side of the market model.
    Its a denormalized model because it duplicate some members used during strategy processing,
    to avoid dealing with the trader thread/process.

    @member name str Comes from the broker usage name (could use the epic or market-id if none other).
    @member symbol str Common usual name (ex: EURUSD, BTCUSD).
    @member market_id str Unique broker identifier.
    @member alias str A secondary or display name.

    @note ofr is a synonym for ask.

    @todo may we need hedging, leverage limits, contract_size, lot_size ?
    """

    TF_TICK = 0
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

    __slots__ = '_watchers', '_name', '_symbol', '_market_id', '_alias', '_tradeable', '_currency', \
                '_trade_quantity', '_trade_max_factor', '_trade_quantity_mode', '_leverage', \
                '_market_bid', '_market_ofr', '_last_update_time', \
                '_vol24h_base', '_vol24h_quote', '_fees', '_size_limits', '_price_limits', '_notional_limits', \
                '_ticks', '_tickbars', '_candles', '_buy_sells', '_wanted', '_base', '_quote', '_trade', '_orders', '_hedging', '_expiry', \
                '_value_per_pip', '_one_pip_means'

    def __init__(self, name, symbol, market_id, alias=None):
        self._watchers = {}
        self._name =  name
        self._symbol = symbol
        self._market_id = market_id
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
        self._trade_max_factor = 1
        self._trade_quantity_mode = Instrument.TRADE_QUANTITY_DEFAULT

        self._leverage = 1.0  # 1 / margin_factor

        self._market_bid = 0.0
        self._market_ofr = 0.0
        self._last_update_time = 0.0

        self._vol24h_base = None
        self._vol24h_quote = None

        self._fees = ([0.0, 0.0], [0.0, 0.0])  # ((maker fee, taker fee), (maker commission, taker commission))

        self._size_limits = (0.0, 0.0, 0.0, 0)
        self._price_limits = (0.0, 0.0, 0.0, 0)
        self._notional_limits = (0.0, 0.0, 0.0, 0)

        self._ticks = []      # list of tuple(timestamp, bid, ofr, volume)
        self._candles = {}    # list per timeframe
        self._buy_sells = {}  # list per timeframe
        self._tickbars = []   # list of TickBar

        self._one_pip_means = 1.0
        self._value_per_pip = 1.0

        self._wanted = []  # list of wanted timeframe before be ready (its only for initialization)

    def add_watcher(self, watcher_type, watcher):
        if watcher:
            self._watchers[watcher_type] = watcher

    def watcher(self, watcher_type):
        return self._watchers.get(watcher_type)

    @property
    def name(self):
        return self._name
    
    @property
    def symbol(self):
        return self._symbol
    
    @property
    def alias(self):
        return self._alias
    
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
    def trade_max_factor(self):
        return self._trade_max_factor

    @trade_max_factor.setter
    def trade_max_factor(self, max_factor):
        if max_factor >= 1:
            self._trade_max_factor = max_factor

    @property
    def trade_quantity_mode(self):
        return self._trade_quantity_mode

    @trade_quantity_mode.setter
    def trade_quantity_mode(self, trade_quantity_mode):
        self._trade_quantity_mode = trade_quantity_mode

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
    def market_ofr(self):
        return self._market_ofr

    @market_ofr.setter
    def market_ofr(self, ofr):
        self._market_ofr = ofr

    @property
    def market_price(self):
        return (self._market_bid + self._market_ofr) * 0.5

    @property
    def market_spread(self):
        return (self._market_ofr - self._market_bid)

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

    def last_prices(self, tf, price_type, number):
        prices = [0] * number

        if tf == 0:
            # get from ticks
            ticks = self._ticks
            if ticks:
                j = number - 1
                for i in range(len(ticks)-1, max(-1, len(ticks)-number-1), -1):
                    prices[j] = (ticks[i][1] + ticks[i][2]) * 0.5
                    j -= 1
        else:
            candles = self._candles.get(tf)
            if candles:
                j = number - 1
                for i in range(len(candles)-1, max(-1, len(candles)-number-1), -1):
                    prices[j] = (candles[i].bid[price_type] + candles[i].ofr[price_type]) * 0.5
                    j -= 1

        return prices

    def last_volumes(self, tf, number):
        volumes = [0] * number

        if tf == 0:
            # get from ticks
            ticks = self._ticks
            if ticks:
                j = number - 1
                for i in range(len(ticks)-1, max(-1, len(ticks)-number-1), -1):
                    volumes[j] = ticks[i][3]
                    j -= 1
        else:
            candles = self._candles.get(tf)
            if candles:
                j = number - 1
                for i in range(len(candles)-1, max(-1, len(candles)-number-1), -1):
                    volumes[j] = candles[i].volume
                    j -= 1

        return volumes

    def check_temporal_coherency(self, tf):
        """
        Check temporal coherency of the candles and return the list of incoherencies.
        """
        issues = []

        for tf, candles in self._candles.items():
            candles = self._candles.get(tf)
            number = len(candles)
            if candles:
                for i in range(len(candles)-1, max(-1, len(candles)-number-1), -1):
                    if candles[i].timestamp - candles[i-1].timestamp != tf:
                        logger.error("Timestamp inconsistency from %s and %s candles at %s delta=(%s)" % (i, i-1, candles[i-1].timestamp, candles[i].timestamp - candles[i-1].timestamp))
                        issues.append(('ohlc', tf, i, i-1, candles[i-1].timestamp, candles[i].timestamp - candles[i-1].timestamp))

        for tf, buy_sells in self._buy_sells.items():
            if buy_sells:
                number = len(buy_sells)
                for i in range(len(buy_sells)-1, max(-1, len(buy_sells)-number-1), -1):
                    if buy_sells[i].timestamp - buy_sells[i-1].timestamp != tf:
                        logger.error("Timestamp inconsistency from %s and %s buy/sell signals at %s delta=(%s)" % (i, i-1, buy_sells[i-1].timestamp, buy_sells[i].timestamp - buy_sells[i-1].timestamp))
                        issues.append(('buysell', tf, i, i-1, candles[i-1].timestamp, buy_sells[i].timestamp - buy_sells[i-1].timestamp))

        ticks = self._ticks
        if ticks:
            number = len(ticks)
            for i in range(len(ticks)-1, max(-1, len(ticks)-number-1), -1):
                if ticks[i][0] - ticks[i-1][0] != tf:                    
                    logger.error("Timestamp inconsistency from %s and %s ticks at %s delta=(%s)" % (i, i-1, ticks[i-1][0], ticks[i][0] - ticks[i-1][0]))
                    issues.append(('tick', 0, i, i-1, ticks[i-1][0], ticks[i][0] - ticks[i-1][0]))
        
        return issues

    #
    # candles OHLC
    #

    def add_candle(self, candle, max_candles=-1):
        """
        Append a new candle.
        @param max_candles Pop candles until num candles > max_candles.

        @todo might split in two method, and same for tick
        """
        if not candle:
            return

        if isinstance(candle, list):
            # array of candles
            tf = candle[0]._timeframe

            if self._candles.get(tf):
                candles = self._candles[tf]

                if len(candles) > 0:
                    for c in candle:
                        # for each candle only add it if more recent or replace a non consolidated
                        if c.timestamp > candles[-1].timestamp:
                            if not candles[-1].ended:
                                # remove the last candle if was not consolidated
                                candles.pop(-1)

                            candles.append(c)

                        elif c.timestamp == candles[-1].timestamp and not candles[-1].ended:
                            # replace the last candle if was not consolidated
                            candles[-1] = c
                else:
                    # initiate array
                    candles.extend(candle)
            else:
                self._candles[tf] = candle

            # keep safe size
            if max_candles > 1:
                candles = self._candles[tf]
                while(len(candles)) > max_candles:
                    candles.pop(0)
        else:
            # single candle
            if self._candles.get(candle._timeframe):
                candles = self._candles[candle._timeframe]

                if len(candles) > 0:
                    # ignore the candle if older than the latest
                    if candle.timestamp > candles[-1].timestamp:
                        if not candles[-1].ended:
                            # replace the last candle if was not consolidated
                            candles[-1] = candle
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

    # def candle(self, tf, ofs):
    #     candles = self._candles.get(tf)
    #     if candles:
    #         if abs(ofs) <= len(candles):
    #             return candles[ofs]

    #     return None

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
                            filler.copy_bid(results[-1])
                            filler.copy_ofr(results[-1])

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
                            filler.copy_bid(results[-1])
                            filler.copy_ofr(results[-1])

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

    def add_tick(self, tick):
        if not tick:
            return

        if isinstance(tick, list):
            ticks = self._ticks

            if len(ticks) > 0:
                for t in tick:
                    # for each tick only add it if more recent
                    if t[0] > ticks[-1][0]:
                        ticks.append(t)
            else:
                # initiate array
                self._ticks = tick
        else:
            if len(self._ticks) > 0:
                # ignore the tick if older than the last one
                if tick[0] > self._ticks[-1][0]:
                    self._ticks.append(tick)
            else:
                self._ticks.append(tick)

    def clear_ticks(self):
        self._ticks.clear()

    def tick(self, ofs):
        if abs(ofs) <= len(self._ticks):
            return self._ticks[ofs]

        return None

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

    def last_ticks(self, number):
        results = [Ticks()] * number

        ticks = self._ticks
        if ticks:
            j = number - 1
            for i in range(len(ticks)-1, max(-1, len(ticks)-number-1), -1):
                results[j] = ticks[i]
                j -= 1

        return results

    #
    # tick-bar
    #

    def add_tickbar(self, tickbar, max_tickbars=-1):
        """
        Append a new tickbar.
        @param max_tickbars Pop tickbars until num tickbars > max_tickbars.

        @todo might split in two method, and same for tick
        """
        if not tickbar:
            return

        if isinstance(tickbar, list):
            # array of tickbar
            if len(self._tickbars) > 0:
                for t in tickbar:
                    # for each tickbar only add it if more recent or replace a non consolidated
                    if t.timestamp > self._tickbars[-1].timestamp:
                        if not self._tickbars[-1].ended:
                            # remove the last tickbar if was not consolidated
                            self._tickbars.pop(-1)

                        self._tickbars.append(t)

                    elif t.timestamp == self._tickbars[-1].timestamp and not self._tickbars[-1].ended:
                        # replace the last tickbar if was not consolidated
                        self._tickbars[-1] = c
            else:
                # initiate array
                self._tickbars = tickbar

            # keep safe size
            if max_tickbars > 1:
                while(len(self._tickbars)) > max_tickbars:
                    self._tickbars.pop(0)
        else:
            # single tickbar
            if len(self._tickbars) > 0:
                # ignore the tickbar if older than the latest
                if tickbar.timestamp > self._tickbars[-1].timestamp:
                    if not self._tickbars[-1].ended:
                        # replace the last tickbar if was not consolidated
                        self._tickbars[-1] = tickbar
                    else:
                        self._tickbars.append(tickbar)

                elif tickbar.timestamp == self._tickbars[-1].timestamp and not self._tickbars[-1].ended:
                    # replace the last tickbar if was not consolidated
                    self._tickbars[-1] = tickbar
            else:
                self._tickbars.append(tickbar)

            # keep safe size
            if max_tickbars > 1:
                while(len(self._tickbars)) > max_tickbars:
                    self._tickbars.pop(0)

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
    # general
    #

    def spread(self):
        """
        Returns the last more recent spread.
        @todo need to update market data
        """
        if self._ticks:
            return self._ticks[-1][2] - self._ticks[-1][1]
        else:
            candles = None
            if self._candles.get(Instrument.TF_SEC):
                candles = self._candles[Instrument.TF_SEC]
            elif self._candles.get(60):
                candles = self._candles[Instrument.TF_MIN]

            if candles:
                return candles[-1].spread

        # or another way to query it
        return 0.0

    def bid(self, tf=None):
        """
        Returns the last more recent bid (close) price.
        @param tf At desired timeframe or at the most precise found
        """
        if self._ticks:
            return self._ticks[-1][1]
        else:
            candles = None
            if tf and self._candles.get(tf):
                candles = self._candles[tf]
            elif self._candles.get(Instrument.TF_SEC):
                candles = self._candles[Instrument.TF_SEC]
            elif self._candles.get(Instrument.TF_MIN):
                candles = self._candles[Instrument.TF_MIN]

            if candles:
                return candles[-1].bid_close
        
        return None

    def ofr(self, tf=None):
        """
        Returns the last more recent offer (close) price.
        @param tf At desired timeframe or at the most precise found
        """
        if self._ticks:
            return self._ticks[-1][2]
        else:
            candles = None
            if tf and self._candles.get(tf):
                candles = self._candles[tf]
            elif self._candles.get(Instrument.TF_SEC):
                candles = self._candles[Instrument.TF_SEC]
            elif self._candles.get(Instrument.TF_MIN):
                candles = self._candles[Instrument.TF_MIN]

            if candles:
                return candles[-1].ofr_close

        return None

    def price(self, tf=None):
        """
        Returns the last more recent mid (close) price.
        @param tf At desired timeframe or at the most precise found
        """
        if self._ticks:
            return (self._ticks[-1][1] + self._ticks[-1][2]) * 0.5
        else:
            candles = None
            if tf and self._candles.get(tf):
                candles = self._candles[tf]
            elif self._candles.get(Instrument.TF_SEC):
                candles = self._candles[Instrument.TF_SEC]
            elif self._candles.get(Instrument.TF_MIN):
                candles = self._candles[Instrument.TF_MIN]

            if candles:
                return candles[-1].close

        return None

    def num_samples(self, tf):
        if tf == Instrument.TF_TICK:
            return len(self._ticks)

        if self._candles.get(tf):
            return len(self._candles[tf])

        return 0

    def height(self, tf, index):
        """
        Returns the height of the last candle for a specified timeframe.
        @param tf At desired timeframe
        """
        candles = self._candles.get(tf)
        if candles:
            return candles[index].height

        return 0.0

    def purge_last(self, tf, n):
        """
        Clean candle or tick for a particular timeframe, and keep only the n last entries.
        """
        if tf > 0:
            candles = self._candles.get(tf)
            if candles and len(candles) > n:
                self._candles[tf] = candles[-n:]
        elif self._ticks and len(self._ticks) > n:
            self._ticks = self._ticks[-n:]

    def purge(self, older_than=60*60*24, n_last=100):
        """
        Purge ticks and candles that are older than predefined conditions or n keep only n last candles, to avoid memory issues.
        """
        now = time.time()

        # on ticks
        m = 0
        for n, tick in enumerate(self._ticks):
            if now - tick[0] < older_than:
                m = n
                break

        if m > 0:
            # keep the m+1 recents
            self._ticks = self._ticks[m:]

        # per tf of candles
        for tf, candles in self._candles.items():
            m = 0

            for n, candle in enumerate(candles):
                if now - candle.timestamp < older_than:
                    m = n
                    break

            if m > 0:
                # keep the m+1 recents
                self._candles[tf] = candles[m:]

        # per tf of buy/sell signals
        for tf, buy_sells in self._buy_sells.items():
            m = 0

            for n, buy_sell in enumerate(buy_sells):
                if now - buy_sell.timestamp < older_than:
                    m = n
                    break

            if m > 0:
                # keep the m+1 recents
                self._buy_sells[tf] = buy_sells[m:]             

    def from_to_prices(self, tf, price_type, from_ts=0, to_ts=-1):
        prices = [0] * number

        candles = self._candles.get(tf)
        if candles:
            if from_ts <= 0:
                # from the older
                from_ts = candles[0].timestamp

            if to_ts <= 0:
                # to the latest
                to_ts = candles[-1].timestamp

            j = 0
            for candle in candles:
                if candle.timestamp < from_ts:
                    continue
                elif candle.timestamp > to_ts:
                    break

                prices[j] = (candle.bid[price_type] + candle.ofr[price_type]) * 0.5
                j += 1

        return prices

    def from_to_volumes(self, tf, from_ts=0, to_ts=-1):
        volumes = [0] * number

        if tf == 0:
            # get volumes from ticks
            ticks = self._ticks.get(tf)
            if ticks:
                if from_ts <= 0:
                    # from the older
                    from_ts = ticks[0][0]

                if to_ts <= 0:
                    # to the latest
                    to_ts = ticks[-1][0]

                j = 0
                for tick in ticks:
                    if tick[0] < from_ts:
                        continue
                    elif tick[0] > to_ts:
                        break

                    volumes[j] = tick[3]
                    j += 1
        else:
            candles = self._candles.get(tf)
            if candles:
                if from_ts <= 0:
                    # from the older
                    from_ts = candles[0].timestamp

                if to_ts <= 0:
                    # to the latest
                    to_ts = candles[-1].timestamp

                j = 0
                for candle in candles:
                    if candle.timestamp < from_ts:
                        continue
                    elif candle.timestamp > to_ts:
                        break

                    volumes[j] = candle.volume
                    j += 1

        return volumes

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

    def ack_timeframe(self, timeframe):
        if timeframe in self._wanted:
            self._wanted.remove(timeframe)
            return True

        return False

    def open_exec_price(self, direction):
        """
        Return the execution price if an order open a position.
        It depend of the direction of the order and the market bid/ofr prices.
        If position is long, then returns the market ofr price.
        If position is short, then returns the market bid price.
        """
        if direction > 0:
            return self._market_ofr
        elif direction < 0:
            return self._market_bid
        else:
            return self._market_ofr

    def close_exec_price(self, direction):
        """
        Return the execution price if an order/position is closing.
        It depend of the direction of the order and the market bid/ofr prices.
        If position is long, then returns the market bid price.
        If position is short, then returns the market ofr price.
        """
        if direction > 0:
            return self._market_bid
        elif direction < 0:
            return self._market_ofr
        else:
            return self._market_bid

    def trade_quantity_mode_to_str(self):
        if self._trade_quantity_mode == Instrument.TRADE_QUANTITY_DEFAULT:
            return "default"
        elif self._trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            return "quote-to-base"
        else:
            return "default"

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

    def format_price(self, price):
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        precision = self._price_limits[3] or 8
        tick_size = self._price_limits[2] or 0.00000001

        adjusted_price = truncate(round(price / tick_size) * tick_size, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove tailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def adjust_quantity(self, quantity, min_is_zero=True):
        """
        From quantity return the floor tradable quantity according to min, max and rounded to step size.
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

        if self.max_size > 0.0 and quantity > self.max_size:
            return self.max_size

        if self.step_size > 0:
            precision = self._size_limits[3]
            # return max(round(self.step_size * round(quantity / self.step_size), precision), self.min_size)
            return max(round(self.step_size * math.floor(quantity / self.step_size), precision), self.min_size)

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
    def basetime(tf, timestamp):
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

        return 0
