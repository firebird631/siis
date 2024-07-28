# @date 2022-10-17
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Support/resistance indicator based on OHLCs

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument


class SRLevelIndicator(Indicator):
    """
    Support/resistance indicator based on OHLCs based on timeframe.

    @todo Support of evening session and overnight session.
    @todo Complete finalize and check time ranges

    It is a complement on ATRSR indicator or any other S/R indicator.
    Take in compute parameters two list of levels (down and up).

    @note Works with both temporal and non-temporal bars.
    """

    __slots__ = '_depth', '_step_size', '_currents', '_previous'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_SUPPORT_RESISTANCE

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TIMEFRAME | Indicator.BASE_TICKBAR

    def __init__(self, timeframe, depth=5, step_size=1.0):
        super().__init__("srlevel", timeframe)

        self._compute_at_close = True  # only at close

        self._depth = depth  # number of levels to use
        self._step_size = step_size  # width of a step (must be adjusted for each instrument)

        self._currents = []
        self._previous = []

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def step_size(self) -> float:
        return self._step_size

    @property
    def currents(self) -> list[float]:
        return self._currents

    @property
    def previous(self) -> list[float]:
        return self._previous

    def supports(self, price: float, direction: int, epsilon: float = 0.0):
        """
        Give the current and previous supports below or above given price and a direction.
        @param price: float price to compare with
        @param direction: int 1 or -1
        @param epsilon: float optional epsilon for comparison
        """
        bottoms = []

        if direction > 0:
            for lvl in self._currents:
                if lvl + epsilon < price:
                    bottoms.append(lvl)
        elif direction < 0:
            for lvl in self._currents:
                if lvl - epsilon > price:
                    bottoms.append(lvl)

        return bottoms

    def resistances(self, price: float, direction: int, epsilon: float = 0.0):
        """
        Give the current and previous resistances below or above given price and a direction.
        @param price: float price to compare with
        @param direction: int 1 or -1
        @param epsilon: float optional epsilon for comparison
        """
        resistances = []

        if direction > 0:
            for lvl in self._currents:
                if lvl - epsilon > price:
                    resistances.append(lvl)
        elif direction < 0:
            for lvl in self._currents:
                if lvl + epsilon < price:
                    resistances.append(lvl)

        return resistances

    def compute(self, timestamp, last_timestamp, downs, ups, step_size=None):
        """
        Compute method. The downs and ups given should be ordered by time and not by price.
        More recent are more useful.

        @param timestamp: current timestamp in seconds
        @param last_timestamp: last computation timestamp of the downs and ups givens in parameters
        @param downs: recently computed downward S/R.
        @param ups: recently computed upwards S/R.
        @param step_size: optional step size to override default else use default (from init).
        @return: A list of optimised and filtered levels.
        """
        if self._last_timestamp >= last_timestamp:
            return self._currents

        self._previous = self._currents
        self._currents = []

        # preferred step size
        step_size = step_size if step_size else self._step_size

        # optimizes S/R
        for dn in downs[-self.depth:]:
            pass

        for up in ups[-self.depth:]:
            pass

        self._last_timestamp = timestamp

        return self._currents
