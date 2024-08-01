# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Profile indicator and composite

from strategy.indicator.indicator import Indicator
from strategy.indicator.models import VolumeProfile
from instrument.instrument import Instrument, TickType

from database.database import Database

from common.utils import truncate

import numpy as np

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator, BidAskLinearScaleDict


class TickVolumeProfileIndicator(VolumeProfileBaseIndicator):
    """
    Volume Profile indicator based on tick or trade update.
    """

    def __init__(self, timeframe:  float, length:  int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__("tickvolumeprofile", timeframe, length, sensibility, volume_area)

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    def compute(self, timestamp: float, tick: TickType):
        if self._session_offset or self._session_duration:
            base_time = Instrument.basetime(Instrument.TF_DAY, timestamp)
            if timestamp < base_time + self._session_offset:
                # ignored, out of session
                return

            if timestamp >= base_time + self._session_offset + self._session_duration:
                # ignored, out of session
                return

        if self._current and tick[0] >= self._current.timestamp + self._timeframe:
            self.finalize()

        if self._current is None:
            if self._timeframe > 0:
                base_time = Instrument.basetime(self._timeframe, tick[0])
            else:
                base_time = tick[0]

            self._current = BidAskLinearScaleDict(base_time, self._sensibility,
                                                  self._price_precision, self._tick_size, self._tick_scale)

        # -1  for bid, 1 for ask, or 0 if no info
        if tick[5] < 0:
            self._current.add_bid(tick[3], tick[4])
        elif tick[5] > 0:
            self._current.add_ask(tick[3], tick[4])
        else:
            self._current.add_bid(tick[3], tick[4]*0.5)
            self._current.add_ask(tick[3], tick[4]*0.5)

        self._last_timestamp = timestamp
