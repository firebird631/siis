# @date 2018-09-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Bollinger Bands indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n
from talib import BBANDS as ta_BBANDS

import statistics as stat
import numpy as np
import copy

import logging
logger = logging.getLogger('siis.strategy.indicator.bollingerbands')


class BollingerBandsIndicator(Indicator):
    """
    Bollinger Bands indicator
    https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/bollinger-band-width

    TA-lib necessary path :

    In src/ta_func/ta_utility.h :

    --- #define TA_IS_ZERO(v) (((-0.00000001)<v)&&(v<0.00000001))
    +++ #define TA_IS_ZERO(v) (((-0.000000000000000001)<v)&&(v<0.000000000000000001))
    --- #define TA_IS_ZERO_OR_NEG(v) (v<0.00000001)
    +++ #define TA_IS_ZERO_OR_NEG(v) (v<0.000000000000000001)
    """

    __slots__ = '_length', '_prev_bottom', '_prev_ma', '_prev_top', '_last_bottom', '_last_ma', '_last_top', '_bottoms', '_tops', '_mas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, length=20):
        super().__init__("bollingerbands", timeframe)
        
        self._length = length   # periods number

        self._prev_bottom = 0.0
        self._prev_ma = 0.0
        self._prev_top = 0.0

        self._last_bottom = 0.0
        self._last_ma = 0.0
        self._last_top = 0.0

        self._bottoms = np.array([])
        self._mas = np.array([])
        self._tops = np.array([])

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    # @property
    # def step(self):
    #     return self._step
    
    # @step.setter
    # def step(self, step):
    #     self._step = step

    # @property
    # def filtering(self):
    #     return self._filtering

    # @filtering.setter
    # def filtering(self, filtering):
    #     self._filtering = filtering

    @property
    def prev_bottom(self):
        return self._prev_bottom

    @property
    def prev_ma(self):
        return self._prev_ma

    @property
    def prev_top(self):
        return self._prev_top

    @property
    def last_bottom(self):
        return self._last_bottom

    @property
    def last_ma(self):
        return self._last_ma

    @property
    def last_top(self):
        return self._last_top

    @property
    def bottoms(self):
        return self._bottoms
    
    @property
    def tops(self):
        return self._tops
    
    @property
    def mas(self):
        return self._mas

    @staticmethod
    def BB(n, data):
        mm = MM_n(n, data)
        up_bol = copy.deepcopy(mm)
        bottom_bol = copy.deepcopy(mm)

        for (j, d) in enumerate(data):
            i = min(j, n)
            sample = data[j-i:j+1]
            sigma = 0 if j == 0 else np.sqrt(stat.variance(sample, up_bol[j]))
            up_bol[j] = up_bol[j] + 2*sigma
            bottom_bol[j] = bottom_bol[j] - 2*sigma

        return bottom_bol, mm, up_bol

    @staticmethod
    def BB_sf(n: int, data, step=1, filtering=False):
        """
        Calcul des bandes de Bollinger
        N est le nombre de periodes à observer pour calculer la MM et sigma
        step permet de selectionner un echantillon tout les steps, avec filtrage ou non
        Retourne 3 courbes : Bollinger bas ; MM_N ; Bollinger haut, interpolees linéairement
        """
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0, len(data), step)

        mm = MM_n(N, sub_data)
        up_bol = copy.deepcopy(mm)
        bottom_bol = copy.deepcopy(mm)

        for (j, d) in enumerate(sub_data):
            i = min(j, n)
            sample = sub_data[j-i:j+1]
            sigma = 0 if j == 0 else np.sqrt(stat.variance(sample, up_bol[j]))
            up_bol[j] = up_bol[j] + 2*sigma
            bottom_bol[j] = bottom_bol[j] - 2*sigma

        return (np.interp(range(len(data)), t_subdata,bottom_bol),
                np.interp(range(len(data)), t_subdata, mm),
                np.interp(range(len(data)), t_subdata, up_bol))

    def compute(self, timestamp, prices):
        self._prev_top = self._last_top
        self._prev_ma = self._last_ma
        self._prev_bottom = self._last_bottom

        # self._tops, self._mas, self._bottoms = BollingerBandsIndicator.BB(self._length, prices)
        # self._tops, self._mas, self._bottoms = ta_BBANDS(prices*10000.0, timeperiod=self._length, nbdevup=2, nbdevdn=2, matype=0)
        self._tops, self._mas, self._bottoms = ta_BBANDS(prices, timeperiod=self._length, nbdevup=2, nbdevdn=2, matype=0)

        # self._tops *= 0.0001
        # self._mas *= 0.0001
        # self._bottoms *= 0.0001

        self._last_top = self._tops[-1]
        self._last_ma = self._mas[-1]
        self._last_bottom = self._bottoms[-1]

        # used to check with a crypto over BTC if values are the same else need to patch TA-lib
        # if self.timeframe == 3600:
        #     logger.info(prices)
        #     logger.info(self._tops)
        #     logger.info(self._mas)
        #     logger.info(self._bottoms)

        self._last_timestamp = timestamp

        return self._tops, self._mas, self._bottoms
