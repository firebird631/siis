# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based analyser base class.

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Union

if TYPE_CHECKING:
    from instrument.instrument import Candle
    from monitor.streamable import Streamable

    from .timeframestrategytrader import TimeframeStrategyTrader
    from .strategysignal import StrategySignal
    from .indicator.price.price import PriceIndicator
    from .indicator.volume.volume import VolumeIndicator

from .strategybaseanalyser import StrategyBaseAnalyser

from instrument.candlegenerator import CandleGenerator
from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy.strategytimeframeanalyser')


class StrategyTimeframeAnalyser(StrategyBaseAnalyser):
    """
    StrategyTimeframeAnalyser Timeframe data-series analyser base class.
    """

    strategy_trader: TimeframeStrategyTrader

    tf: float
    depth: int
    history: int

    last_timestamp: float

    _update_at_close: bool
    _signal_at_close: bool

    candles_gen: CandleGenerator
    _last_closed: bool
    
    last_signal: Union[StrategySignal, None]

    price: Union[PriceIndicator, None]
    volume: Union[VolumeIndicator, None]

    open_price: Union[float, None]          # open price of the last closed candle
    close_price: Union[float, None]         # close price of the last closed candle
    prev_open_price: Union[float, None]     # previous open price
    prev_close_price: Union[float, None]    # previous close price

    def __init__(self, strategy_trader: TimeframeStrategyTrader, timeframe: float,
                 depth: int, history: int, params: dict = None):
        self.strategy_trader = strategy_trader  # parent strategy-trader object

        params = params or {}

        self.tf = timeframe
        self.depth = depth       # min samples size needed for processing
        self.history = history   # sample history size

        self.last_timestamp = 0.0

        self._update_at_close = params.get('update-at-close', False)
        self._signal_at_close = params.get('signal-at-close', False)

        self.candles_gen = CandleGenerator(self.strategy_trader.base_timeframe, self.tf)
        self._last_closed = False  # last generated candle closed

        self.last_signal = None

        self.price = None   # price indicator
        self.volume = None  # volume indicator

        self.open_price = None        # last OHLC open
        self.close_price = None       # last OHLC close
        self.prev_open_price = None   # previous OHLC open
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
                    indicator = self.strategy_trader.strategy.indicator(param[0])(self.tf, *param[1:])
                    indicator.setup(self.strategy_trader.instrument)

                    # @todo warning if not enough depth/history

                    setattr(self, ind, indicator)
                else:
                    logger.error("Indicator %s not found for %s on timeframe %s" % (
                        param[0], ind, timeframe_to_str(self.tf)))
            else:
                # logger.info("No indicator for %s on timeframe %s" % (ind, timeframe_to_str(self.tf)))
                setattr(self, ind, None)

    def init_candle_generator(self):
        """
        Set up the ohlc generator for this sub, using the configured timeframe and the current opened ohlc.
        This method is called once the initial ohlc are fetched from the strategy setup process.
        """
        if self.candles_gen and not self.candles_gen.current:
            last_candle = self.strategy_trader.instrument.candle(self.tf)
            if last_candle and not last_candle.ended:
                # the last candle is not ended, we have to continue it
                self.candles_gen.current = last_candle

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
        If signal at close then wait for the last candle close, else always returns true.
        """
        if self._signal_at_close:
            return self._last_closed

        return True

    def process(self, timestamp: float) -> Union[StrategySignal, None]:
        """
        Process the computation here.
        """
        return None

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

    def get_candles(self) -> List[Candle]:
        """
        Get the candles list to process.
        """
        dataset = self.strategy_trader.instrument.candles(self.tf)
        candles = dataset[-self.depth:] if dataset else []

        return candles

    #
    # properties
    #

    @property
    def timeframe(self) -> float:
        """
        Timeframe of this strategy-trader in second.
        """
        return self.tf

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