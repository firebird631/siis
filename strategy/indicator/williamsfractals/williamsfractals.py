# @date 2023-10-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Williams Fractals indicator

from strategy.indicator.indicator import Indicator

import numpy as np


class WilliamsFractalsIndicator(Indicator):
    """
    Williams Fractals indicator
    """

    __slots__ = '_length', '_prev', '_last', '_fractals'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, length=2):
        super().__init__("williamsfractals", timeframe)

        self._length = length  # periods number
        self._prev = 0.0
        self._last = 0.0

        self._fractals = np.array([])

    @property
    def length(self):
        return self._length

    @length.setter
    def length(self, length):
        self._length = length

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

    @property
    def fractals(self):
        return self._fractals

    def compute(self, timestamp, prices, volumes):
        self._prev = self._last

        # @todo

        # on inverse le up fractal donne un short signal sur la bougie suivante
        # mais ici on respecte l'indicateur !

        # UpFractal
        # bool upflagDownFrontier = true
        # bool upflagUpFrontier0 = true
        # bool upflagUpFrontier1 = true
        # bool upflagUpFrontier2 = true
        # bool upflagUpFrontier3 = true
        # bool upflagUpFrontier4 = true

        # for i = 1 to n
        #     upflagDownFrontier := upflagDownFrontier and (high[n-i] < high[n])
        #     upflagUpFrontier0 := upflagUpFrontier0 and (high[n+i] < high[n])
        #     upflagUpFrontier1 := upflagUpFrontier1 and (high[n+1] <= high[n] and high[n+i + 1] < high[n])
        #     upflagUpFrontier2 := upflagUpFrontier2 and (high[n+1] <= high[n] and high[n+2] <= high[n] and high[n+i + 2] < high[n])
        #     upflagUpFrontier3 := upflagUpFrontier3 and (high[n+1] <= high[n] and high[n+2] <= high[n] and high[n+3] <= high[n] and high[n+i + 3] < high[n])
        #     upflagUpFrontier4 := upflagUpFrontier4 and (high[n+1] <= high[n] and high[n+2] <= high[n] and high[n+3] <= high[n] and high[n+4] <= high[n] and high[n+i + 4] < high[n])
        # flagUpFrontier = upflagUpFrontier0 or upflagUpFrontier1 or upflagUpFrontier2 or upflagUpFrontier3 or upflagUpFrontier4

        # upFractal = (upflagDownFrontier and flagUpFrontier)

        # downFractal
        # bool downflagDownFrontier = true
        # bool downflagUpFrontier0 = true
        # bool downflagUpFrontier1 = true
        # bool downflagUpFrontier2 = true
        # bool downflagUpFrontier3 = true
        # bool downflagUpFrontier4 = true

        # for i = 1 to n
        #     downflagDownFrontier := downflagDownFrontier and (low[n-i] > low[n])
        #     downflagUpFrontier0 := downflagUpFrontier0 and (low[n+i] > low[n])
        #     downflagUpFrontier1 := downflagUpFrontier1 and (low[n+1] >= low[n] and low[n+i + 1] > low[n])
        #     downflagUpFrontier2 := downflagUpFrontier2 and (low[n+1] >= low[n] and low[n+2] >= low[n] and low[n+i + 2] > low[n])
        #     downflagUpFrontier3 := downflagUpFrontier3 and (low[n+1] >= low[n] and low[n+2] >= low[n] and low[n+3] >= low[n] and low[n+i + 3] > low[n])
        #     downflagUpFrontier4 := downflagUpFrontier4 and (low[n+1] >= low[n] and low[n+2] >= low[n] and low[n+3] >= low[n] and low[n+4] >= low[n] and low[n+i + 4] > low[n])
        # flagDownFrontier = downflagUpFrontier0 or downflagUpFrontier1 or downflagUpFrontier2 or downflagUpFrontier3 or downflagUpFrontier4

        # downFractal = (downflagDownFrontier and flagDownFrontier)

        # plotshape(downFractal, style=shape.triangledown, location=location.belowbar, offset=-n, color=#F44336, size = size.small)
        # plotshape(upFractal, style=shape.triangleup,   location=location.abovebar, offset=-n, color=#009688, size = size.small)

        self._last = self._fractals[-1]
        self._last_timestamp = timestamp

        return self._fractals
