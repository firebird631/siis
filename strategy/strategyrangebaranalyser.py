# @date 2023-09-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Tick bar based sub-strategy base class.

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Tuple, Union, Optional

from watcher.watcher import Watcher

if TYPE_CHECKING:
    from monitor.streamable import Streamable

    from .strategytraderbase import StrategyTraderBase
    from .indicator.price.price import PriceIndicator
    from .indicator.volume.volume import VolumeIndicator

    from instrument.instrument import Instrument, TickType
    from instrument.bar import BarBase, RangeBar

from instrument.rangebargenerator import RangeBarGenerator

from .strategybaseanalyser import StrategyBaseAnalyser

import logging
logger = logging.getLogger('siis.strategy.strategyrangebaranalyser')
error_logger = logging.getLogger('siis.error.strategy.strategyrangebaranalyser')
traceback_logger = logging.getLogger('siis.traceback.strategy.strategyrangebaranalyser')


class StrategyRangeBarAnalyser(StrategyBaseAnalyser):
    """
    StrategyRangeBarAnalyser data-series per non-temporal range-bar analyser base class.
    """

    rb: int

    last_timestamp: float

    _update_at_close: bool

    _range_bar_generator: Union[RangeBarGenerator, None]
    _last_closed: bool

    price: Union[PriceIndicator, None]
    volume: Union[VolumeIndicator, None]

    open_price: Union[float, None]  # open price of the last closed bar
    close_price: Union[float, None]  # close price of the last closed bar
    prev_open_price: Union[float, None]  # previous open price
    prev_close_price: Union[float, None]  # previous close price

    _range_bars: List[RangeBar]

    def __init__(self, name: str, strategy_trader: StrategyTraderBase, range_bar_size: int,
                 depth: int, history: int, params: dict = None):

        super().__init__(name, strategy_trader)

        params = params or {}

        self.rb = range_bar_size
        self.depth = depth  # min samples size needed for processing
        self.history = history  # sample history size

        self.last_timestamp = 0.0

        self._update_at_close = params.get('update-at-close', False)

        self._range_bar_generator = RangeBarGenerator(range_bar_size, params.get('tick-scale', 1.0))
        self._last_closed = False  # last generated bar closed

        self.price = None  # price indicator
        self.volume = None  # volume indicator

        self.open_price = None  # last OHLC open
        self.close_price = None  # last OHLC close
        self.prev_open_price = None  # previous OHLC open
        self.prev_close_price = None  # previous OHLC close

        self._range_bars = []

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
        return self._range_bar_generator

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
                    indicator = self._strategy_trader.strategy.indicator(param[0])(0.0, *param[1:])
                    indicator.setup(self._strategy_trader.instrument)

                    # @todo warning if not enough depth/history

                    setattr(self, ind, indicator)
                else:
                    logger.error("Indicator %s not found for %s on bar %s" % (param[0], ind, self.rb))
            else:
                # logger.info("No indicator for %s on bar %s" % (ind, self.tb))
                setattr(self, ind, None)

    def setup_generator(self, instrument: Instrument):
        if self._range_bar_generator:
            self._range_bar_generator.setup(instrument)

    def query_historical_data(self, to_date: datetime):
        if self.bar_size > 0:
            self.need_initial_data()

            # non-temporal bar then cannot determine the beginning date
            begin_date = None
            end_date = to_date - timedelta(seconds=1) if to_date else None

            adj_from_date, adj_to_date, n_last = self.instrument.adjust_date_and_last_n(
                self.history, self.depth, begin_date, end_date)

            watcher = self.instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
            if watcher:
                watcher.query_historical_range_bars(self.instrument.market_id, self.name, self.timeframe,
                                                    to_date=adj_to_date, n_last=n_last)

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

    def complete(self, range_bars: List[BarBase], timestamp: float):
        """
        Must be called at the end of the process method.
        """
        self.last_timestamp = timestamp

        # -1 is current
        if self._last_closed and self.price:
            # get just closed tick bar price and swap
            self.prev_close_price = self.close_price
            self.prev_open_price = self.open_price

            if len(self.price.close) > 1:
                self.close_price = self.price.close[-2]
                self.open_price = self.price.open[-2]

            # last closed bar processed (reset before next gen)
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

    def get_bars(self) -> List[BarBase]:
        """
        Get the range-bar list to process.
        """
        return self._range_bars[-self.depth:] if self._range_bars else []

    def add_bars(self, range_bars_list: List[RangeBar], max_bars: int = -1):
        """
        Append an array of new range-bars.
        @param range_bars_list
        @param max_bars Pop range-bars until num range_bars > max_range_bars.
        """
        if not range_bars_list:
            return

        # array of tickbar
        if len(self._range_bars) > 0:
            for range_bar in range_bars_list:
                # for each tickbar only add it if more recent or replace a non consolidated
                if range_bar.timestamp > self._range_bars[-1].timestamp:
                    if not self._range_bars[-1].ended:
                        # remove the last range-bar if was not consolidated
                        # self._range_bars.pop(-1)
                        self._range_bars[-1].set_consolidated(True)
                        self._range_bars.append(range_bar)
                    else:
                        self._range_bars.append(range_bar)

                elif range_bar.timestamp == self._range_bars[-1].timestamp and not self._range_bars[-1].ended:
                    # replace the last range-bar if was not consolidated
                    self._range_bars[-1] = range_bar
        else:
            # initiate array, simply copy reference
            self._range_bars = range_bars_list

        # keep safe size
        if max_bars > 1 and self._range_bars:
            while(len(self._range_bars)) > max_bars:
                self._range_bars.pop(0)

    def add_bar(self, range_bar: RangeBar, max_bars: int = -1):
        """
        Append a new range-bar.
        @param range_bar
        @param max_bars Pop tickbars until num range_bars > max_range_bars.
        """
        if not range_bar:
            return

        # single tickbar
        if len(self._range_bars) > 0:
            # ignore the tickbar if older than the latest
            if range_bar.timestamp > self._range_bars[-1].timestamp:
                if not self._range_bars[-1].ended:
                    # replace the last tickbar if was not consolidated
                    # self._range_bars[-1] = range_bar
                    self._range_bars[-1].set_consolidated(True)
                    self._range_bars.append(range_bar)
                else:
                    self._range_bars.append(range_bar)

            elif range_bar.timestamp == self._range_bars[-1].timestamp and not self._range_bars[-1].ended:
                # replace the last tickbar if was not consolidated
                self._range_bars[-1] = range_bar
        else:
            self._range_bars.append(range_bar)

        # keep safe size
        if max_bars > 1 and self._range_bars:
            while(len(self._range_bars)) > max_bars:
                self._range_bars.pop(0)
            # if self.rb == 16:
            #     logger.debug("%s %s" % (self._range_bars[-2], self._range_bars[-1]))

    def range_bar(self) -> Optional[RangeBar]:
        """Return as possible the last range-bar."""
        if self._range_bars:
            return self._range_bars[-1]

        return None

    def range_bars(self) -> List[RangeBar]:
        """Returns range-bars list."""
        return self._range_bars

    def clear_bars(self):
        self._range_bars.clear()

    #
    # properties
    #

    @property
    def timeframe(self) -> float:
        """
        Timeframe of this strategy-trader is bar.
        """
        return 0.0

    @property
    def bar_size(self) -> int:
        """
        Range-bar size.
        """
        return self.rb

    @property
    def samples_depth_size(self) -> int:
        """
        Number of Ohlc to have at least to process the computation.
        """
        return self.depth

    @property
    def samples_history_size(self) -> int:
        """
        Number of Ohlc used for initialization on kept in memory.
        """
        return self.history

    @property
    def update_at_close(self) -> bool:
        return self._update_at_close

    @property
    def last_closed(self) -> bool:
        return self._last_closed

    #
    # data streaming (@deprecated way) and monitoring
    #

    def setup_streamer(self, streamer: Streamable):
        pass

    def stream(self, streamer: Streamable):
        pass
