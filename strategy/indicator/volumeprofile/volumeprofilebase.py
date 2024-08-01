# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Profile indicator and composite

import math
from typing import Optional, List, Tuple

from instrument.instrument import Instrument
from strategy.indicator.indicator import Indicator

from common.utils import truncate

import numpy as np
import scipy.signal as sg


class BidAskVPScale(object):
    """
    Base model for a bid/ask volume at bin price. Each subclass must implement its own method but respect the
    add_bid, add_ask, bid, ask, volume methods
    The at method must return the correct index into the bins array.
    Bins are price ascending ordered.
    Could be better to trim left and right 0 areas.
    """

    _bins: Optional[np.array]

    _min_price: float
    _max_price: float

    _sensibility: int

    _price_precision: int
    _tick_size: float
    _tick_scale: float

    _half_size: int

    _poc_idx: int
    _poc_vol: float

    _peaks_idx: Optional[np.array]
    _valleys_idx: Optional[np.array]

    _val_idx: int
    _vah_idx: int

    def __init__(self, sensibility: int, tick_scale: float = 1.0):
        self._bins = None       # 2d array of volume bid/ask, per bin price

        self._min_price = 0.0   # bin price of at index 0 of bins (included from bins)
        self._max_price = 0.0   # bin price of at last index of bins + one step (excluded from bins)

        self._sensibility = sensibility

        self._price_precision = 8
        self._tick_size = 0.00000001

        self._tick_scale = tick_scale

        self._half_size = 0
        self._poc_idx = -1         # real-time POC bin index
        self._poc_vol = 0.0

        self._peaks_idx = None
        self._valleys_idx = None

        self._val_idx = -1
        self._vah_idx = -1

    def setup(self, instrument: Instrument):
        """
        Setup some constant from instrument.
        The tick size is scaled by the tick_scale factor.
        """
        if instrument is None:
            return

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001 * self._tick_scale

    def adjust_price(self, price: float) -> float:
        """
        Adjust the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    def at(self, price: float) -> Tuple[float, int]:
        """Volume and index at price. Resize as necessary"""
        return 0.0, -1

    def price_at(self, idx: int) -> float:
        """Price at index. Only getter, does not resize if not exists"""
        return 0.0

    def volume_at(self, idx: int) -> float:
        """Volume bid+ask at index. Only getter, does not resize if not exists"""
        return 0.0

    def add_bid(self, price: float, volume: int):
        base_price, idx = self.at(price)
        self._bins[0, idx] += volume
        self._update_poc(base_price, idx)

    def add_ask(self, price: float, volume: int):
        base_price, idx = self.at(price)
        self._bins[1, idx] += volume
        self._update_poc(base_price, idx)

    def bid(self, price: float) -> float:
        base_price, idx = self.at(price)
        return self._bins[0, idx]

    def ask(self, price: float) -> float:
        base_price, idx = self.at(price)
        return self._bins[1, idx]

    def volume(self, price: float) -> float:
        base_price, idx = self.at(price)
        return self._bins[0, idx] + self._bins[1, idx]

    #
    # helpers
    #

    def consolidate(self):
        """
        Trim left and right empty bins. Bin are always price ascending ordered
        The POC index is adjusted. But VA, peaks and valleys must be defined after that.
        """
        left = 0
        for i in range(0, self._bins.shape[1]):
            if self._bins[i, 0] + self._bins[i, 1] != 0.0:
                break
            left += 1

        right = self._bins.shape[1] - 1
        for i in range(self._bins.shape[1]-1, 0, -1):
            if self._bins[i, 0] + self._bins[i, 1] != 0.0:
                break
            right -= 1

        if left > 0 or right < self._bins.shape[1] - 1:
            self._bins = self._bins[left:right]

            # adjust POC index (others are computed after trim_bins)
            self._poc_idx -= left

    #
    # POC volume
    #

    def _update_poc(self, base_price: float, idx):
        volume = self._bins[0, idx] + self._bins[1, idx]
        if volume > self._poc_vol:
            self._poc_vol = volume
            self._poc_idx = idx

    def poc_idx(self) -> int:
        return self._poc_idx

    def poc_price(self) -> float:
        # avg price (base bin price + half of sensibility)
        if self._poc_idx >= 0:
            return self.price_at(self._poc_idx) + self._sensibility * 0.5
        else:
            return 0.0

    def poc_volume(self) -> float:
        return self._poc_vol

    #
    # volume area
    #

    def set_va_idx(self, val_idx: int, vah_idx: int):
        self._val_idx = val_idx
        self._vah_idx = vah_idx

    def val_idx(self) -> int:
        return self._val_idx

    def vah_idx(self) -> int:
        return self._vah_idx

    def val_price(self) -> float:
        return self.price_at(self._val_idx) if self._val_idx >= 0 else 0.0

    def vah_price(self) -> float:
        return self.price_at(self._vah_idx) if self._vah_idx >= 0 else 0.0

    #
    # peaks & valleys
    #

    def set_peaks_idx(self, ps: np.array):
        self._peaks_idx = ps

    def set_valleys_idx(self, vs: np.array):
        self._valleys_idx = vs

    @property
    def peaks_idx(self) -> np.array:
        return self._peaks_idx

    @property
    def valleys_idx(self) -> np.array:
        return self._valleys_idx

    @property
    def peaks_prices(self) -> List[float]:
        return [self.price_at(idx) for idx in self._peaks_idx]

    @property
    def valleys_prices(self) -> List[float]:
        return [self.price_at(idx) for idx in self._valleys_idx]


class BidAskPointScale(BidAskVPScale):
    """
    Dynamic array with bid/ask at price. Each bin have a width of sensibility parameter.
    Initial array is empty. It is allocated with the first price/volume.
    The initial half_size parameter is used to growth the array in both direction.
    If a new price is outside the range the array is increased into both direction of an integer scale of half_size.
    """

    _growth_size: int

    def init(self, price: float, half_size: int = 10):
        # init bins with 10 bin below (including) price and 10 above (excluding)
        adj_price = self.adjust_price(price)

        base_price = int(adj_price / self._sensibility) * self._sensibility

        self._min_price = base_price - half_size * self._sensibility
        self._max_price = base_price + half_size * self._sensibility

        # simply alloc with zeros
        self._bins = np.zeros((2, 2 * half_size))
        self._half_size = half_size

        # growth size to initial size
        self._growth_size = half_size

    def realloc(self, new_half_size: int):
        if new_half_size > self._half_size:
            org_bins = self._bins
            ofs = new_half_size - self._half_size

            self._bins = np.zeros((2, 2 * new_half_size))

            # copy
            for i in range(0, self._half_size*2):
                self._bins[0, i+ofs] = org_bins[0, i]
                self._bins[1, i+ofs] = org_bins[1, i]

            self._min_price -= ofs * self._sensibility
            self._max_price += ofs * self._sensibility

            self._half_size = new_half_size

    def price_at(self, idx: int) -> float:
        return min(self._min_price + idx * self._sensibility, self._max_price)

    def volume_at(self, idx: int) -> float:
        if idx < self._bins.shape[1]:
            return self._bins[0, idx] + self._bins[1, idx]

        return 0.0

    def at(self, price: float):
        adj_price = self.adjust_price(price)

        if not self._half_size:
            self.init(price)

        if adj_price < self._min_price:
            # underflow
            new_half_size = self._half_size + math.ceil((self._min_price - adj_price) / (
                    self._growth_size * self._sensibility)) * self._growth_size
            self.realloc(new_half_size)

        base_price = int(adj_price / self._sensibility) * self._sensibility

        if base_price >= self._max_price:
            # overflow
            new_half_size = self._half_size + math.ceil((adj_price - self._max_price) / (
                    self._growth_size * self._sensibility)) * self._growth_size
            self.realloc(new_half_size)

        index = int((base_price - self._min_price) // self._sensibility)
        return base_price, index


class VolumeProfileBaseIndicator(Indicator):
    """
    Single or multiple Volume Profile indicator base model.
    It could be composed using the composite volume profile to build exotic durations.

    This indicator is "compute-at-close" because :
      - Tick version it can update at each tick or many, there is no limitation
      - Bar version (timeframe or non-temporal) it could only compute at close because it is too complex to withdraw
        the previous volumes at price and update at each bar update until its close.

    There is two mode, one for computing at each bar close, another to compute at each tick.
    The first can work with adaptive logarithmic bins. It is adapted to high amplitude bars because n points will
    not represent the same changes in percentage.
    But because of some markets (CFD, Futures) are priced in change per points or tick a logarithmic method could not
    be optimal. And for highly volatile cryptocurrencies it could be interesting.

    @note The per point (x sensibility factor) is the first realized.
    """

    __slots__ = '_length', '_sensibility', '_volume_area', '_size', '_vps', '_current', \
        '_session_offset', '_session_duration', '_price_precision', '_tick_size', '_bins'

    _vps: List[BidAskVPScale]
    _current: Optional[BidAskVPScale]

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def builder(cls, base_type: int, timeframe: float, **kwargs):
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.volumeprofile.volumeprofile import VolumeProfileIndicator
            return VolumeProfileIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.volumeprofile.tickbarvolumeprofile import TickBarVolumeProfileIndicator
            return TickBarVolumeProfileIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.volumeprofile.tickvolumeprofile import TickVolumeProfileIndicator
            return TickVolumeProfileIndicator(timeframe, **kwargs)

        return None

    def __init__(self, name: str, timeframe: float, length: int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__(name, timeframe)

        self._compute_at_close = True  # only at close (that mean at each tick or each closed bar)

        self._length = length  # number of volumes profiles to keep back
        self._sensibility = sensibility
        self._volume_area = volume_area

        self._session_offset = 0.0    # 0 means starts at 00:00 UTC
        self._session_duration = 0.0  # 0 means full day

        self._price_precision = 1
        self._tick_size = 1.0

        self._current = None
        self._vps = []

    def setup(self, instrument):
        if instrument is None:
            return

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001

        self._session_offset = instrument.session_offset
        self._session_duration = instrument.session_duration

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
    def current(self):
        return self._current

    @property
    def vps(self):
        return self._vps

    def finalize(self):
        """
        Finalize the computation of a volume-profile by computing the VAH, VAL and finding peaks and valleys.
        Does by update when the last trade timestamp open a new session.
        """
        if self._current is None:
            return

        # find peaks and valley
        # # vp.peaks, vp.valleys = self._asic_peaks_and_valleys_detection(self._bins, self._sensibility, vp)
        self._current.peaks, self._current.valleys = self._scipy_peaks_and_valleys_detection(self._current)

        # # volumes arranged by price
        # volumes_by_price = VolumeProfileBaseIndicator._sort_volumes_by_price(self._current)

        # @todo update because now have bin ordered
        # find the low and high of the volume area
        # val_idx, vah_idx = self._single_volume_area(vp, volumes_by_price, vp.poc)
        # self._current.set_va_idx(val_idx, vah_idx)

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

    #
    # volume area
    #

    # @staticmethod
    # def _sort_volumes_by_price(vp):
    #     return sorted([(b, v) for b, v in vp.volumes.items()], key=lambda x: x[0])

    def _single_volume_area(self, vp, volumes_by_price, poc_price):
        """
        Simplest method to detect the volume area.
        Starting from the POC goes left and right until having the inner volume reached.
        It is not perfect because it could miss some peaks that will be important to have
        and sometimes the best choice might not be tried with centered algorithm.
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

    #
    # peaks and valleys
    #

    @staticmethod
    def _scipy_peaks_and_valleys_detection(vp: BidAskVPScale):
        """
        Scipy find_peaks based peaks and valleys detection algorithm.
        """
        if not vp or not vp.volumes:
            return [], []

        # bins = np.array(self._bins)
        # volumes = np.zeros(len(self._bins))

        prices = np.array(  list(vp.volumes.keys()))
        weights = np.array(list(vp.volumes.values()))

        # actual version is 1, but more efficient is 2 (to be confirmed with more tests and adjustments)
        ps, vs = VolumeProfileBaseIndicator._find_peaks_and_valleys_sci_peak(weights)
        # self._find_peaks_and_valleys_sci_peak2(weights, prices, ps, vs)

        vp.set_peaks_idx(ps)
        vp.set_valleys_idx(vs)

        # # index to price
        # return [vp.price_at(p) for p in ps], [vp.price_at(v) for v in vs]

    @staticmethod
    def _basic_peaks_and_valleys_detection(src_bins, sensibility: float, vp):
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
    def _find_peaks_and_valleys_sci_peak(weights):
        """
        Based on scipy find_peaks method.
        @todo Could compute height with mean + stddev
        """
        l = len(weights)

        distanceP = max(2, l // 6)
        distanceV = max(2, l // 6)

        M = max(weights)

        heightP = M / 4
        heightV = -M / 4

        vs = sg.find_peaks(-weights, heightV, None, distanceV)[0]
        ps = sg.find_peaks(weights, heightP, None, distanceP)[0]

        return ps, vs

    @staticmethod
    def _find_peaks_and_valleys_sci_peak_adv(weights, n_samples=20):
        """
        Based on scipy find_peaks method. Profile is split with nsamples per buck.
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

        return ps, vs

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


class LogVolumeProfileBaseIndicator(VolumeProfileBaseIndicator):
    """
    Logarithmic version of the volume profile. @see VolumeProfileBaseIndicator.

    @todo
    """

    __slots__ = '_sensibility'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def builder(cls, base_type: int, timeframe: float, **kwargs):
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.volumeprofile.logvolumeprofile import LogVolumeProfileIndicator
            return LogVolumeProfileIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.volumeprofile.logtickbarvolumeprofile import LogTickBarVolumeProfileIndicator
            return LogTickBarVolumeProfileIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.volumeprofile.logtickvolumeprofile import LogTickVolumeProfileIndicator
            return LogTickVolumeProfileIndicator(timeframe, **kwargs)

        return None

    def __init__(self, name: str, timeframe: float, length: int = 10, sensibility: int = 10, volume_area: float = 70):
        super().__init__(name, timeframe)

    def bin_lookup(self, price):
        """Works for logarithmic bins"""
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
