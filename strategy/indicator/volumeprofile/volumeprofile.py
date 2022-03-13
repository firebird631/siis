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

# @todo Support of evening session and overnight session.


class BaseVolumeProfileIndicator(Indicator):
    """
    Single or multiple Volume Profile indicator base model.
    """

    __slots__ = '_length', '_sensibility', '_volume_area', '_size', '_vps', '_current', \
        '_session_offset', '_price_precision', '_tick_size', '_range', '_bins'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, name, timeframe, length=10, sensibility=10, volume_area=70):
        super().__init__(name, timeframe)

        self._compute_at_close = True  # only at close

        self._length = length   # number of volumes profiles to keep back
        self._sensibility = sensibility
        self._volume_area = volume_area

        self._session_offset = 0.0

        self._price_precision = 1
        self._tick_size = 1.0

        self._range = (1.0, 1.0)
        self._bins = tuple()

        self._current = None
        self._vps = []

    def setup(self, instrument):
        if instrument is None:
            return

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001

        self._session_offset = instrument.session_offset

    def setup_range(self, instrument, min_price, max_price):
        self._range = (min_price, max_price)
        self._bins = tuple(instrument.adjust_price(price) for price in np.exp(
            np.arange(np.log(min_price), np.log(max_price), self._sensibility * 0.01)))

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def sensibility(self):
        return self._sensibility

    @property
    def range(self):
        return self._range
    
    @property
    def bins(self):
        return self._bins

    @property
    def current(self):
        return self._current

    @property
    def vps(self):
        return self._vps

    def finalize(self, vp):
        """
        Finalize the computation of the last VP and push it.
        Does by update when the last trade timestamp open a new session.
        """
        if vp is None:
            return

        vp.poc = BaseVolumeProfileIndicator.find_poc(vp)

        # volumes arranged by price
        volumes_by_price = BaseVolumeProfileIndicator.sort_volumes_by_price(vp)

        # find peaks and valley
        vp.peaks, vp.valleys = BaseVolumeProfileIndicator.basic_peaks_and_valleys_detection(
            self._bins, self._sensibility, vp)

    #
    # internal computing
    #

    def adjust_price(self, price):
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    def bin_lookup(self, price):
        # idx = int(np.log(price) * self._sensibility)
        
        # if 0 <= idx < len(self._bins):
        #     return self._bins[idx]
        # else:
        #     return None

        if price < self._bins[0]:
            # underflow
            return None

        prev = 0.0

        for b in self._bins:
            if b > price >= prev:
                return prev

            prev = b

        # last bin or overflow
        return self._bins[-1]

    @staticmethod
    def find_poc(vp):
        """
        Detect the price at the max volume.
        """
        poc_price = 0.0
        poc_vol = 0.0

        for b, v in vp.volumes.items():
            if v > poc_vol:
                poc_vol = v
                poc_price = b

        return poc_price

    @staticmethod
    def sort_volumes_by_price(vp):
        return sorted([(b, v) for b, v in vp.volumes.items()], key=lambda x: x[0])

    @staticmethod
    def single_volume_area(vp, volumes_by_price, poc_price, volume_area):
        """
        Simplest method to detect the volume area.
        Starting from the POC goes left and right until having the inner volume reached.
        Its not perfect because it could miss some peaks that will be important to have
        and sometime the best choice might not be try with centered algorithm.
        """
        if not volumes_by_price or not poc_price:
            return 0.0, 0.0

        index = -1

        for i, bv in enumerate(volumes_by_price):
            if bv[0] == poc_price:
                index = i
                break

        if index < 0:
            return 0.0, 0.0

        low_price = 0.0
        high_price = 0.0

        sum_vols = sum(vp.volumes.values())

        in_area = sum_vols * volume_area * 0.01
        out_area = 1.0 - in_area

        left = index
        right = index
        max_index = len(volumes_by_price)-1
        summed = 0.0

        while summed < in_area:
            if left >= 0:
                summed += volumes_by_price[left][1]
                low_price = volumes_by_price[left][0]
                left -= 1

            if right < max_index:
                summed += volumes_by_price[right][1]
                right += 1
                high_price = volumes_by_price[right][0]

            if left < 0 and right > max_index:
                break

        return low_price, high_price

    @staticmethod
    def basic_peaks_and_valleys_detection(src_bins, sensibility, vp):
        """
        Simplest peaks and valleys detection algorithm.
        """
        if not vp or not vp.volumes:
            return [], []

        peaks = []
        valleys = []

        bins = np.array(src_bins)
        volumes = np.zeros(len(src_bins))

        avg = np.average(list(vp.volumes.values()))

        for i, b in enumerate(src_bins):
            if b in vp.volumes:
                volumes[i] = vp.volumes[b]

        # @todo high_region, low_region detection
        sens = sensibility * 0.01 * 10

        last_peak = -1
        last_valley = -1

        for i in range(1, len(volumes)-1):
            v = volumes[i]

            vl = v - v * sens
            vh = v + v * sens

            # peaks
            # if volumes[i] > avg and volumes[i-1] < volumes[i] and volumes[i+1] < volumes[i]:
            #     peaks.append(bins[i])

            if volumes[i-1] < vl and volumes[i+1] < vl and i - last_valley > 1 and i - last_peak > 2:
                peaks.append(bins[i])
                last_peak = i

            # valleys
            # if volumes[i] < avg and volumes[i-1] > volumes[i] and (volumes[i+1] > volumes[i]):# or volumes[i+1] == 0.0):
            #     valleys.append(bins[i])

            if volumes[i-1] > vh and volumes[i+1] > vh and i - last_peak > 1 and i - last_valley > 2:
                valleys.append(bins[i])
                last_valley = i

        return peaks, valleys

    #
    # cache management
    #

    def load(self, strategy_trader, base_timestamp, from_date, to_date=None):
        """
        Load from DB a range of daily volume profile, inclusive.
        """
        self._vps = Database.inst().get_cached_volume_profile(
                strategy_trader.trader().name, strategy_trader.instrument.market_id, strategy_trader.strategy.identifier,
                self._timeframe, from_date, to_date=to_date,
                sensibility=self._sensibility, volume_area=self._volume_area)

        if self._vps:
            if self._vps[-1].timestamp <= base_timestamp < self._vps[-1].timestamp + self._timeframe:
                # current detected
                self._current = self._vps.pop()


