# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Profile indicator and composite

from instrument.instrument import Instrument

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator, BidAskLinearScaleDict


class TickBarVolumeProfileIndicator(VolumeProfileBaseIndicator):
    """
    Volume Profile indicator based on OHLCs list update.
    @todo
    """

    def __init__(self, timeframe:  float, length: int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__("volumeprofile", timeframe, length, sensibility, volume_area)

    def retrieve_bar_index(self, timestamps):
        from_idx = -1

        for i, ts in enumerate(reversed(timestamps)):
            if self._last_timestamp > ts:
                break

            from_idx = -i - 1

        return from_idx

    def compute(self, timestamp, timestamps, highs, lows, closes, volumes):
        # only update at close, no overwrite
        delta = self.retrieve_bar_index(timestamps)

        # base index
        num = len(timestamps)

        for b in range(num + delta, num):
            # ignore non closed candles
            if timestamp < timestamps[b] + self._timeframe:
                break

            if self._session_offset or self._session_duration:
                base_time = Instrument.basetime(Instrument.TF_DAY, timestamp)
                if timestamp < base_time + self._session_offset:
                    # ignored, out of session
                    return

                if timestamp >= base_time + self._session_offset + self._session_duration:
                    # ignored, out of session
                    return

            if self._current and timestamps[b] >= self._current.timestamp + self._timeframe:
                self.finalize()

            if self._current is None:
                if self._timeframe > 0:
                    base_time = Instrument.basetime(self._timeframe, timestamps[b])
                else:
                    base_time = timestamps[b]

                self._current = BidAskLinearScaleDict(base_time, self._sensibility,
                                                      self._price_precision, self._tick_size, self._tick_scale)

            # avg price based on HLC3
            hlc3 = (highs[b] + lows[b] + closes[b]) / 3

            # not very important to detail bid/ask volume from a source of bar
            self._current.add_bid(hlc3, volumes[b]*0.5)
            self._current.add_ask(hlc3, volumes[b]*0.5)

            self._last_timestamp = timestamp
