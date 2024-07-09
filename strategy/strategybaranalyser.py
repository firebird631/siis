# @date 2023-09-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Tick bar based sub-strategy base class.

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Union

if TYPE_CHECKING:
    from monitor.streamable import Streamable

    from .tickbarbasedstrategytrader import TickBarBasedStrategyTrader
    from .strategysignal import StrategySignal
    from .indicator.price.price import PriceIndicator
    from .indicator.volume.volume import VolumeIndicator

    from instrument.rangebargenerator import RangeBarBaseGenerator
    from instrument.tickbargenerator import TickBarBaseGenerator
    from instrument.instrument import Instrument
    from instrument.tickbar import TickBarBase

from .strategybaseanalyser import StrategyBaseAnalyser

import logging

logger = logging.getLogger('siis.strategy.strategybaranalyser')


class StrategyBarAnalyser(StrategyBaseAnalyser):
    """
    StrategyBarAnalyser data-series per non-temporal bar analyser base class.
    """

    strategy_trader: TickBarBasedStrategyTrader

    tb: int
    depth: int
    history: int

    last_timestamp: float

    _update_at_close: bool
    _signal_at_close: bool

    tick_bar_gen: Union[TickBarBaseGenerator, RangeBarBaseGenerator, None]
    _last_closed: bool

    last_signal: Union[StrategySignal, None]

    price: Union[PriceIndicator, None]
    volume: Union[VolumeIndicator, None]

    open_price: Union[float, None]  # open price of the last closed bar
    close_price: Union[float, None]  # close price of the last closed bar
    prev_open_price: Union[float, None]  # previous open price
    prev_close_price: Union[float, None]  # previous close price

    def __init__(self, strategy_trader: TickBarBasedStrategyTrader, tickbar: int,
                 depth: int, history: int, params: dict = None):
        self.strategy_trader = strategy_trader  # parent strategy-trader object

        params = params or {}

        self.tb = tickbar
        self.depth = depth  # min samples size needed for processing
        self.history = history  # sample history size

        self.last_timestamp = 0.0

        self._update_at_close = params.get('update-at-close', False)
        self._signal_at_close = params.get('signal-at-close', False)

        self.tick_bar_gen = None
        self._last_closed = False  # last generated tickbar closed

        self.last_signal = None

        self.price = None  # price indicator
        self.volume = None  # volume indicator

        self.open_price = None  # last OHLC open
        self.close_price = None  # last OHLC close
        self.prev_open_price = None  # previous OHLC open
        self.prev_close_price = None  # previous OHLC close

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

        if 'signal-at-close' in params and params['signal-at-close'] != self._signal_at_close:
            self._signal_at_close = params['signal-at-close']

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
                if self.strategy_trader.strategy.indicator(param[0]):
                    # instantiate and setup indicator
                    indicator = self.strategy_trader.strategy.indicator(param[0])(0.0, *param[1:])
                    indicator.setup(self.strategy_trader.instrument)

                    # @todo warning if not enough depth/history

                    setattr(self, ind, indicator)
                else:
                    logger.error("Indicator %s not found for %s on tickbar %s" % (param[0], ind, self.tb))
            else:
                # logger.info("No indicator for %s on tickbar %s" % (ind, self.tb))
                setattr(self, ind, None)

    def setup_generator(self, instrument: Instrument):
        if self.tick_bar_gen:
            self.tick_bar_gen.setup(instrument)

    def need_update(self, timestamp: float) -> bool:
        """
        Return True if computing must be done.
        If update at close then wait for the last OHLC close, else always returns true.
        """
        if self._update_at_close:
            return self._last_closed

        return True

    def need_signal(self, timestamp: float) -> bool:
        """
        Return True if the signal can be generated and returned at this processing.
        If signal at close then wait for the last tickbar close, else always returns true.
        """
        if self._signal_at_close:
            return self._last_closed

        return True

    def process(self, timestamp: float) -> Union[StrategySignal, None]:
        """
        Process the computation here.
        """
        return None

    def complete(self, tickbars: List[TickBarBase], timestamp: float):
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

            # last closed tickbar processed (reset before next gen)
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

    def get_tickbars(self) -> List[TickBarBase]:
        """
        Get the tickbar list to process.
        """
        dataset = self.strategy_trader.instrument.tickbars(self.tb)
        tickbars = dataset[-self.depth:] if dataset else []

        return tickbars

    #
    # properties
    #

    @property
    def timeframe(self) -> float:
        """
        Timeframe of this strategy-trader is tick.
        """
        return 0.0

    @property
    def tickbar(self) -> float:
        """
        Tickbar size.
        """
        return self.tb

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
    def signal_at_close(self) -> bool:
        return self._signal_at_close

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
