# @date 2023-09-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Base model for strategy sub

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Union

if TYPE_CHECKING:
    from instrument.instrument import Candle
    from monitor.streamable import Streamable

    from .strategysignal import StrategySignal


class StrategySub(object):
    """
    Base model for strategy sub.
    """

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

    def init_candle_generator(self):
        """
        Set up the ohlc generator for this sub, using the configured timeframe and the current opened ohlc.
        This method is called once the initial ohlc are fetched from the strategy setup process.
        """
        pass

    def need_update(self, timestamp: float) -> bool:
        """
        Return True if computing must be done.
        If update at close then wait for the last OHLC close, else always returns true.
        """
        return True

    def need_signal(self, timestamp: float) -> bool:
        """
        Return True if the signal can be generated and returned at this processing.
        If signal at close then wait for the last candle close, else always returns true.
        """
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
        pass

    def cleanup(self, timestamp: float):
        """
        Once data are processed some cleanup could be necessary to be done
        before running the next process pass.

        For example resetting stats of the closed OHLC.
        """
        pass

    #
    # properties
    #

    @property
    def timeframe(self) -> float:
        """
        Timeframe of this strategy-trader in second.
        """
        return 0.0

    @property
    def tickbar(self) -> int:
        """
        Tickbar size.
        """
        return 0

    @property
    def samples_depth_size(self) -> int:
        """
        Number of Ohlc to have at least to process the computation.
        """
        return 0

    @property
    def samples_history_size(self) -> int:
        """
        Number of Ohlc used for initialization on kept in memory.
        """
        return 0

    @property
    def update_at_close(self) -> bool:
        return False

    @property
    def signal_at_close(self) -> bool:
        return False

    @property
    def last_closed(self) -> bool:
        return False

    #
    # data streaming (@deprecated way) and monitoring
    #

    def setup_streamer(self, streamer: Streamable):
        pass

    def stream(self, streamer: Streamable):
        pass

    def report_state(self) -> Tuple:
        """
        Return a tuple of tuples with the data value to report.
        """
        return tuple()
