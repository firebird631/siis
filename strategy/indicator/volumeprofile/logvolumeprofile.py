# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Logarithmic Volume Profile indicator based on OHLCs list update.

from strategy.indicator.indicator import Indicator
from strategy.indicator.models import VolumeProfile
from instrument.instrument import Instrument

from database.database import Database

from common.utils import truncate

import numpy as np

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator


class LogVolumeProfileIndicator(VolumeProfileBaseIndicator):
    """
    Logarithmic Volume Profile indicator based on OHLCs list update.
    """

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    def __init__(self, timeframe: float,
                 history_size: int = 10,
                 sensibility: int = 10,
                 value_area: float = 70,
                 detect_peaks_and_valleys: bool = False,
                 tick_scale: float = 1.0):
        super().__init__("logvolumeprofile", timeframe, history_size, sensibility, value_area,
                         detect_peaks_and_valleys, tick_scale)

    # @todo generate
