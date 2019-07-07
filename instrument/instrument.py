# @date 2018-08-27
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Instrument symbol

from datetime import datetime, timedelta
from common.utils import UTC, timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy.instrument')


class Candle(object):
    """
    Candle for an instrument.
    @note Ofr is a synonym for ask.

    @note 11 floats + 1 bool
    """

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
        return "%s bid %s/%s/%s/%s ofr %s/%s/%s/%s" % (
            timeframe_to_str(self._timeframe),
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
    name come from the broker usage name (could use the epic or market-id if none other).
    symbol is a common usual name (ex: EURUSD, BTCUSD).
    market-id is a the unique broker identifier.
    alias is a only a secondary or display name.
    base_exchance_rate is the rate of the quote symbol over its related account currency.

    @note ofr is a synonym for ask.
    @todo set 24h vol, fee, commission from market info data signal
    """

    TF_TICK = 0
    TF_T = TF_TICK
    TF_SEC = 1
    TF_1S = TF_SEC
    TF_10SEC = 10
    TF_10S = TF_10SEC
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
    CONTRACT_FUTUR = 2

    TYPE_UNKNOWN = 0
    TYPE_CURRENCY = 1     # FOREX
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

    def __init__(self, name, symbol, market_id, alias=None):
        self._watchers = {}
        self._name =  name
        self._symbol = symbol
        self._market_id = market_id
        self._alias = alias
        self._base_exchange_rate = 1.0
        self._tradeable = True

        self._currency = "USD"
        self._trade_quantity = 0.0
        self._leverage = 1.0  # 1 / margin_factor

        self._market_bid = 0.0
        self._market_ofr = 0.0
        self._update_time = 0.0

        self._vol24h = 0.0
        self._vol24h_quote = 0.0

        self._fees = ((0.0, 0.0), (0.0, 0.0))  # ((maker fee, taker fee), (maker commission, taker commission))

        self._ticks = []      # list of tuple(timestamp, bid, ofr, volume)
        self._candles = {}    # list per timeframe
        self._buy_sells = {}  # list per timeframe

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
    def update_time(self):
        return self._update_time

    @update_time.setter
    def update_time(self, update_time):
        self._update_time = update_time

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

    @property
    def base_exchange_rate(self):
        """
        Current base exchange rate from the quote to the account currency.
        It is used to compute the profit/loss in account currency unit.
        But in backtesting it is possible that we don't have this information,
        and this ratio is non static.
        """
        return self._base_exchange_rate

    @base_exchange_rate.setter
    def base_exchange_rate(self, v):
        self._base_exchange_rate = v

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def trader_quantity(self):
        return self._trader_quantity

    @trader_quantity.setter
    def trader_quantity(self, quantity):
        self._trader_quantity = quantity

    @property
    def currency(self):
        return self._currency

    @currency.setter
    def currency(self, currency):
        self._currency = currency
    
    @property
    def leverage(self):
        """
        Account and instrument related leverage.
        """
        return self._leverage
    
    @leverage.setter
    def leverage(self, leverage):
        self._leverage = leverage

    #
    # ticks and candles
    #

    def tick(self, ofs):
        if abs(ofs) <= len(self._ticks):
            return self._ticks[ofs]

        return None

    # def candle(self, tf, ofs):
    #     candles = self._candles.get(tf)
    #     if candles:
    #         if abs(ofs) <= len(candles):
    #             return candles[ofs]

    #     return None

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

                        elif c.timestamp == candles[-1].timestamp:  # and not candles[-1].ended:
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

                    elif candle.timestamp == candles[-1].timestamp:  # and not candles[-1].ended:
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

    #
    # helpers
    #

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

    #
    # fee/commission
    #

    def set_fees(self, maker, taker):
        self._fees[Instrument.MAKER][0] = maker
        self._fees[Instrument.TAKER][0] = taker

    def set_commissions(self, maker, taker):
        self._fees[Instrument.MAKER][1] = maker
        self._fees[Instrument.TAKER][1] = taker

    def maker_fee(self):
        return self._fees[Instrument.MAKER][0]

    def taker_fee(self):
        return self._fees[Instrument.MAKER][0]

    def maker_commission(self):
        return self._fees[Instrument.TAKER][1]

    def taker_commission(self):
        return self._fees[Instrument.TAKER][1]

    #
    # static
    #

    @staticmethod
    def basetime(tf, timestamp):
        if tf < 7*24*60*60:
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
