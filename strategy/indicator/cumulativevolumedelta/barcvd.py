# @date 2024-07-28
# @author Frederic Scherma
# @license Copyright (c) 2024 Dream Overflow
# Bar based Cumulative Volume Delta indicator

from typing import List

from .cvdbase import CumulativeVolumeDeltaBase

from instrument.instrument import TickType
from strategy.indicator.indicator import Indicator
# from database.database import Database

import numpy as np


class BarCumulativeVolumeDelta(CumulativeVolumeDeltaBase):
    """
    Cumulative volume delta indicator based on temporal (timeframe-bar / Candle) series.
    """

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TIMEFRAME | Indicator.BASE_TICKBAR

    def __init__(self, timeframe: float, session):
        super().__init__("barcumulativevolumedelta", timeframe, session)

    def compute(self, timestamp, volumes):
        pass
