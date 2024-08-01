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

    def __init__(self, timeframe:  float, length: int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__("logvolumeprofile", timeframe, length, sensibility, volume_area)

    def compute(self, timestamp, timestamps, highs, lows, closes, volumes):
        # only update at close, no overwrite
        delta = min(int((timestamp - self._last_timestamp) / self._timeframe) + 1, len(timestamps))

        # base index
        num = len(timestamps)

        for b in range(num-delta, num):
            # ignore non closed candles
            if timestamp < timestamps[b] + self._timeframe:
                break

            # for any new candles
            if self._current and timestamps[b] >= self._current.timestamp + self._timeframe:
                self.finalize(self._current)

                self._vps.append(self._current)
                self._current = None

            if self._current is None:
                basetime = Instrument.basetime(self._timeframe, timestamps[b])
                self._current = VolumeProfile(basetime, self._timeframe)

            # avg price based on HLC3
            hlc3 = (highs[b] + lows[b] + closes[b]) / 3

            # round price to bin
            lbin = self.bin_lookup(hlc3)

            if lbin:
                if lbin not in self._current.volumes:
                    # set volume to the bin
                    self._current.volumes[lbin] = volumes[b]
                else:
                    # or merge
                    self._current.volumes[lbin] += volumes[b]

        self._last_timestamp = timestamp
