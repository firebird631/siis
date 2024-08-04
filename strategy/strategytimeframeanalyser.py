# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based analyser base class.

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Union, Optional

from watcher.watcher import Watcher
from .indicator.indicator import Indicator
from .strategytraderbase import StrategyTraderBase

if TYPE_CHECKING:
    from instrument.instrument import Candle, TickType
    from monitor.streamable import Streamable

    from .indicator.price.price import PriceIndicator
    from .indicator.volume.volume import VolumeIndicator

from .strategybaseanalyser import StrategyBaseAnalyser

from instrument.timeframebargenerator import TimeframeBarGenerator
from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy.strategytimeframeanalyser')


class StrategyTimeframeAnalyser(StrategyBaseAnalyser):
    """
    StrategyTimeframeAnalyser Timeframe data-series analyser base class.

    __init__ signature for child class must be :
        def __init__(self, name: str, strategy_trader: StrategyTraderBase, params: dict):
            super().__init__(name, strategy_trader, params['timeframe'], params['depth'], params['history'], params)

            # to your stuff here

            self.setup_indicators(params)

    to be invokable by a strategy trader.
    @note This could change on a refactoring.
    """

    tf: float
    depth: int
    history: int

    last_timestamp: float

    _update_at_close: bool

    _timeframe_bar_generator: TimeframeBarGenerator
    _last_closed: bool
    
    price: Union[PriceIndicator, None]
    volume: Union[VolumeIndicator, None]

    open_price: Union[float, None]          # open price of the last closed candle
    close_price: Union[float, None]         # close price of the last closed candle
    prev_open_price: Union[float, None]     # previous open price
    prev_close_price: Union[float, None]    # previous close price

    _timeframe_bars: List[Candle]

    def __init__(self, name: str, strategy_trader: StrategyTraderBase, timeframe: float,
                 depth: int, history: int, params: dict = None):

        super().__init__(name, strategy_trader)

        params = params or {}

        self.tf = timeframe
        self.depth = depth       # min samples size needed for processing
        self.history = history   # sample history size

        self.last_timestamp = 0.0

        self._update_at_close = params.get('update-at-close', False)

        self._timeframe_bar_generator = TimeframeBarGenerator(self._strategy_trader.base_timeframe, self.tf)
        self._last_closed = False  # last generated candle closed

        self.price = None   # price indicator
        self.volume = None  # volume indicator

        self.open_price = None        # last OHLC open
        self.close_price = None       # last OHLC close
        self.prev_open_price = None   # previous OHLC open
        self.prev_close_price = None  # previous OHLC close

        self._timeframe_bars = []

    def loads(self, params: dict):
        """
        Reload basic parameters.
        """
        if 'depth' in params and params['depth'] != self.depth:
            self.depth = params['depth']

        if 'history' in params and params['history'] != self.history:
            self.history = params['history']

        if 'update-at-close' in params and params['update-at-close'] != self._update_at_close:
            self._update_at_close = params['update-at-close']

    @property
    def bar_generator(self):
        return self._timeframe_bar_generator

    def setup_indicators(self, params: dict):
        """
        Standard implementation to instantiate and set up the indicator based on the timeframe,
        from the parameters.
        """
        if 'indicators' not in params:
            return None

        if type(params['indicators']) is not dict:
            return None

        for ind, param in params['indicators'].items():
            if param is not None:
                if self._strategy_trader.strategy.indicator(param[0]):
                    # instantiate and setup indicator
                    indicator = self._strategy_trader.strategy.indicator(param[0]).builder(
                        Indicator.BASE_TIMEFRAME, self.tf, *param[1:])

                    indicator.setup(self._strategy_trader.instrument)

                    setattr(self, ind, indicator)
                else:
                    logger.error("Indicator %s not found for %s on timeframe %s" % (
                        param[0], ind, timeframe_to_str(self.tf)))
            else:
                # logger.info("No indicator for %s on timeframe %s" % (ind, timeframe_to_str(self.tf)))
                setattr(self, ind, None)

    def init_generator(self):
        """
        Set up the bar generator, using the configured timeframe and the current opened ohlc.
        This method is called once the initial ohlc are fetched from the strategy setup process.
        """
        if self._timeframe_bar_generator and not self._timeframe_bar_generator.current:
            last_candle = self._timeframe_bars[-1] if self._timeframe_bars else None
            if last_candle and not last_candle.ended:
                # the last candle is not ended, we have to continue it
                self._timeframe_bar_generator.current = last_candle

    def query_historical_data(self, to_date: Optional[datetime]):
        if self.timeframe > 0.0:
            self.need_initial_data()

            # determine from date using timeframe and history size
            begin_date = to_date - timedelta(seconds=self.history * self.timeframe + 1.0) if to_date else None
            end_date = to_date - timedelta(seconds=1) if to_date else None

            adj_from_date, adj_to_date, n_last = self.instrument.adjust_date_and_last_n(
                self.history, self.depth, begin_date, end_date)

            watcher = self.instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
            if watcher:
                watcher.query_historical_timeframe_bars(self.instrument.market_id, self.name, self.timeframe,
                                                        from_date=adj_from_date, to_date=adj_to_date, n_last=n_last)

    def need_update(self, timestamp: float) -> bool:
        """
        Return True if computing must be done.
        If update at close then wait for the last OHLC close, else always returns true.
        """
        if self._update_at_close:
            return self._last_closed

        return True

    def process(self, timestamp: float, last_ticks: Union[List[TickType], None] = None):
        """
        Process the computation here.
        """
        pass

    def complete(self, candles: List[Candle], timestamp: float):
        """
        Must be called at the end of the process method.
        """
        self.last_timestamp = timestamp

        # -1 is current
        if self._last_closed and self.price:
            # get just closed OHLC price and swap
            self.prev_close_price = self.close_price
            self.prev_open_price = self.open_price

            if len(self.price.close) > 1:
                self.close_price = self.price.close[-2]
                self.open_price = self.price.open[-2]

            # last closed candle processed (reset before next gen)
            # self._last_closed = False

        elif self.close_price is None or self.open_price is None:
            # initial
            if len(self.price.close) > 1:
                self.close_price = self.price.close[-2]
                self.open_price = self.price.open[-2]

    def cleanup(self, timestamp: float):
        """
        Once data are processed some cleanup could be necessary to be done
        before running the next process pass.

        For example resetting stats of the closed OHLC.
        """
        if self.close_price:
            self.prev_open_price = None
            self.prev_close_price = None

    def get_bars(self) -> List[Candle]:
        """Get a slice of depth of the timeframes bars list to process."""
        return self._timeframe_bars[-self.depth:] if self._timeframe_bars else []

    def get_all_bars(self) -> List[Candle]:
        """Get all available bars."""
        return self._timeframe_bars

    def get_bars_after(self, after_timestamp: float) -> List:
        """
        Returns bars having timestamp >= after_ts in seconds.
        """
        results = []

        if self._timeframe_bars:
            # process for most recent to the past
            for c in reversed(self._timeframe_bars):
                if c.timestamp > after_timestamp:
                    # is there a gap between the prev and current candles, introduce missing ones
                    if len(results) and (results[0].timestamp - c.timestamp > self.timeframe):
                        ts = results[0].timestamp - self.timeframe

                        while ts > c.timestamp:
                            filler = Candle(ts, self.timeframe)

                            # same as previous
                            filler.copy(results[-1])

                            # empty volume
                            filler._volume = 0

                            results.insert(0, filler)
                            ts -= self.timeframe

                    results.insert(0, c)
                else:
                    break

        return results

    def add_bars(self, timeframe_bars_list: List[Candle], max_bars: int = -1):
        """
        Append an array of new timeframe-bars/candles.
        @param timeframe_bars_list
        @param max_bars Pop timeframe-bars until num timeframe_bars > max_bars.
        """
        if not timeframe_bars_list:
            return

        # array of tickbar
        if len(self._timeframe_bars) > 0:
            for timeframe_bar in timeframe_bars_list:
                # for each bar only add it if more recent or replace a non consolidated
                if timeframe_bar.timestamp > self._timeframe_bars[-1].timestamp:
                    if not self._timeframe_bars[-1].ended:
                        # remove the last candle if was not consolidated
                        # self._timeframe_bars.pop(-1)
                        self._timeframe_bars[-1].set_consolidated(True)
                        self._timeframe_bars.append(timeframe_bar)
                    else:
                        self._timeframe_bars.append(timeframe_bar)

                elif timeframe_bar.timestamp == self._timeframe_bars[-1].timestamp and not self._timeframe_bars[-1].ended:
                    # replace the last range-bar if was not consolidated
                    self._timeframe_bars[-1] = timeframe_bar
        else:
            # initiate array, simply copy reference
            self._timeframe_bars = timeframe_bars_list

        # keep safe size
        if max_bars > 1 and self._timeframe_bars:
            while(len(self._timeframe_bars)) > max_bars:
                self._timeframe_bars.pop(0)

    def add_bar(self, timeframe_bar: Candle, max_bars: int = -1):
        """
        Append a new timeframe-bar.
        @param timeframe_bar
        @param max_bars Pop tickbars until num range_bars > max_range_bars.
        """
        if not timeframe_bar:
            return

        # single tickbar
        if len(self._timeframe_bars) > 0:
            # ignore the bar if older than the latest
            if timeframe_bar.timestamp > self._timeframe_bars[-1].timestamp:
                if not self._timeframe_bars[-1].ended:
                    # replace the last bar if was not consolidated
                    # self._timeframe_bars[-1] = timeframe_bar
                    self._timeframe_bars[-1].set_consolidated(True)
                    self._timeframe_bars.append(timeframe_bar)
                else:
                    self._timeframe_bars.append(timeframe_bar)

            elif timeframe_bar.timestamp == self._timeframe_bars[-1].timestamp and not self._timeframe_bars[-1].ended:
                # replace the last bar if was not consolidated
                self._timeframe_bars[-1] = timeframe_bar
        else:
            self._timeframe_bars.append(timeframe_bar)

        # keep safe size
        if max_bars > 1 and self._timeframe_bars:
            while(len(self._timeframe_bars)) > max_bars:
                self._timeframe_bars.pop(0)
            # if self.timeframe == "2m":
            #     logger.debug("%s %s" % (self._timeframe_bars[-2], self._timeframe_bars[-1]))

    def clear_bars(self):
        self._timeframe_bars.clear()

    #
    # properties
    #

    @property
    def timeframe(self) -> float:
        return self.tf

    @property
    def samples_depth_size(self) -> int:
        return self.depth

    @property
    def samples_history_size(self) -> int:
        return self.history

    @property
    def update_at_close(self) -> bool:
        return self._update_at_close

    @property
    def last_closed(self) -> bool:
        return self._last_closed

    #
    # data streaming and monitoring
    #

    def setup_streamer(self, streamer: Streamable):
        pass

    def stream(self, streamer: Streamable):
        pass

    def retrieve_bar_index(self, streamer: Streamable):
        return -min(int((self.last_timestamp - streamer.last_timestamp) / self.tf) + 1, len(self.price.prices))
