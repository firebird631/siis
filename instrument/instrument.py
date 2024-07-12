# @date 2018-08-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Instrument symbol

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Union, Optional, Tuple, Dict

if TYPE_CHECKING:
    from watcher.watcher import Watcher
    from .rangebar import RangeBar

import math

from dataclasses import dataclass
from datetime import datetime, timedelta

from common.utils import UTC, timeframe_to_str, truncate, decimal_place

import logging
logger = logging.getLogger('siis.instrument.instrument')
error_logger = logging.getLogger('siis.error.instrument.instrument')

TickType = Tuple[float, float, float, float, float, float]
OHLCType = Tuple[float, float, float, float, float, float, float]


class Candle(object):
    """
    Candle for an instrument with OHLC, volume, timestamp and timeframe.
    Ended is true only when the candle is closed (consolidated). It means the current is False.
    The spread field could be used when backtesting using candle data in place of tick/trade data.
    It contains the average spread during the timeframe of the candle.

    @note 8 floats + 1 bool
    """

    __slots__ = '_timestamp', '_timeframe', '_open', '_high', '_low', '_close', '_spread', '_volume', '_ended'

    def __init__(self, timestamp: float, timeframe: float):
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
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def timeframe(self) -> float:
        return self._timeframe

    @property
    def open(self) -> float:
        return self._open

    @property
    def high(self) -> float:
        return self._high

    @property
    def low(self) -> float:
        return self._low

    @property
    def close(self) -> float:
        return self._close

    @property
    def spread(self) -> float:
        return self._spread

    @property
    def ended(self) -> bool:
        return self._ended

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def height(self) -> float:
        return self.high - self.low
    
    def set(self, last: float):
        self._open = last
        self._high = last
        self._low = last
        self._close = last

    def set_ohlc(self, o: float, h: float, l: float, c: float):
        self._open = o
        self._high = h
        self._low = l
        self._close = c

    def set_volume(self, ltv: float):
        self._volume = ltv

    def add_volume(self, ltv: float):
        self._volume += ltv

    def set_ohlc_s_v(self, o: float, h: float, l: float, c: float, s: float, v: float):
        self._open = o
        self._high = h
        self._low = l
        self._close = c
        self._spread = s
        self._volume = v

    def set_spread(self, spread: float):
        self._spread = spread

    def set_consolidated(self, cons: bool):
        self._ended = cons

    def copy(self, dup: Candle):
        self._open = dup._open
        self._high = dup._high
        self._low = dup._low
        self._close = dup._close
        self._spread = dup._spread

    def __repr__(self) -> str:
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

    _strategy: Union[str, None]

    def __init__(self, timestamp: float, timeframe: float):
        self._timestamp = timestamp
        self._timeframe = timeframe
        self._strategy = None
        self._order_type = BuySellSignal.ORDER_ENTRY
        self._direction = None
        self._exec_price = 0.0
        self._params = {}

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def timeframe(self) -> float:
        return self._timeframe

    @property
    def strategy(self) -> str:
        return self._strategy
    
    @property
    def direction(self) -> int:
        return self._direction
    
    @property
    def order_type(self) -> int:
        return self._order_type

    @property
    def exec_price(self) -> float:
        return self._exec_price

    def set_data(self, strategy: str, order_type: int, direction: int, exec_price: float, timeframe: float):
        self._strategy = strategy
        self._order_type = order_type
        self._direction = direction
        self._exec_price = exec_price
        self._timeframe = timeframe

    @property
    def params(self) -> dict:
        return self._params
    
    @params.setter
    def params(self, params: dict):
        self._params = params


@dataclass
class TradingSession:
    """
    Instrument trading session dataclass.
    Times are related to the configured instrument timezone.
    """

    day_of_week: int = 0
    from_time: float = 0.0
    to_time: float = 0.0

    def to_dict(self):
        return {
            'day-of-week': self.day_of_week,
            'from-time': self.from_time,
            'to-time': self.to_time
        }