class VolumeProfileIndicator(BaseVolumeProfileIndicator):
    """
     Volume Profile indicator based on OHLCs list update.
    """

    def __init__(self, timeframe, length=10, sensibility=10, volume_area=70):
        super().__init__("volumeprofile", timeframe, length, sensibility, volume_area)

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


class TickVolumeProfileIndicator(BaseVolumeProfileIndicator):
    """
    Volume Profile indicator based on tick or trade update.
    """

    def __init__(self, timeframe, length=10, sensibility=10, volume_area=70):
        super().__init__("tickbar-volumeprofile", timeframe, length, sensibility, volume_area)

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


class CompositeVolumeProfile(object):
    """
    Composite volume profile.

    The composite volume profile is managed by a volume profile indicator,
    automatically or manually.

    The timeframe is the base timeframe, not the cumulated duration.
    Then the cumulated duration is timeframe x length.
    """

    __slots__ = '_timeframe', '_length', '_use_current', '_vp', '_volume_profile', \
                '_last_timestamp', '_last_base_timestamp'

    def __init__(self, timeframe, length, volume_profile, use_current=True):
        self._timeframe = timeframe
        self._length = length
        self._use_current = use_current
        
        self._last_timestamp = 0.0
        self._last_base_timestamp = 0.0

        self._volume_profile = volume_profile

        self._vp = VolumeProfile(0, timeframe)

    @property
    def vp(self):
        return self._vp

    def is_update_needed(self, timestamp, partial_update=True):
        """
        Returns True of the close timestamp was reached.

        @param timestamp Current timestamp.
        @param partial_update If True it will return True at each intermediate volume profile realized,
            else it will wait for the length of new volumes profiles completed.
        """
        if partial_update:
            return timestamp >= self._last_base_timestamp + self._timeframe
        else:
            return timestamp >= self._last_base_timestamp + self._timeframe * self._length

    def composite(self, timestamp):
        """
        Build a composite profile of length, eventually use the current volume profile in addiction.
        """
        if self._volume_profile is None or not self._volume_profile.vps:
            return

        volume_profile = self._volume_profile

        base_index = max(-self._length, -len(volume_profile.vps))
        base_timestamp = volume_profile.vps[base_index]

        cvp = VolumeProfile(Instrument.basetime(self._timeframe, base_timestamp), self._timeframe)

        for vp in volume_profile.vps[base_index:]:
            for b, v in vp.volumes.items():
                if b not in cvp.volumes:
                    cvp.volumes[b] = v
                else:
                    cvp.volumes[b] += v

        self._last_base_timestamp = volume_profile.vps[-1].timestamp

        # append current VP
        if self._use_current and volume_profile.current:
            vp = volume_profile.current

            for b, v in vp.volumes.items():
                if b not in cvp.volumes:
                    cvp.volumes[b] = v
                else:
                    cvp.volumes[b] += v

            self._last_base_timestamp = volume_profile.current.timestamp

        self._finalize(volume_profile, cvp)

        self._last_timestamp = timestamp

        return cvp

    #
    # internal methods
    #

    def _finalize(self, volume_profile, vp):
        """
        Finalize the computation of the last VP and push it.
        Does by update when the last trade timestamp open a new session.
        """
        if vp is None:
            return

        vp.poc = BaseVolumeProfileIndicator.find_poc(vp)

        # volumes arranged by price
        volumes_by_price = BaseVolumeProfileIndicator.sort_volumes_by_price(vp)

        # find peaks and valley
        vp.peaks, vp.valleys = BaseVolumeProfileIndicator.basic_peaks_and_valleys_detection(
            volume_profile.bins, volume_profile.sensibility, vp)
