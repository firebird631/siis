# @date 2018-10-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Simple volume indicator using candle data.

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample

import numpy as np


class VolumeIndicator(Indicator):
    """
    Simple volume indicator using candle data.
    """

    VOLUME_TICK = 0   # take the tick volume

    __slots__ = '_method', '_volumes', '_prev', '_last'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, method=VOLUME_TICK):
        super().__init__("volume", timeframe)
        
        self._method = method
        self._volumes = np.array([])

        self._prev = 0.0
        self._last = 0.0

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

    @property
    def volumes(self):
        return self._volumes

    @staticmethod
    def Volume(method, data):
        if method == VolumeIndicator.VOLUME_TICK:
            return np.array([x.volume for x in data])
        else:
            return np.array([x.volume for x in data])

    @staticmethod
    def Volume_sf(method, data, step=1, filtering=False):
        if method == VolumeIndicator.VOLUME_TICK:
            tick_volumes = [x.volume for x in data]

            sub_data = down_sample(tick_volumes, step) if filtering else np.array(tick_volumes[::step])
            # todo interpolate
            # t_subdata = range(0,len(data),step)

            return sub_data

        return np.array([])

    def compute(self, timestamp, candles):
        self._prev = self._last

        self._volumes = VolumeIndicator.Volume(self._method, candles)  # , self._step, self._filtering)

        self._last = self._volumes[-1]
        self._last_timestamp = timestamp

        return self._volumes
