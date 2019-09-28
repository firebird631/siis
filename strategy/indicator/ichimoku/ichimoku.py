# @date 2019-09-11
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# @brief Ichimoku Kinko Hyo indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MMexp_n, MM_n
from talib import MIN as ta_MIN, MAX as ta_MAX, MIDPRICE as ta_MIDPRICE

import numpy as np


class IchimokuIndicator(Indicator):
    """
    Ichimoku Kinko Hyo indicator
    https://fr.wikipedia.org/wiki/Ichimoku_Kinko_Hyo

    Take care using results than :
        - Senkou span A and senkou span B are shift in futur by kijun sen length (26)
        - Chikou span is shift in past by kiju sen length (26)
        - Tenkan sen and kiju sen are aligned to initial data
    """

    __slots__ = '_tenkan_sen_l', '_kijun_sen_l', '_senkou_span_b_l', '_tenkans' ,'_kijuns', '_ssas', '_ssbs', '_chikous', \
        '_prev_tenkan', '_last_tenkan', '_prev_kijun', '_last_kijun', '_trmax_h', '_trmin_l', '_krmax_h', '_krmin_l', '_sbrmax_h', '_sbrmin_l'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, tenkan_sen_l=9, kijun_sen_l=26, senkou_span_b_l=52):
        super().__init__("ichimoku", timeframe)

        self._tenkan_sen_l = tenkan_sen_l    # tenkan sen periods number
        self._kijun_sen_l = kijun_sen_l      # kijun sen periods number
        self._senkou_span_b_l = senkou_span_b_l  # senkou span B periods number

        self._tenkans = np.empty(0)
        self._kijuns = np.empty(0)

        self._ssas = np.empty(0)
        self._ssbs = np.empty(0)

        self._chikous = np.empty(0)

        self._prev_tenkan = 0.0
        self._last_tenkan = 0.0

        self._prev_kijun = 0.0
        self._last_kijun = 0.0

        self._trmax_h = np.empty(0)
        self._trmin_l = np.empty(0)

        self._krmax_h = np.empty(0)
        self._krmin_l = np.empty(0)

        self._sbrmax_h = np.empty(0)
        self._sbrmin_l = np.empty(0)

    @property
    def tenkan_sen_l(self):
        return self._tenkan_sen_l

    @tenkan_sen_l.setter
    def tenkan_sen_l(self, length):
        self._tenkan_sen_l = length

    @property
    def kijun_sen_l(self):
        return self._kijun_sen_l
    
    @kijun_sen_l.setter
    def kijun_sen_l(self, length):
        self._kijun_sen_l = length

    @property
    def senkou_span_b_l(self):
        return self._senkou_span_b_l
    
    @senkou_span_b_l.setter
    def senkou_span_b_l(self, length):
        self._senkou_span_b_l = length

    @property
    def tenkans(self):
        return self._tenkans

    @property
    def kijuns(self):
        return self._kijuns

    @property
    def ssas(self):
        return self._ssas

    @property
    def ssbs(self):
        return self._ssbs

    @property
    def chikous(self):
        return self._chikous

    @property
    def prev_tenkan(self):
        return self._prev_tenkan

    @property
    def last_tenkan(self):
        return self._last_tenkan

    @property
    def prev_kijun(self):
        return self._prev_kijun

    @property
    def last_kijun(self):
        return self._last_kijun

    @staticmethod
    def rolling_min(array, window, out):
        # need at least window data
        for i in range(0, window):
            out[i] = 0.0

        for i in range(window, len(array), 1):
            out[i] = np.amin(array[i-window:i])

    @staticmethod
    def rolling_max(array, window, out):
        # need at least window data
        for i in range(0, window):
            out[i] = 0.0

        for i in range(window, len(array), 1):
            out[i] = np.amax(array[i-window:i])

    def compute(self, timestamp, high, low, close):
        self._prev_tenkan = self._last_tenkan
        self._prev_kijun = self._last_kijun

        n = len(high)

        # # resize temporary arrays
        # if len(self._trmax_h) != n:
        #     self._trmax_h = np.zeros(n)
        #     self._trmin_l = np.zeros(n)

        #     self._krmax_h = np.zeros(n)
        #     self._krmin_l = np.zeros(n)

        #     self._sbrmax_h = np.zeros(n)
        #     self._sbrmin_l = np.zeros(n)

        #
        # tenkan-sen - conversion line (window of 9)
        #

        # IchimokuIndicator.rolling_max(high, self._tenkan_sen_l, self._trmax_h)
        # IchimokuIndicator.rolling_min(low, self._tenkan_sen_l, self._trmin_l)

        # self._tenkans = (self._trmax_h + self._trmin_l) * 0.5
        self._tenkans = ta_MIDPRICE(high, low, self._tenkan_sen_l)

        #
        # kijun-sen - base line (window of 9)
        #

        # IchimokuIndicator.rolling_max(high, self._kijun_sen_l, self._krmax_h)
        # IchimokuIndicator.rolling_min(low, self._kijun_sen_l, self._krmin_l)

        # self._kijuns = (self._krmax_h + self._krmin_l) * 0.5
        self._kijuns = ta_MIDPRICE(high, low, self._kijun_sen_l)

        #
        # senkou span A - leading span A
        #

        # must be considered as shifted in futur (26)
        self._ssas = (self._tenkans + self._kijuns) * 0.5

        #
        # senkou span B - leading span B
        #

        # IchimokuIndicator.rolling_max(high, self._senkou_span_b_l, self._sbrmax_h)
        # IchimokuIndicator.rolling_min(low, self._senkou_span_b_l, self._sbrmin_l)

        # # must be considered as shifted in futur (26)
        # self._ssbs = (self._sbrmax_h + self._sbrmin_l) * 0.5
        self._ssbs = ta_MIDPRICE(high, low, self._senkou_span_b_l)

        #
        # chikou span - lagging span (shifted in past)
        #

        # self._chikous = np.array(close)

        self._last_tenkan = self._tenkans[-1]
        self._last_kijun = self._kijuns[-1]
        self._last_timestamp = timestamp

        return self._tenkans, self._kijuns, self._ssas, self._ssbs, self._chikous
