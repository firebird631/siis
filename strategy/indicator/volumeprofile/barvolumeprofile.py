# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Profile indicator per bar

from instrument.instrument import Instrument, Candle
from strategy.indicator.indicator import Indicator

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator, BidAskLinearScaleDict


class BarVolumeProfileIndicator(VolumeProfileBaseIndicator):
    """
    Volume Profile indicator based on OHLCs list update.
    """

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TIMEFRAME | Indicator.BASE_TICKBAR

    def __init__(self,
                 timeframe:  float,
                 sensibility: int = 10,
                 volume_area: float = 70,
                 detect_peaks_and_valleys: bool = False,
                 tick_scale: float = 1.0):
        super().__init__("barvolumeprofile", timeframe, sensibility, volume_area, detect_peaks_and_valleys, tick_scale)

    def update(self, bar: Candle, finalize: bool):
        """
        Append volumes of the bar to the current volume profile and eventually compute volume area, peaks and valleys.
        If finalize is True close the current volume profile and create a new one.

        @param bar: Bar by bar to process generation
        @param finalize: Set to True when a bar just close
        """
        if self._session_offset or self._session_duration:
            # compute daily base time only if a session is defined
            base_time = Instrument.basetime(Instrument.TF_DAY, bar.timestamp)

            if bar.timestamp < base_time + self._session_offset:
                # ignored, out of session
                return

            if bar.timestamp >= base_time + self._session_offset + self._session_duration:
                # ignored, out of session
                return

        if self._current is None:
            if self._timeframe > 0:
                base_time = Instrument.basetime(self._timeframe, bar.timestamp)
            else:
                base_time = bar.timestamp

            self._current = BidAskLinearScaleDict(base_time, self._sensibility,
                                                  self._price_precision, self._tick_size, self._tick_scale)

        # avg price based on HLC3
        hlc3 = (bar.high + bar.low + bar.close) / 3

        # not very important to detail bid/ask volume from a source of bar
        self._current.add_bid(hlc3, bar.volume*0.5)
        self._current.add_ask(hlc3, bar.volume*0.5)

        if finalize:
            self.finalize()

        # retain the last tick timestamp
        self._last_timestamp = bar.timestamp
