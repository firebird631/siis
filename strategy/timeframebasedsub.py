# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based sub-strategy base class.

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Union

if TYPE_CHECKING:
    from instrument.instrument import Candle
    from monitor.streamable import Streamable

    from .timeframebasedstrategytrader import TimeframeBasedStrategyTrader
    from .strategysignal import StrategySignal
    from .indicator.price.price import PriceIndicator
    from .indicator.volume.volume import VolumeIndicator

from instrument.candlegenerator import CandleGenerator
from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy.timeframebasedsub')


class TimeframeBasedSub(object):
    """
    TimeframeBasedSub sub computation base class.
    """

    strategy_trader: TimeframeBasedStrategyTrader

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

    open_price: Union[float, None]
    close_price: Union[float, None]
    prev_open_price: Union[float, None]
    prev_close_price: Union[float, None]

    def __init__(self, strategy_trader: TimeframeBasedStrategyTrader, timeframe: float,
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

    def setup_indicators(self, params: dict):
        """
        Standard implementation to instantiate and setup the indicator based on the timeframe,
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

                    setattr(self, ind, indicator)
                else:
                    logger.error("Indicator %s not found for %s on timeframe %s" % (
                        param[0], ind, timeframe_to_str(self.tf)))
            else:
                logger.info("No indicator for %s on timeframe %s" % (ind, timeframe_to_str(self.tf)))
                setattr(self, ind, None)

    def init_candle_generator(self):
        """
        Setup the ohlc generator for this sub unit using the configured timeframe
        and the current opened ohlc.
        This method is called once the initial ohlc are fetched from the strategy setup process.
        """
        if self.candles_gen and not self.candles_gen.current:
            last_candle = self.strategy_trader.instrument.candle(self.tf)
            if last_candle and not last_candle.ended:
                # the last candle is not ended, we have to continue it
                self.candles_gen.current = last_candle

    def need_update(self, timestamp: float) -> bool:
        """
        Return True if the compute must be done.
        If update at close then wait for the last OHLC close, else always returns true.
        """
        if self._update_at_close:
            return self._last_closed

        return True

    def need_signal(self, timestamp: float) -> bool:
        """
        Return True if the signal can be generated and returned at this processing.
        If signal at close than wait for the last candle close, else always returns true.
        """
        if self._signal_at_close:
            return self._last_closed

        return True

    def process(self, timestamp: float):
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
        # candles = self.strategy_trader.instrument.last_candles(self.tf, self.depth)
        candles = self.strategy_trader.instrument.candles(self.tf)[-self.depth:]

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

    def report_state(self) -> Tuple:
        """
        Return an tuple of tuples with the data value to report.
        """
        return tuple()
