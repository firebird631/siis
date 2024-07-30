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
import scipy.signal as sg


class VolumeProfileBaseIndicator(Indicator):
    """
    Single or multiple Volume Profile indicator base model.
    It could be composed using the composite volume profile to build exotic durations.

    This indicator is compute at close because :
      - Tick version it can update at each tick or many, there is no limitation
      - Bar version (timeframe or non-temporal) it could only compute at close because it is too complex to withdraw
        the previous volumes at price and update at each bar update until its close.

    @todo Support of evening session and overnight session.
    """

    __slots__ = '_length', '_sensibility', '_volume_area', '_size', '_vps', '_current', \
        '_session_offset', '_price_precision', '_tick_size', '_range', '_bins'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def builder(cls, base_type: int, timeframe: float, **kwargs):
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.volumeprofile import VolumeProfileIndicator
            return VolumeProfileIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.volumeprofile import TickBarVolumeProfileIndicator
            return TickBarVolumeProfileIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.volumeprofile import TickVolumeProfileIndicator
            return TickVolumeProfileIndicator(timeframe, **kwargs)

        return None

    def __init__(self, name: str, timeframe: float, length: int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__(name, timeframe)

        self._compute_at_close = True  # only at close (that mean at each tick or each closed bar)

        self._length = length  # number of volumes profiles to keep back
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

        vp.poc = VolumeProfileBaseIndicator.find_poc(vp)

        # # volumes arranged by price
        # volumes_by_price = VolumeProfileBaseIndicator.sort_volumes_by_price(vp)
        #
        # # find peaks and valley
        # # vp.peaks, vp.valleys = self.basic_peaks_and_valleys_detection(self._bins, self._sensibility, vp)
        # vp.peaks, vp.valleys = self.scipy_peaks_and_valleys_detection(vp)
        #
        # # find the low and high of the volume area
        # vp.low_area, vp.high_area = self.single_volume_area(vp, volumes_by_price, vp.poc)

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

    def single_volume_area(self, vp, volumes_by_price, poc_price):
        """
        Simplest method to detect the volume area.
        Starting from the POC goes left and right until having the inner volume reached.
        It is not perfect because it could miss some peaks that will be important to have
        and sometimes the best choice might not be try with centered algorithm.
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

        in_area = sum_vols * self._volume_area * 0.01
        out_area = 1.0 - in_area

        left = index
        right = index
        max_index = len(volumes_by_price) - 1
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
    def scipy_peaks_and_valleys_detection(vp):
        """
        Scipy find_peaks based peaks and valleys detection algorithm.
        """
        if not vp or not vp.volumes:
            return [], []

        peaks = []
        valleys = []

        # bins = np.array(self._bins)
        # volumes = np.zeros(len(self._bins))

        prices = np.array(list(vp.volumes.keys()))
        weights = np.array(list(vp.volumes.values()))

        # actual version is 1, but more efficient is 2 (to be confirmed with more tests and adjustments)
        VolumeProfileBaseIndicator._find_peaks_and_valleys_sci_peak(weights, prices, peaks, valleys)
        # self._find_peaks_and_valleys_sci_peak2(weights, prices, peaks, valleys)

        return peaks, valleys

    #
    # internal
    #

    @staticmethod
    def basic_peaks_and_valleys_detection(src_bins, sensibility: float, vp):
        """
        Simplest peaks and valleys detection algorithm.
        """
        if not vp or not vp.volumes:
            return [], []

        peaks = []
        valleys = []

        bins = np.array(src_bins)
        volumes = np.zeros(len(src_bins))

        # avg = np.average(list(vp.volumes.values()))

        for i, b in enumerate(src_bins):
            if b in vp.volumes:
                volumes[i] = vp.volumes[b]

        # @todo high_region, low_region detection
        sens = sensibility * 0.01 * 10

        last_peak = -1
        last_valley = -1

        for i in range(1, len(volumes) - 1):
            v = volumes[i]

            vl = v - v * sens
            vh = v + v * sens

            # peaks
            # if volumes[i] > avg and volumes[i-1] < volumes[i] and volumes[i+1] < volumes[i]:
            #     peaks.append(bins[i])

            if volumes[i - 1] < vl and volumes[i + 1] < vl and i - last_valley > 1 and i - last_peak > 2:
                peaks.append(bins[i])
                last_peak = i

            # valleys
            # if volumes[i] < avg and volumes[i-1] > volumes[i] and (volumes[i+1] > volumes[i]):# or volumes[i+1] == 0.0):
            #     valleys.append(bins[i])

            if volumes[i - 1] > vh and volumes[i + 1] > vh and i - last_peak > 1 and i - last_valley > 2:
                valleys.append(bins[i])
                last_valley = i

        return peaks, valleys

    @staticmethod
    def _find_peaks_and_valleys_sci_peak(weights, prices, peaks, valleys):
        """
        Based on scipy find_peaks method.
        """
        l = len(weights)

        distanceP = max(2, l // 6)
        distanceV = max(2, l // 6)

        M = max(weights)

        heightP = M / 4
        heightV = -M / 4

        vs = sg.find_peaks(-weights, heightV, None, distanceV)[0]
        ps = sg.find_peaks(weights, heightP, None, distanceP)[0]

        # index to price
        valleys += [prices[v] for v in vs]
        peaks += [prices[p] for p in ps]

    @staticmethod
    def _find_peaks_and_valleys_sci_peak2(weights, prices, peaks, valleys, n_samples=20):
        """
        Based on scipy find_peaks method. Profile is split with nsamples per buch.
        n_sample=20 seems OK in the first tests with btc.
        """
        def get_pkvl_robust(d):
            l = len(d)
            distanceP = max(2, l // 3)
            distanceV = max(2, l // 3)
            M = max(d)
            heightP = M / 6
            heightV = -M / 6
            vs = sg.find_peaks(-d, heightV, None, distanceV)[0]
            ps = sg.find_peaks(d, heightP, None, distanceP)[0]
            return vs, ps

        def split_by(n):
            l = len(weights)
            cpt = 0
            while (cpt + 2) * n <= l:
                yield weights[cpt * n:(cpt + 1) * n]
                cpt = cpt + 1
            yield weights[cpt * n:]

        vs, ps = np.array([], dtype=int), np.array([], dtype=int)
        for (n, d) in enumerate(split_by(n_samples)):
            m, M = get_pkvl_robust(d)
            vs, ps = np.hstack((vs, m + n * n_samples)), np.hstack((ps, M + n * n_samples))

        # index to price
        valleys += [prices[v] for v in vs]
        peaks += [prices[p] for p in ps]

    #
    # cache management (@todo maybe move to strategy with INDICATOR_BULK signal but its a more hard than soft design...)
    #

    # def load(self, strategy_trader, base_timestamp, from_date, to_date=None):
    #     """
    #     Load from DB a range of daily volume profile, inclusive.
    #     """
    #     self._vps = Database.inst().get_cached_volume_profile(
    #         strategy_trader.trader().name, strategy_trader.instrument.market_id, strategy_trader.strategy.identifier,
    #         self._timeframe, from_date, to_date=to_date,
    #         sensibility=self._sensibility, volume_area=self._volume_area)
    #
    #     if self._vps:
    #         if self._vps[-1].timestamp <= base_timestamp < self._vps[-1].timestamp + self._timeframe:
    #             # current detected
    #             self._current = self._vps.pop()
