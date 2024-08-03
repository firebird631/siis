# @date 2023-09-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Range bar generators.

import logging
from typing import TYPE_CHECKING, Union, List, Optional

from strategy.mixins.generatorupdater import GeneratorUpdaterMixin

if TYPE_CHECKING:
    pass

from common.utils import truncate

from instrument.instrument import Instrument, TickType, Candle
from instrument.bar import RangeBar, ReversalBar, TickBar, VolumeBar

logger = logging.getLogger('siis.instrument.bargeneratorbase')


class BarGeneratorBase(object):
    """
    Base model for non temporal bar specialized generators.
    """

    __slots__ = '_size', '_last_timestamp', '_last_consumed', '_current', '_tick_size', '_last_price', \
        '_price_precision', '_tick_scale'

    _size: int
    _tick_scale: float
    _price_precision: int
    _tick_size: float
    _last_consumed: int
    _last_timestamp: float
    _last_price: float
    _current: Union[RangeBar, ReversalBar, TickBar, VolumeBar, None]

    def __init__(self, size: int, tick_scale: float = 1.0):
        """
        @param size Generated tick bar tick number.
        @param tick_scale Regroup ticks by a scalar (default 1.0 for non grouping).
        """
        self._size = size if size > 0 else 1

        self._tick_scale = tick_scale

        self._price_precision = 1
        self._tick_size = 1.0

        self._last_consumed = 0
        self._last_timestamp = 0.0

        self._last_price = 0.0

        self._current = None

    @property
    def size(self) -> int:
        return self._size

    @property
    def tick_scale(self) -> float:
        return self._tick_scale

    @property
    def tick_size(self) -> float:
        return self._tick_size

    @property
    def price_precision(self) -> int:
        return self._price_precision

    @property
    def current(self) -> Union[RangeBar, ReversalBar, TickBar, VolumeBar, None]:
        return self._current

    def setup(self, instrument: Instrument):
        """
        Setup some constant from instrument.
        The tick size is scaled by the tick_scale factor.
        """
        if instrument is None:
            return

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001 * self._tick_scale

    def adjust_price(self, price: float) -> float:
        """
        Adjust the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    def generate_from_candles(self, from_candles: List[Candle], ignore_non_ended: bool = True,
                              generator_updater: Optional[GeneratorUpdaterMixin] = None):
        return []

    def generate_from_ticks(self, from_ticks: List[TickType],
                            generator_updater: Optional[GeneratorUpdaterMixin] = None):
        """
        Generate as many range-bar as possible from the array of ticks or trades given in parameters.
        """
        to_tickbars = []
        self._last_consumed = 0

        for from_tick in from_ticks:
            to_tickbar = self.update(from_tick)
            if to_tickbar:
                # if self.size == 16:
                #     logger.debug(str(to_tickbar))
                to_tickbars.append(to_tickbar)

            # alongside generate tick based indicator, close them only if a new bar
            if generator_updater:
                generator_updater.update_tick(from_tick, finalize=to_tickbar is not None)

            self._last_consumed += 1

        return to_tickbars

    def update(self, tick: TickType):
        """
        Overrides this method to implements specifics computed tick-bar model from a single tick or trade.
        """
        pass
