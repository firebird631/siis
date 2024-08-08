# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Per bar logarithmic volume profile indicator.

from strategy.indicator.indicator import Indicator
from strategy.indicator.volumeprofile.volumeprofilebase import LogVolumeProfileBaseIndicator


class BarLogVolumeProfileIndicator(LogVolumeProfileBaseIndicator):
    """
    Per bar logarithmic volume profile indicator.
    """

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TIMEFRAME | Indicator.BASE_TICKBAR

    def __init__(self, timeframe: float,
                 history_size: int = 10,
                 sensibility: int = 10,
                 value_area: float = 70,
                 detect_peaks_and_valleys: bool = False,
                 tick_scale: float = 1.0):
        super().__init__("barlogvolumeprofile", timeframe, history_size, sensibility, value_area, detect_peaks_and_valleys, tick_scale)

    # @todo generate
