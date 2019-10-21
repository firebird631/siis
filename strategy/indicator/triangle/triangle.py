# @date 2018-09-15
# @author Frederic SCHERMA
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Triangle indicator and trend detection indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n

import scipy.stats as st

import numpy as np
import copy
import math


class TriangleIndicator(Indicator):
    """
    Triangle indicator and trend detection.
    """

    __slots__ = '_length', '_split_idx', '_bottom_partial_interp', '_top_partial_interp', '_bottom', '_top'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, length=20):
        super().__init__("triangle", timeframe)

        self._compute_at_close = True  # only at close
        self._length = length   # periods number

        self._split_idx = []
        self._bottom_partial_interp = []
        self._top_partial_interp = []

        self._bottom = []
        self._top = []

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    def bottom(self):
        return self._bottom
    
    @property
    def top(self):
        return self._top

    @staticmethod
    def triangles_reg(bottom, top):
        # On perd la 1ere valeur:
        variations = np.diff(top-bottom)
        inversion_tendance_index = [ i+1 for (i,x) in enumerate( list(variations[1:] * variations[:-1])) if x < 0 ]
        data_splitter = lambda data, split_idx: [data[0:split_idx[0]]] + [ data[split_idx[i]:split_idx[i+1]] for i in range(len(split_idx) - 1) ] + [data[split_idx[-1]:]]

        if not inversion_tendance_index:
            return [], [], []

        split_idx = data_splitter(range(len(bottom)), inversion_tendance_index)
        split_bottom_data, split_top_data = data_splitter(bottom, inversion_tendance_index), data_splitter(top, inversion_tendance_index)

        bottom_partial_interp, top_partial_interp = map(st.linregress, zip(split_idx, split_bottom_data)), map(st.linregress, zip(split_idx, split_top_data))
        return split_idx, bottom_partial_interp, top_partial_interp

    @staticmethod
    def triangles_reg_sf(bottom, top, step=1, filtering=False):
        # On perd la 1ere valeur:
        variations = np.diff(down_sample(top[::step], step)- down_sample(bottom[::step], step)) if filtering else np.diff( top[::step]-bottom[::step])
        inversion_tendance_index = [ i+1 for (i,x) in enumerate( list(variations[1:] * variations[:-1])) if x < 0 ]
        data_splitter = lambda data, split_idx: [data[0:split_idx[0]]] + [ data[split_idx[i]:split_idx[i+1]] for i in range(len(split_idx) - 1) ] + [data[split_idx[-1]:]]

        if not inversion_tendance_index:
            return [], [], []

        split_idx = data_splitter(range(len(bottom)), inversion_tendance_index)
        split_bottom_data, split_top_data = data_splitter(bottom, inversion_tendance_index), data_splitter(top, inversion_tendance_index)

        bottom_partial_interp, top_partial_interp = map(st.linregress, zip(split_idx, split_bottom_data)), map(st.linregress, zip(split_idx, split_top_data))
        return split_idx, bottom_partial_interp, top_partial_interp

    def compute(self, timestamp, bottom, top):
        self._split_idx, bottom_partial_interp, top_partial_interp = TriangleIndicator.triangles_reg(bottom, top)  # , self._step, self._filtering)

        self._bottom_partial_interp = list(bottom_partial_interp)
        self._top_partial_interp = list(top_partial_interp)

        self._last_timestamp = timestamp

        return self._split_idx, self._bottom_partial_interp, self._top_partial_interp

    def triangles(self):
        self._bottom = np.array([0.0]*2*len(self._bottom_partial_interp))
        self._top = np.array([0.0]*2*len(self._top_partial_interp))

        j = 0
        for i in range(0, len(self._bottom_partial_interp)):
            r = self._split_idx[i]
            l = len(r)
            b = self._bottom_partial_interp[i]

            if math.isnan(b.intercept) or math.isnan(b.slope):
                continue

            self._bottom[j] = (r[0], b.intercept)
            self._bottom[j+1] = (r[-1], b.intercept + b.slope * l)

            j += 2

        j = 0
        for i in range(0, len(self._top_partial_interp)):
            r = self._split_idx[i]
            l = len(r)
            t = self._top_partial_interp[i]

            if math.isnan(t.intercept) or math.isnan(t.slope):
                continue

            self._top[j] = (r[0], t.intercept)
            self._top[j+1] = (r[-1], t.intercept + t.slope * l)

            j += 2

        return self._bottom, self._top
