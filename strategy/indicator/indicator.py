# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Indicator base class

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from instrument.instrument import Instrument


class Indicator(object):
    """
    Base class for an indicator.
    """

    __slots__ = '_name', '_timeframe', '_last_timestamp', '_compute_at_close'

    TYPE_UNKNOWN = 0
    TYPE_AVERAGE_PRICE = 1
    TYPE_MOMENTUM = 2
    TYPE_VOLATILITY = 4
    TYPE_SUPPORT_RESISTANCE = 8
    TYPE_TREND = 16
    TYPE_VOLUME = 32
    TYPE_MOMENTUM_VOLUME = 2|32
    TYPE_MOMENTUM_SUPPORT_RESISTANCE_TREND = 2|8|16

    CLS_UNDEFINED = 0
    CLS_CUMULATIVE = 1
    CLS_INDEX = 2
    CLS_OSCILLATOR = 3
    CLS_OVERLAY = 4
    CLS_CYCLE = 5

    BASE_TIMEFRAME = 0
    BASE_TICKBAR = 1
    BASE_TICK = 2

    @classmethod
    def indicator_type(cls) -> int:
        return Indicator.TYPE_UNKNOWN

    @classmethod
    def indicator_class(cls) -> int:
        return Indicator.TYPE_UNKNOWN

    @classmethod
    def persistent(cls) -> bool:
        return False

    @classmethod
    def indicator_base(cls) -> int:
        return Indicator.BASE_TIMEFRAME

    @classmethod
    def indicator_tickbar_based(cls) -> bool:
        """
        Is timeframe bar based indicator.
        """
        return cls.indicator_base() == Indicator.BASE_TICKBAR

    @classmethod
    def indicator_timeframe_based(cls) -> bool:
        """
        Is tick bar based indicator.
        """
        return cls.indicator_base() == Indicator.BASE_TIMEFRAME

    @classmethod
    def indicator_tick_based(cls) -> bool:
        """
        Is tick based indicator.
        """
        return cls.indicator_base() == Indicator.BASE_TICK

    def __init__(self, name: str, timeframe: float):
        self._name = name
        self._timeframe = timeframe

        self._last_timestamp = 0  # last compute timestamp
        self._compute_at_close = False

    def setup(self, instrument: Instrument):
        """
        After the instantiation this method is called with the related instrument objet.
        To be overloaded.
        """
        pass

    @property
    def name(self) -> str:
        return self._name

    @property
    def last_timestamp(self) -> float:
        return self._last_timestamp

    @property
    def timeframe(self) -> float:
        return self._timeframe

    @property
    def compute_at_close(self) -> bool:
        """
        Some indicator could be only computed at an OHLC close
        """
        return self._compute_at_close

    #
    # process
    #

    # def compute(self, timestamp: float) -> Any:
    #     # parameters are different depending of the indicator
    #     return None
