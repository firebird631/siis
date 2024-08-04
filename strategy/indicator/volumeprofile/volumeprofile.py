# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Per tick volume profile indicator

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument, TickType

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator, BidAskLinearScaleDict


class VolumeProfileIndicator(VolumeProfileBaseIndicator):
    """
    Volume Profile indicator based on tick or trade update.
    """

    def __init__(self, timeframe: float,
                 sensibility: int = 1,
                 volume_area: float = 70,
                 detect_peaks_and_valleys: bool = False,
                 tick_scale: float = 1.0):
        super().__init__("volumeprofile", timeframe, sensibility, volume_area, detect_peaks_and_valleys, tick_scale)

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    @classmethod
    def builder(cls, base_type: int, timeframe: float, *args):
        return VolumeProfileIndicator(timeframe, *args)

    def update(self, tick: TickType, finalize: bool):
        """
        Append volumes of the tick to the current volume profile and eventually compute volume area, peaks and valleys.
        If finalize is True close the current volume profile and create a new one.

        @param tick: Tick by tick to process generation
        @param finalize: Set to True when a bar just close
        """
        if self._session_offset or self._session_duration:
            # compute daily base time only if a session is defined
            base_time = Instrument.basetime(Instrument.TF_DAY, tick[0])

            if tick[0] < base_time + self._session_offset:
                # ignored, out of session
                return

            if tick[0] >= base_time + self._session_offset + self._session_duration:
                # ignored, out of session
                return

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

        if finalize:
            self.finalize()

        # retain the last tick timestamp
        self._last_timestamp = tick[0]
