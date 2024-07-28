# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Profile indicator and composite

from strategy.indicator.indicator import Indicator
from strategy.indicator.models import VolumeProfile
from instrument.instrument import Instrument

from database.database import Database

from common.utils import truncate

import numpy as np

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator


class TickVolumeProfileIndicator(VolumeProfileBaseIndicator):
    """
    Volume Profile indicator based on tick or trade update.
    """

    def __init__(self, timeframe:  float, length:  int = 10, sensibility: float = 10, volume_area: float = 70):
        super().__init__("tickvolumeprofile", timeframe, length, sensibility, volume_area)

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    def compute(self, timestamp, tick):
        # @todo session_offset, evening/overnight session
        if self._current and tick[0] >= self._current.timestamp + self._timeframe:
            self.finalize(self._current)

            self._vps.append(self._current)
            self._current = None

        if self._current is None:
            basetime = Instrument.basetime(self._timeframe, tick[0])
            self._current = VolumeProfile(basetime, self._timeframe)

        # round price to bin
        lbin = self.bin_lookup(tick[3])

        if lbin:
            if lbin not in self._current.volumes:
                # set volume to the bin
                self._current.volumes[lbin] = tick[4]
            else:
                # or merge
                self._current.volumes[lbin] += tick[4]

        self._last_timestamp = timestamp
