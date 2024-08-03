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

    def __init__(self, timeframe:  float, length:  int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__("barlogvolumeprofile", timeframe, length, sensibility, volume_area)

    # @todo generate
