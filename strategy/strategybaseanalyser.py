# @date 2023-09-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Base model for strategy analyser

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Union

from strategy.mixins.generatorupdater import GeneratorUpdaterMixin

if TYPE_CHECKING:
    from datetime import datetime

    from strategy.strategytraderbase import StrategyTraderBase
    from instrument.instrument import Candle, TickType, Instrument
    from monitor.streamable import Streamable


class StrategyBaseAnalyser(GeneratorUpdaterMixin):
    """
    Base model for strategy analyser per timeframe or any other non-temporal bar method.
    It computes different indicators (mostly oscillators) and some states.
    It is computed at each tick or bar from the strategy trader process.

    @see StrategyTimeframeAnalyser for temporal timeframe (1m, 1h...)
    @see StrategyRangeBarAnalyser for range-bar.
    @see StrategyReversalBarAnalyser for reversal-bar.
    @see StrategyTickBarAnalyser for tick-bar.
    @see StrategyVolumeBarAnalyser for volume-bar.
    """

    _name: str
    _strategy_trade: StrategyTraderBase

    _waiting_initial_data: bool

    depth: int
    history: int

    def __init__(self, name: str,strategy_trader: StrategyTraderBase):
        self._name = name
        self._strategy_trader = strategy_trader

        self._waiting_initial_data = False

        self.depth = 0
        self.history = 0

    def loads(self, params: dict):
        """
        Reload basic parameters.
        """
        pass

    def setup_indicators(self, params: dict):
        """
        Standard implementation to instantiate and set up the indicator based on the timeframe,
        from the parameters.
        """
        pass

    def init_generator(self):
        """
        Initiate the bar generator for this analyser depending on the type and configuration.
        This method is called once the initial ohlc are fetched from the strategy setup process.
        """
        pass

    def setup_generator(self, instrument: Instrument):
        """
        Set up the bar generator for this analyser depending on the instrument parameters.
        This method is called once the market info are retrieved.
        """
        pass

    def query_historical_data(self, to_date: datetime):
        """
        Query historical data from database.
        Use history size and auto compute the necessary best range.
        """
        pass

    def get_all_bars(self) -> List:
        """Get all available bars."""
        return []

    def add_bar(self, bar, max_size: int = -1):
        """Add a single bar"""
        pass

    def add_bars(self, bars: List, max_size: int = -1):
        """Add a list of bars"""
        pass

    def get_bars_after(self, after_timestamp: float) -> List:
        """
        Returns bars having timestamp >= after_ts in seconds.
        """
        return []

    def clear_bars(self):
        """Clear bars"""
        pass

    def need_update(self, timestamp: float) -> bool:
        """
        Return True if computing must be done.
        If update at close then wait for the last OHLC close, else always returns true.
        """
        return True

    def process(self, timestamp: float, last_ticks: Union[List[TickType], None] = None):
        """
        Process the computation of indicators and tools here. And eventual intermediates states (crossing...)
        """
        pass

    def complete(self, candles: List[Candle], timestamp: float):
        """
        Must be called at the end of the process method.
        """
        pass

    def cleanup(self, timestamp: float):
        """
        Once data are processed some cleanup could be necessary to be done
        before running the next process pass.

        For example resetting stats of the closed OHLC.
        """
        pass

    def need_initial_data(self):
        """This analyser wait to receive initial data set of bars."""
        self._waiting_initial_data = True

    @property
    def is_need_initial_data(self) -> bool:
        """Return True if an initial data set of bars is waited."""
        return self._waiting_initial_data

    def ack_initial_data(self):
        """Acknowledge the reception of initial data set of bars."""
        self._waiting_initial_data = False

    #
    # properties
    #

    @property
    def name(self) -> str:
        """Unique name per strategy as defined into the configuration."""
        return self._name

    @classmethod
    def type_name(cls) -> str:
        """Internal type name (mode)."""
        return ""

    @property
    def strategy_trade(self) -> StrategyTraderBase:
        """Owner strategy trader."""
        return self._strategy_trader

    @property
    def timeframe(self) -> float:
        """Timeframe of this strategy-trader in second or 0 for non-temporal bar."""
        return 0.0

    @property
    def bar_size(self) -> int:
        """Non temporal-bar size."""
        return 0

    @property
    def bar_generator(self):
        """Bar generator."""
        return None

    @property
    def samples_depth_size(self) -> int:
        """Number of Ohlc to have at least to process the computation."""
        return 0

    @property
    def samples_history_size(self) -> int:
        """Number of Ohlc used for initialization on kept in memory."""
        return 0

    @property
    def update_at_close(self) -> bool:
        return False

    @property
    def last_closed(self) -> bool:
        return False

    @property
    def instrument(self):
        return self._strategy_trader.instrument

    #
    # indicator processing
    #

    def update_tick(self, tick: TickType, finalize: bool):
        """
        Here put any tick based indicator update.
        Such as bar volume-profile, bar vwap, bar cumulative volume delta...
        @param tick: Last processed tick
        @param finalize: True if the bar just close
        """
        pass

    def update_bar(self, bar: Candle):
        """
        Here put any bar based indicator update.
        Such as bar volume-profile, bar vwap, bar cumulative volume delta...
        @param bar: Last generated bar and closed bar
        """
        pass

    #
    # data streaming
    #

    def setup_streamer(self, streamer: Streamable):
        pass

    def stream(self, streamer: Streamable):
        pass

    def retrieve_bar_index(self, streamer: Streamable):
        return -1

    #
    # data series reporting
    #

    def report_state_members(self) -> Tuple:
        """
        Return a tuple of tuples with the name and format of the value to report.
        @note Must be of the same length as return by report_state method.
        """
        return tuple()

    def report_state(self) -> Tuple:
        """
        Return a tuple of tuples with the data value to report.
        @note Must be of the same length as return by report_state_members method.
        """
        return tuple()