class Instrument(object):
    """
    Instrument is the strategy side of the market model.
    Its a denormalized model because it duplicates some members used during strategy processing,
    to avoid dealing with the trader thread/process.

    @member symbol str Common usual name (ex: EURUSD, BTCUSD).
    @member market_id str Unique broker identifier.
    @member alias str A secondary or display name.
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
    TF_QUARTER = 60*60*24*90
    TF_YEAR = 60*60*24*365

    PRICE_OPEN = 0
    PRICE_HIGH = 1
    PRICE_LOW = 2
    PRICE_CLOSE = 3

    CONTRACT_SPOT = 0
    CONTRACT_CFD = 1
    CONTRACT_FUTURE = 2
    CONTRACT_OPTION = 3
    CONTRACT_WARRANT = 4
    CONTRACT_TURBO = 5

    TYPE_UNKNOWN = 0
    TYPE_CURRENCY = 1
    TYPE_COMMODITY = 2
    TYPE_INDICE = 3
    TYPE_STOCK = 4
    TYPE_RATE = 5
    TYPE_SECTOR = 6
    TYPE_CRYPTO = 7

    UNIT_AMOUNT = 0
    UNIT_CONTRACTS = 1
    UNIT_SHARES = 2
    UNIT_INVERSE = 3

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

    __slots__ = '_watchers', '_market_id', '_symbol', '_alias', '_tradeable', \
                '_market_type', '_contract_type', '_unit_type', \
                '_trade_quantity', '_trade_quantity_mode', '_leverage', \
                '_market_bid', '_market_ask', '_last_update_time', \
                '_vol24h_base', '_vol24h_quote', '_fees', \
                '_size_limits', '_price_limits', '_notional_limits', '_settlement_precision', \
                '_ticks', '_range_bars', '_candles', '_buy_sells', \
                '_needed_timeframes', '_needed_range_bars', \
                '_base', '_quote', '_settlement', '_trade', '_orders', \
                '_hedging', '_expiry', '_value_per_pip', '_one_pip_means', '_lot_size', '_contract_size',  \
                '_timezone', '_session_offset', '_trading_sessions'

    _watchers: Dict[int, Watcher]
    _trading_sessions: List[TradingSession]

    def __init__(self, market_id: str, symbol: str, alias: Optional[str] = None):
        self._watchers = {}
        self._market_id = market_id
        self._symbol = symbol
        self._alias = alias
        self._tradeable = True
        self._expiry = "-"

        self._market_type = Instrument.TYPE_UNKNOWN
        self._unit_type = Instrument.UNIT_CONTRACTS
        self._contract_type = Instrument.CONTRACT_SPOT

        self._base = ""
        self._quote = ""
        self._settlement = ""

        self._trade = 0
        self._orders = 0

        self._hedging = False

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
        self._settlement_precision = 8

        self._ticks = []      # list of tuple(timestamp, bid, ask, last, volume, direction)
        self._candles = {}    # list per timeframe
        self._buy_sells = {}  # list per timeframe
        self._range_bars = {}   # list of TickBar per size

        self._one_pip_means = 1.0
        self._value_per_pip = 1.0
        self._lot_size = 0.0
        self._contract_size = 1.0

        # evening session from 00h00m00s000ms to 23h59m59s999ms in UTC, tuple with float time offset and time duration
        self._timezone = 0.0         # market timezone UTC+N
        self._session_offset = 0.0   # day session offset from 00:00 in seconds

        # allowed trading session (empty mean anytime) else must be explicit. each session is a TradingSession model.
        self._trading_sessions = []

        self._needed_timeframes = []  # list of needed timeframe before be ready (it is only for initialization)
        self._needed_range_bars = []  # list of needed range-bar before be ready (it is only for initialization)

    def add_watcher(self, watcher_type: int, watcher: Watcher):
        if watcher:
            self._watchers[watcher_type] = watcher

    def watcher(self, watcher_type: int) -> Union[Watcher, None]:
        return self._watchers.get(watcher_type)

    def watchers(self):
        return self._watchers

    @property
    def symbol(self) -> str:
        return self._symbol

    @symbol.setter
    def symbol(self, symbol: str):
        self._symbol = symbol

    @property
    def alias(self) -> str:
        return self._alias

    @alias.setter
    def alias(self, alias: str):
        self._alias = alias

    @property
    def market_id(self) -> str:
        return self._market_id

    @property
    def tradeable(self) -> bool:
        return self._tradeable

    @tradeable.setter
    def tradeable(self, status: bool):
        self._tradeable = status

    @property
    def market_type(self) -> int:
        return self._market_type

    @market_type.setter
    def market_type(self, market_type: int):
        self._market_type = market_type

    @property
    def unit_type(self) -> int:
        return self._unit_type

    @unit_type.setter
    def unit_type(self, unit_type: int):
        self._unit_type = unit_type

    @property
    def contract_type(self) -> int:
        return self._contract_type

    @contract_type.setter
    def contract_type(self, contract_type: int):
        self._contract_type = contract_type

    #
    # instrument trade type
    #

    @property
    def trade(self) -> int:
        return self._trade

    @trade.setter
    def trade(self, trade: int):
        self._trade = trade

    @property
    def has_spot(self) -> bool:
        return self._trade & Instrument.TRADE_SPOT == Instrument.TRADE_SPOT

    @property
    def has_margin(self) -> bool:
        return self._trade & Instrument.TRADE_MARGIN == Instrument.TRADE_MARGIN

    @property
    def indivisible_position(self) -> bool:
        return self._trade & Instrument.TRADE_IND_MARGIN == Instrument.TRADE_IND_MARGIN

    @property
    def fifo_position(self) -> bool:
        return self._trade & Instrument.TRADE_FIFO == Instrument.TRADE_FIFO

    @property
    def has_position(self) -> bool:
        return self._trade & Instrument.TRADE_POSITION == Instrument.TRADE_POSITION

    @property
    def orders(self) -> int:
        return self._orders

    @orders.setter
    def orders(self, flags: int):
        self._orders = flags

    def set_quote(self, symbol: str):
        self._quote = symbol

    @property
    def quote(self) -> str:
        return self._quote

    def set_base(self, symbol: str):
        self._base = symbol

    @property
    def base(self) -> str:
        return self._base

    @property
    def settlement(self) -> str:
        return self._settlement

    def set_settlement(self, settlement: str):
        self._settlement = settlement

    @property
    def hedging(self) -> bool:
        return self._hedging
    
    @hedging.setter
    def hedging(self, hedging: bool):
        self._hedging = hedging

    @property
    def expiry(self) -> str:
        return self._expiry
    
    @expiry.setter
    def expiry(self, expiry: str):
        self._expiry = expiry

    #
    # options
    #

    @property
    def trade_quantity(self) -> float:
        return self._trade_quantity

    @trade_quantity.setter
    def trade_quantity(self, quantity: float):
        if quantity > 0.0:
            self._trade_quantity = quantity

    @property
    def trade_quantity_mode(self) -> int:
        return self._trade_quantity_mode

    @trade_quantity_mode.setter
    def trade_quantity_mode(self, trade_quantity_mode: int):
        self._trade_quantity_mode = trade_quantity_mode

    def trade_quantity_mode_to_str(self) -> str:
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
    def timezone(self) -> float:
        return self._timezone

    @property
    def session_offset(self) -> float:
        return self._session_offset

    def has_trading_sessions(self) -> bool:
        return len(self._trading_sessions) > 0

    @property
    def trading_sessions(self) -> List[TradingSession]:
        """
        @return: Empty list where each tuple is three values for day of week, hour of day, minute of day
        """
        return self._trading_sessions

    #
    # price/volume
    #

    @property
    def market_bid(self) -> float:
        return self._market_bid

    @market_bid.setter
    def market_bid(self, bid: float):
        self._market_bid = bid

    @property
    def market_ask(self) -> float:
        return self._market_ask

    @market_ask.setter
    def market_ask(self, ask: float):
        self._market_ask = ask

    @property
    def market_price(self) -> float:
        return (self._market_bid + self._market_ask) * 0.5

    @property
    def market_spread(self) -> float:
        return self._market_ask - self._market_bid

    @property
    def last_update_time(self) -> float:
        return self._last_update_time

    @last_update_time.setter
    def last_update_time(self, last_update_time: float):
        self._last_update_time = last_update_time

    @property
    def vol24h_base(self) -> float:
        return self._vol24h_base
    
    @property
    def vol24h_quote(self) -> float:
        return self._vol24h_quote
    
    @vol24h_base.setter
    def vol24h_base(self, v: float):
        self._vol24h_base = v

    @vol24h_quote.setter
    def vol24h_quote(self, v: float):
        self._vol24h_quote = v
 
    #
    # limits
    #

    @property
    def size_limits(self) -> Tuple[float, float, float, float]:
        return self._size_limits

    @property
    def min_size(self) -> float:
        return self._size_limits[0]

    @property
    def max_size(self) -> float:
        return self._size_limits[1]

    @property
    def step_size(self) -> float:
        return self._size_limits[2]

    @property
    def size_precision(self) -> float:
        return self._size_limits[3]

    @property
    def notional_limits(self) -> Tuple[float, float, float, float]:
        return self._notional_limits

    @property
    def min_notional(self) -> float:
        return self._notional_limits[0]

    @property
    def max_notional(self) -> float:
        return self._notional_limits[1]

    @property
    def step_notional(self) -> float:
        return self._notional_limits[2]

    @property
    def notional_precision(self) -> float:
        return self._notional_limits[3]

    @property
    def price_limits(self) -> Tuple[float, float, float, float]:
        return self._price_limits

    @property
    def min_price(self) -> float:
        return self._price_limits[0]

    @property
    def max_price(self) -> float:
        return self._price_limits[1]

    @property
    def step_price(self) -> float:
        return self._price_limits[2]

    @property
    def settlement_precision(self) -> float:
        return self._settlement_precision

    @property
    def tick_price(self) -> float:
        return self._price_limits[2]

    @property
    def price_precision(self) -> float:
        return self._price_limits[3]

    @property
    def value_per_pip(self) -> float:
        return self._value_per_pip

    @property
    def one_pip_means(self) -> float:
        return self._one_pip_means

    @property
    def lot_size(self) -> float:
        return self._lot_size

    @property
    def contract_size(self) -> float:
        return self._contract_size

    @property
    def leverage(self) -> float:
        """
        Account and instrument related leverage.
        """
        return self._leverage
    
    @leverage.setter
    def leverage(self, leverage: float):
        self._leverage = leverage

    def set_size_limits(self, min_size: float, max_size: float, step_size: float):
        size_precision = max(0, decimal_place(step_size) if step_size > 0 else 0)
        self._size_limits = (min_size, max_size, step_size, size_precision)

    def set_notional_limits(self, min_notional: float, max_notional: float, step_notional: float):
        notional_precision = max(0, decimal_place(step_notional) if step_notional > 0 else 0)
        self._notional_limits = (min_notional, max_notional, step_notional, notional_precision)

    def set_price_limits(self, min_price: float, max_price: float, step_price: float):
        price_precision = max(0, decimal_place(step_price) if step_price > 0 else 0)
        self._price_limits = (min_price, max_price, step_price, price_precision)

    def set_settlement_precision(self, settlement_precision: float):
        self._settlement_precision = settlement_precision

    @value_per_pip.setter
    def value_per_pip(self, value_per_pip: float):
        self._value_per_pip = value_per_pip

    @one_pip_means.setter
    def one_pip_means(self, one_pip_means: float):
        self._one_pip_means = one_pip_means

    @lot_size.setter
    def lot_size(self, lot_size: float):
        self._lot_size = lot_size

    @contract_size.setter
    def contract_size(self, contract_size: float):
        self._contract_size = contract_size

    #
    # ticks or candles
    #

    def check_temporal_coherency(self, tf: float) -> List[Tuple[str, float, int, int, float, float]]:
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

    def add_candles(self, candles_list: List[Candle], max_candles: int = -1):
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

    def add_candle(self, candle: Candle, max_candles: int = -1):
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

    def last_candles(self, tf: float, number: int) -> List[Candle]:
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

    def candle(self, tf: float) -> Union[Candle, None]:
        """
        Return as possible the last candle.
        """
        candles = self._candles.get(tf)
        if candles:
            return candles[-1]

        return None

    def candles(self, tf: float) -> Union[List[Candle], None]:
        """
        Returns candles list for a specific timeframe.
        @param tf Timeframe
        """
        return self._candles.get(tf)

    def reduce_candles(self, timeframe: float, max_candles: int):
        """
        Reduce the number of candle to max_candles.
        """
        if not max_candles or not timeframe:
            return

        if self._candles.get(timeframe):
            candles = self._candles[timeframe][-max_candles:]

    def last_ended_timestamp(self, tf: float) -> float:
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

    def candles_from(self, tf: float, from_ts: float) -> List[Candle]:
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

    def candles_after(self, tf: float, after_ts: float) -> List[Candle]:
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

    def add_ticks(self, ticks_list: List[TickType]):
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

    def add_tick(self, tick: TickType):
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

    def ticks(self) -> List[TickType]:
        return self._ticks

    def detach_ticks(self) -> List[TickType]:
        """
        Detach the array of tick and set up a new empty for the instrument.
        """
        ticks = self._ticks
        self._ticks = []
        return ticks

    def ticks_after(self, after_ts: float) -> List[TickType]:
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
    # range-bar
    #
    
    def add_range_bars(self, size: int, range_bars_list: List[RangeBar], max_range_bars: int = -1):
        """
        Append an array of new range-bars.
        @param size: Size of the range-bar
        @param range_bars_list
        @param max_range_bars Pop range-bars until num range_bars > max_range_bars.
        """
        if not range_bars_list:
            return

        if self._range_bars.get(size):
            range_bars = self._range_bars[size]

            # array of tickbar
            if len(range_bars) > 0:
                for range_bar in range_bars_list:
                    # for each tickbar only add it if more recent or replace a non consolidated
                    if range_bar.timestamp > range_bars[-1].timestamp:
                        if not range_bars[-1].ended:
                            # remove the last range-bar if was not consolidated
                            range_bars.pop(-1)
                            # tickbars[-1]._ended = True

                        range_bars.append(range_bar)

                    elif range_bar.timestamp == range_bars[-1].timestamp and not range_bars[-1].ended:
                        # replace the last range-bar if was not consolidated
                        range_bars[-1] = range_bar
            else:
                # initiate array
                self._range_bars[size] = range_bars_list
        else:
            # initiate array
            self._range_bars[size] = range_bars_list

        # keep safe size
        if max_range_bars > 1:
            range_bars = self._range_bars[size]
            if range_bars:
                while(len(range_bars)) > max_range_bars:
                    range_bars.pop(0)

    def add_range_bar(self, size: int, range_bar: RangeBar, max_range_bars: int = -1):
        """
        Append a new range-bar.
        @param size: Size of the range-bar
        @param range_bar
        @param max_range_bars Pop tickbars until num range_bars > max_range_bars.
        """
        if not range_bar:
            return

        if self._range_bars.get(size):
            range_bars = self._range_bars[size]

            # single tickbar
            if len(range_bars) > 0:
                # ignore the tickbar if older than the latest
                if range_bar.timestamp > range_bars[-1].timestamp:
                    if not range_bars[-1].ended:
                        # replace the last tickbar if was not consolidated
                        range_bars[-1] = range_bar
                    else:
                        range_bars.append(range_bar)

                elif range_bar.timestamp == range_bars[-1].timestamp and not range_bars[-1].ended:
                    # replace the last tickbar if was not consolidated
                    range_bars[-1] = range_bar
            else:
                range_bars.append(range_bar)
        else:
            self._range_bars[size] = [range_bar]

        # keep safe size
        if max_range_bars > 1:
            range_bars = self._range_bars[size]
            if range_bars:
                while(len(range_bars)) > max_range_bars:
                    range_bars.pop(0)

            # if size == 4:
            #     logger.debug("%s %s" % (range_bars[-2], range_bars[-1]))

    def range_bar(self, size: int) -> Optional[RangeBar]:
        """
        Return as possible the last range-bar.
        """
        range_bars = self._range_bars.get(size, [])

        if range_bars:
            return range_bars[-1]

        return None

    def range_bars(self, size: int) -> List[RangeBar]:
        """
        Returns range-bars list.
        """
        return self._range_bars.get(size)

    #
    # sync
    #

    def ready(self) -> bool:
        """
        Return true when ready to process.
        """
        return not self._needed_timeframes and not self._needed_range_bars

    def need_timeframe(self, timeframe: float):
        """
        Add a required candles for a specific timeframe.
        """
        self._needed_timeframes.append(timeframe)

    def need_range_bar(self, size: float):
        """
        Add a required candles for a specific range-bar size.
        """
        self._needed_range_bars.append(size)

    def is_need_timeframe(self, timeframe: float) -> bool:
        """
        Check if a timeframe is needed.
        """
        return timeframe in self._needed_timeframes

    def is_need_range_bar(self, size: int) -> bool:
        """
        Check if a certain size of range-bar is needed.
        """
        return size in self._needed_range_bars

    def ack_timeframe(self, timeframe: float) -> bool:
        """
        Clear wanted timeframe status and returns true if it was wanted.
        """
        if timeframe in self._needed_timeframes:
            self._needed_timeframes.remove(timeframe)
            return True

        return False

    def ack_range_bar(self, size: int) -> bool:
        """
        Clear wanted range-bar status and returns true if it was wanted.
        """
        if size in self._needed_range_bars:
            self._needed_range_bars.remove(size)
            return True

        return False

    def open_exec_price(self, direction: int, maker: bool = False) -> float:
        """
        Return the execution price if an order open a position.
        It depends on the direction of the order and the market bid/ask prices.
        If position is long, then returns the market ask price.
        If position is short, then returns the market bid price.
        """
        if direction > 0:
            return self._market_ask if not maker else self._market_bid
        elif direction < 0:
            return self._market_bid if not maker else self._market_ask
        else:
            return (self._market_ask + self._market_bid) * 0.5

    def close_exec_price(self, direction: int, maker: bool = False) -> float:
        """
        Return the execution price if an order/position is closing.
        It depends on the direction of the order and the market bid/ask prices.
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

    def adjust_price(self, price: float) -> float:
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        precision = self._price_limits[3] or 8
        tick_size = self._price_limits[2] or 0.00000001

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / tick_size) * tick_size, precision)

    def adjust_quote(self, quote: float) -> float:
        """
        Format the quote according to the precision.
        """
        if quote is None:
            quote = 0.0

        precision = self._notional_limits[3] or 2
        tick_size = self._notional_limits[2] or 0.01

        # adjusted quote price at precision and by step of pip meaning
        return truncate(round(quote / tick_size) * tick_size, precision)

    def adjust_settlement(self, settlement: float) -> float:
        """
        Format the quote according to the precision.
        """
        if settlement is None:
            settlement = 0.0

        if not self._settlement:
            return self.adjust_quote(settlement)

        precision = self._settlement_precision or 8
        tick_size = pow(10, -precision)

        # adjusted quote price at precision and by step of pip meaning
        return truncate(round(settlement / tick_size) * tick_size, precision)

    def format_price(self, price: float) -> str:
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

    def format_quote(self, quote: float) -> str:
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

    def format_settlement(self, settlement: float) -> str:
        """
        Format the settlement according to the precision.
        If the settlement symbol is not defined the quote information are used.
        """
        if settlement is None or math.isnan(settlement):
            settlement = 0.0

        if not self._settlement:
            return self.format_quote(settlement)

        precision = self._settlement_precision or 8
        tick_size = pow(10, -precision)

        adjusted_settlement = truncate(round(settlement / tick_size) * tick_size, precision)
        formatted_settlement = "{:0.0{}f}".format(adjusted_settlement, precision)

        # remove trailing 0s and dot
        if '.' in formatted_settlement:
            formatted_settlement = formatted_settlement.rstrip('0').rstrip('.')

        return formatted_settlement

    def adjust_quantity(self, quantity: float, min_is_zero: bool = True) -> float:
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

    def format_quantity(self, quantity: float) -> str:
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

    def set_fees(self, maker: float, taker: float):
        self._fees[Instrument.MAKER][0] = maker
        self._fees[Instrument.TAKER][0] = taker

    def set_commissions(self, maker: float, taker: float):
        self._fees[Instrument.MAKER][1] = maker
        self._fees[Instrument.TAKER][1] = taker

    @property
    def maker_fee(self) -> float:
        return self._fees[Instrument.MAKER][0]

    @property
    def taker_fee(self) -> float:
        return self._fees[Instrument.TAKER][0]

    @property
    def maker_commission(self) -> float:
        return self._fees[Instrument.MAKER][1]

    @property
    def taker_commission(self) -> float:
        return self._fees[Instrument.TAKER][1]

    def effective_cost(self, quantity: float, price: float) -> float:
        """
        Effective cost, not using the margin factor, for a quantity at specific price.
        Return a value that can be in quote or settlement currency (depends on how is defined contract size) or in
        unit of base in case of contracts
        """
        if quantity <= 0.0 or price <= 0.0:
            return 0.0

        if self._unit_type == Instrument.UNIT_AMOUNT:
            return quantity * (self._lot_size * self._contract_size) * price
        elif self._unit_type == Instrument.UNIT_CONTRACTS:
            return quantity * (self._lot_size * self._contract_size / self._value_per_pip * price)
        elif self._unit_type == Instrument.UNIT_SHARES:
            return quantity * price
        elif self._unit_type == Instrument.UNIT_INVERSE:
            return quantity * (self._lot_size * self._contract_size) / price
        else:
            return quantity * (self._lot_size * self._contract_size) * price

    def compute_pnl(self, quantity: float, direction: int, initial_price: float, last_price: float) -> float:
        """
        Compute the profit or loss according to the market unit type.
        """
        if quantity <= 0.0 or initial_price <= 0.0 or last_price <= 0.0:
            return 0.0

        if self._unit_type == Instrument.UNIT_AMOUNT:
            return quantity * (self._lot_size * self._contract_size) * direction * (last_price - initial_price)
        elif self._unit_type == Instrument.UNIT_CONTRACTS:
            return quantity * (self._lot_size * self._contract_size / self._value_per_pip * direction * (last_price - initial_price))
        elif self._unit_type == Instrument.UNIT_SHARES:
            return quantity * (last_price - initial_price) * direction
        elif self._unit_type == Instrument.UNIT_INVERSE:
            return quantity * (self._lot_size * self._contract_size) * direction * (1.0 / initial_price - 1.0 / last_price)
        else:
            return quantity * (self._lot_size * self._contract_size) * direction * (last_price - initial_price)

    #
    # configuration
    #

    def loads_session(self, data: Dict[str, Union[str, float, int]]):
        """
        Load trading sessions details from a dict.
        @param data: session field (dict)
        """

        if 'timezone' in data:
            self._timezone = float(data['timezone'])

        if 'offset' in data:
            session_offset = Instrument.duration_from_str(data['offset'])
            if session_offset is None:
                error_logger.error("Trading session offset invalid format")
            else:
                self._session_offset = session_offset

        if 'trading' in data:
            if type(data['trading']) is str:
                trading_sessions = self.sessions_from_str(data['trading'])
                if trading_sessions is None:
                    error_logger.error("Trading sessions invalid format")
                else:
                    self._trading_sessions = trading_sessions

            elif type(data['trading']) in (list, tuple):
                for m in data['trading']:
                    trading_sessions = self.sessions_from_str(m)
                    if trading_sessions is None:
                        error_logger.error("Trading sessions invalid format")

                    for session in trading_sessions:
                        if session not in self._trading_sessions:
                            self._trading_sessions.append(session)

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

    @staticmethod
    def duration_from_str(duration: str) -> Union[float, None]:
        if not duration or type(duration) is not str:
            return None

        parts = duration.split(':')
        if len(parts) != 2:
            return None

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
        except ValueError:
            return None

        return hours * 3600.0 + minutes * 60.0

    def sessions_from_str(self, moment: str) -> Union[List[TradingSession], None]:
        # mon tue wed thu fri sat sun
        if not moment or type(moment) is not str:
            return None

        days_of_week = {
            "any": -2,
            "dow": -1,
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6
        }

        parts = moment.split('/')
        if len(parts) != 2:
            return None

        times = parts[1].split("-")
        if len(times) != 2:
            return None

        if parts[0] not in days_of_week:
            return None

        fd = Instrument.duration_from_str(times[0])
        td = Instrument.duration_from_str(times[1])

        results = []

        if parts[0] == "any":
            # any days
            for d in range(0, 7):
                results.append(TradingSession(d, fd, td))
        elif parts[0] == "dow":
            # any days of week
            for d in range(0, 5):
                results.append(TradingSession(d, fd, td))
        else:
            # day is defined
            results.append(TradingSession(days_of_week[parts[0]], fd, td))

        return results
