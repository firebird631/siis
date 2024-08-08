# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Profile indicator and composite

import math

from typing import Optional, List, Union, Dict, Tuple

from strategy.indicator.indicator import Indicator

from common.utils import truncate

import numpy as np
import scipy.signal as sg

from strategy.indicator.models import VolumeProfile

import logging
logger = logging.getLogger('siis.strategy')


class BidAskLinearScaleArray(object):
    """
    Dynamic array with bid/ask at price. Each bin have a width of sensibility parameter.
    Initial array is empty. It is allocated with the first price/volume.
    The initial half_size parameter is used to growth the array in both direction.
    If a new price is outside the range the array is increased into both direction of an integer scale of half_size.

    The at method must return the correct index into the bins array.
    Bins are price ascending ordered.
    Could be better to trim left and right 0 areas.

    Shape is 2, width but performance are better in the other way. But finally it is more usable to have linear arrays.
    """

    _growth_size: int

    _timestamp: float

    _bins: Union[None, np.array]

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

    _consolidated: bool

    def __init__(self, timestamp: float, sensibility: int,
                 price_precision: int = 8, tick_size: float = 0.00000001,
                 tick_scale: float = 1.0):
        self._timestamp = timestamp
        self._bins = None       # 2d array of volume bid/ask, per bin price

        self._min_price = 0.0   # bin price of at index 0 of bins (included from bins)
        self._max_price = 0.0   # bin price of at last index of bins + one step (excluded from bins)

        self._sensibility = sensibility

        self._price_precision = price_precision or 8
        self._tick_size = (tick_size or 0.00000001) * tick_scale

        self._tick_scale = tick_scale

        self._half_size = 0
        self._poc_idx = -1         # real-time POC bin index
        self._poc_vol = 0.0

        self._peaks_idx = None
        self._valleys_idx = None

        self._val_idx = -1
        self._vah_idx = -1

        self._consolidated = False

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

        # reset state
        self._consolidated = False

    def realloc(self, new_half_size: int):
        if new_half_size > self._half_size:
            if self._consolidated:
                # no way ton resize once closed
                return

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

    def adjust_price(self, price: float) -> float:
        """
        Adjust the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    @property
    def timestamp(self) -> float:
        return self._timestamp

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

    def _update_poc(self, idx):
        volume = self._bins[0, idx] + self._bins[1, idx]
        if volume > self._poc_vol:
            self._poc_vol = volume
            self._poc_idx = idx

    def as_dict(self) -> Dict[float, Tuple[float, float]]:
        return {}  # @todo

    def price_at(self, idx: int) -> float:
        return min(self._min_price + idx * self._sensibility, self._max_price)

    def volume_at(self, idx: int) -> float:
        if idx < self._bins.shape[1]:
            return self._bins[0, idx] + self._bins[1, idx]

        return 0.0

    def add_bid(self, price: float, volume: float):
        base_price, idx = self.at(price)
        self._bins[0, idx] += volume
        self._update_poc(idx)

    def add_ask(self, price: float, volume: float):
        base_price, idx = self.at(price)
        self._bins[1, idx] += volume
        self._update_poc(idx)

    def bid(self, price: float) -> float:
        base_price, idx = self.at(price)
        return self._bins[0, idx]

    def ask(self, price: float) -> float:
        base_price, idx = self.at(price)
        return self._bins[1, idx]

    def volume(self, price: float) -> float:
        base_price, idx = self.at(price)
        return self._bins[0, idx] + self._bins[1, idx]

    def prices_array(self) -> np.array:
        """Prices array ordered by ascending"""
        return self._bins[0]

    def volumes_array(self) -> np.array:
        """Volumes array ordered by ascending price"""
        return self._bins[1]

    def consolidate(self):
        """
        Trim left and right empty bins. Bin are always price ascending ordered
        The POC index is adjusted. But VA, peaks and valleys must be defined after that.
        """
        if self._consolidated:
            return

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

        self._consolidated = True

    #
    # POC volume
    #

    @property
    def poc_idx(self) -> int:
        return self._poc_idx

    def poc_price(self) -> float:
        # avg price (base bin price + half of sensibility)
        if self._poc_idx >= 0:
            return self.price_at(self._poc_idx)  # + self._sensibility * 0.5
        else:
            return 0.0

    @property
    def poc_volume(self) -> float:
        return self._poc_vol

    #
    # volume area
    #

    def set_va_idx(self, val_idx: int, vah_idx: int):
        self._val_idx = val_idx
        self._vah_idx = vah_idx

    @property
    def val_idx(self) -> int:
        return self._val_idx

    @property
    def vah_idx(self) -> int:
        return self._vah_idx

    def val_price(self) -> float:
        return self.price_at(self._val_idx)  # + self._sensibility * 0.5 if self._val_idx >= 0 else 0.0

    def vah_price(self) -> float:
        return self.price_at(self._vah_idx)  # + self._sensibility * 0.5 if self._vah_idx >= 0 else 0.0

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

    def peaks_prices(self) -> List[float]:
        return [self.price_at(idx) for idx in self._peaks_idx]

    def valleys_prices(self) -> List[float]:
        return [self.price_at(idx) for idx in self._valleys_idx]


class BidAskLinearScaleDict(object):
    """
    Dict with bid/ask at price. Each bin have a width of sensibility parameter.
    Initial dict is empty.

    @note Dict is more efficient in Python than dynamic array. So let's choose this method.
    """

    _timestamp: float

    _bins: Union[None, dict]

    _min_price: float
    _max_price: float

    _sensibility: int

    _price_precision: int
    _tick_size: float
    _tick_scale: float

    _poc_price: float
    _poc_vol: float

    _peaks_price: Optional[List[float]]
    _valleys_price: Optional[List[float]]

    _val_price: float
    _vah_price: float

    _consolidated: bool

    def __init__(self, timestamp: float, sensibility: int,
                 price_precision: int = 8, tick_size: float = 0.00000001,
                 tick_scale: float = 1.0):

        self._timestamp = timestamp
        self._bins = None       # dict price: bid,ask volume

        self._min_price = 0.0   # bin price of at index 0 of bins (included from bins)
        self._max_price = 0.0   # bin price of at last index of bins + one step (excluded from bins)

        self._sensibility = sensibility

        self._price_precision = price_precision or 8
        self._tick_size = (tick_size or 0.00000001) * tick_scale

        self._tick_scale = tick_scale

        self._half_size = 0
        self._poc_idx = -1         # real-time POC bin index
        self._poc_vol = 0.0

        self._peaks_idx = None
        self._valleys_idx = None

        self._val_idx = -1
        self._vah_idx = -1

        self._consolidated = False

    def init(self, price: float):
        adj_price = self.adjust_price(price)

        base_price = int(adj_price / self._sensibility) * self._sensibility

        self._min_price = base_price
        self._max_price = base_price

        # centered base price
        centered_base_price = base_price + self._sensibility * 0.5

        # initial bin
        self._bins = {centered_base_price: [0.0, 0.0]}

        # reset state
        self._consolidated = False

    def adjust_price(self, price: float) -> float:
        """
        Adjust the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    @property
    def timestamp(self) -> float:
        return self._timestamp

    def as_dict(self) -> Dict[float, Tuple[float, float]]:
        return self._bins

    def add_bid(self, price: float, volume: float):
        base_price = self.set_at(price)
        self._bins[base_price][0] += volume
        self._update_poc(base_price)

    def add_ask(self, price: float, volume: float):
        base_price = self.set_at(price)
        self._bins[base_price][1] += volume
        self._update_poc(base_price)

    def bid(self, price: float) -> float:
        base_price = self.base_price(price)
        return self._bins[base_price][0]

    def ask(self, price: float) -> float:
        base_price = self.base_price(price)
        return self._bins[base_price][1]

    def volume(self, price: float) -> float:
        base_price = self.base_price(price)
        return sum(self._bins[base_price])

    def prices_array(self) -> np.array:
        """Prices array ordered by ascending"""
        return np.fromiter(sorted([p for p, v in self._bins.items()]), dtype=np.double)

    def volumes_by_price_array(self) -> np.array:
        """Unified (bid+ask) volumes array ordered by ascending price"""
        return sorted([(p, v) for p, v in self._bins.items()], key=lambda x: x[0])

    def base_price(self, price: float):
        if not self._bins:
            self.init(price)

        adj_price = self.adjust_price(price)

        # centered price
        return int(adj_price / self._sensibility) * self._sensibility + self._sensibility * 0.5

    def set_at(self, price: float):
        if not self._bins:
            self.init(price)

        adj_price = self.adjust_price(price)
        base_price = int(adj_price / self._sensibility) * self._sensibility

        # centered base price
        centered_base_price = base_price + self._sensibility * 0.5

        if base_price < self._min_price:
            self._min_price = base_price
            self._bins[centered_base_price] = [0.0, 0.0]
        elif base_price > self._max_price:
            self._max_price = base_price
            self._bins[centered_base_price] = [0.0, 0.0]
        elif centered_base_price not in self._bins:
            # intermediate price
            self._bins[centered_base_price] = [0.0, 0.0]

        return centered_base_price

    def _update_poc(self, base_price: float):
        volume = sum(self._bins[base_price])
        if volume > self._poc_vol:
            self._poc_vol = volume
            self._poc_price = base_price

    #
    # POC volume
    #

    def poc_price(self) -> float:
        # avg price
        return self._poc_price

    @property
    def poc_volume(self) -> float:
        return self._poc_vol

    #
    # volume area
    #

    def set_va_prices(self, val_price: float, vah_price: float):
        self._val_price = val_price
        self._vah_price = vah_price

    def val_price(self) -> float:
        return self._val_price

    def vah_price(self) -> float:
        return self._vah_price

    #
    # peaks & valleys
    #

    def set_peaks_prices(self, ps: List[float]):
        self._peaks_price = ps

    def set_valleys_price(self, vs: List[float]):
        self._valleys_price = vs

    def peaks_prices(self) -> List[float]:
        return self._peaks_price

    def valleys_prices(self) -> List[float]:
        return self._valleys_price


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

    __slots__ = '_history', '_sensibility', '_volume_area', '_size', '_vps', '_current', \
        '_session_offset', '_session_duration', '_price_precision', '_tick_size', '_tick_scale', \
        '_compute_peaks_and_valleys'

    _vps: List[VolumeProfile]          # closed previous VPs
    _current: Optional[BidAskLinearScaleDict]  # current dynamic VP

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def builder(cls, base_type: int, timeframe: float, *args):
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.volumeprofile.barvolumeprofile import BarVolumeProfileIndicator
            return BarVolumeProfileIndicator(timeframe, *args)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.volumeprofile.barvolumeprofile import BarVolumeProfileIndicator
            return BarVolumeProfileIndicator(timeframe, *args)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.volumeprofile.volumeprofile import VolumeProfileIndicator
            return VolumeProfileIndicator(timeframe, *args)

        return None

    def __init__(self, name: str, timeframe: float,
                 history_size: int = 10,
                 sensibility: int = 10,
                 value_area: float = 70,
                 detect_peaks_and_valleys: bool = False,
                 tick_scale: float = 1.0):
        """

        @param name:
        @param timeframe: Related timeframe or 0 if non-temporal
        @param history_size: Max kept previous profiles
        @param sensibility: Bin width
        @param value_area: 1% to 99%, 0 or below mean don't compute VA
        @param detect_peaks_and_valleys: If true compute peaks and valleys at close
        """
        super().__init__(name, timeframe)

        self._compute_at_close = True  # no effect

        self._history = history_size

        self._sensibility = sensibility
        self._volume_area = value_area

        self._compute_peaks_and_valleys = detect_peaks_and_valleys

        self._session_offset = 0.0    # 0 means starts at 00:00 UTC
        self._session_duration = 0.0  # 0 means full day

        self._price_precision = 1
        self._tick_size = 1.0
        self._tick_scale = tick_scale

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
    def sensibility(self) -> float:
        return self._sensibility

    @property
    def current(self) -> Union[None, BidAskLinearScaleArray, BidAskLinearScaleDict]:
        return self._current

    def adjust_price(self, price):
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    @property
    def is_compute_volume_area(self) -> bool:
        """True if volume area size is valid ]0..100]"""
        return 0 < self._volume_area <= 100

    @property
    def is_compute_peaks_and_valleys(self) -> bool:
        """True if compute peaks and valleys at finalize"""
        return self._compute_peaks_and_valleys

    @property
    def vps(self) -> List[VolumeProfile]:
        return self._vps

    def has_values(self, min_samples=1) -> bool:
        return len(self._vps) >= min_samples

    def last(self) -> VolumeProfile:
        """Last closed volume profile (not the current computed)"""
        return self._vps[-1] if self._vps else None

    def history(self, index=-1):
        """Return a previous closed volume profile (negative index based)"""
        return self._vps[index] if index < 0 and -index <= len(self._vps) else None

    def update_value_area(self):
        """Force to update value area of the current volume profile."""
        if self._current is None:
            return

        if 0 < self._volume_area <= 100:
            volumes_by_price = self._current.volumes_by_price_array()

            # find the low and high of the volume area
            val_price, vah_price = VolumeProfileBaseIndicator.compute_volume_area(
                volumes_by_price, self._current.poc_price(), self._volume_area)

            self._current.set_va_prices(val_price, vah_price)

    def update_peaks_and_valley(self):
        """Force to update peaks and valleys of the current volume profile."""
        if self._current is None:
            return

        volumes_by_price = self._current.volumes_by_price_array()

        # find peaks and valley
        # ps, vs = VolumeProfileBaseIndicator.basic_peaks_and_valleys_detection(volumes_by_price, 1)
        ps, vs = VolumeProfileBaseIndicator.find_peaks_and_valleys_sci_peak(volumes_by_price)
        # ps, vs = VolumeProfileBaseIndicator.find_peaks_and_valleys_sci_peak_adv(volumes_by_price, 20)

        self._current.set_peaks_prices([volumes_by_price[idx][0] for idx in ps])
        self._current.set_valleys_price([volumes_by_price[idx][0] for idx in vs])

    def finalize(self):
        """
        Finalize the computation of a volume-profile by computing the VAH, VAL and finding peaks and valleys.
        Does by update when the last trade timestamp open a new session.
        """
        if self._current is None:
            return

        timeframe = self._timeframe if self._timeframe > 0 else (self._last_timestamp - self._current.timestamp)

        vp = VolumeProfile(self._current.timestamp, timeframe,
                           self._sensibility,
                           self._current.poc_price(), 0, 0)

        vp.volumes = self._current.as_dict()

        volumes_by_price = None

        if self._compute_peaks_and_valleys:
            volumes_by_price = self._current.volumes_by_price_array()

            # find peaks and valley
            # ps, vs = VolumeProfileBaseIndicator.basic_peaks_and_valleys_detection(volumes_by_price, self._sensibility)
            ps, vs = VolumeProfileBaseIndicator.find_peaks_and_valleys_sci_peak(volumes_by_price)
            # ps, vs = VolumeProfileBaseIndicator._find_peaks_and_valleys_sci_peak_adv(volumes_by_price, 20)

            self._current.set_peaks_prices([volumes_by_price[idx][0] for idx in ps])
            self._current.set_valleys_price([volumes_by_price[idx][0] for idx in vs])

            vp.peaks, vp.valleys = self._current.peaks_prices(), self._current.valleys_prices()

            # logger.info(vp.peaks)
            # logger.info(vp.valleys)

        if 0 < self._volume_area <= 100:
            if volumes_by_price is None:
                volumes_by_price = self._current.volumes_by_price_array()

            # find the low and high of the volume area
            val_price, vah_price = self.compute_volume_area(volumes_by_price, vp.poc)

            self._current.set_va_prices(val_price, vah_price)

            vp.vah = self._current.vah_price()
            vp.val = self._current.val_price()

            # logger.info(vp.val)
            # logger.info(vp.vah)

        self._vps.append(vp)

        if len(self._vps) > self._history:
            # pop left
            self._vps.pop(0)

        # force to create a new one
        self._current = None

    #
    # volume area
    #

    @staticmethod
    def compute_volume_area(volumes_by_price: List, poc_price: float, volume_area: float = 70):
        """
        Simplest method to detect the volume area.
        Starting from the POC goes left and right until having the inner volume reached.
        It is not perfect because it could miss some peaks that will be important to have
        and sometimes the best choice might not be tried with centered algorithm.

        @param volumes_by_price List[(price, volume(bid, ask)]
        @param poc_price
        @param volume_area in percentage ]0..100] (default 70%)
        @return Tuple(float, float) with val_price and vah_price
        """
        if not volumes_by_price or not poc_price:
            return 0.0, 0.0

        poc_idx = -1
        sum_vols = 0.0

        for i, x in enumerate(volumes_by_price):
            if x[0] == poc_price:
                poc_idx = i

            sum_vols += sum(x[1])

        if poc_idx < 0:
            return 0.0, 0.0

        va_inf_price = poc_price
        va_sup_price = poc_price

        in_area = sum_vols * volume_area * 0.01
        # out_area = 1.0 - in_area

        max_index = len(volumes_by_price) - 1
        summed = sum(volumes_by_price[poc_idx][1])

        # start from left and right of the POC
        left = poc_idx - 1
        right = poc_idx + 1

        while summed < in_area:
            if left < 0 and right > max_index:
                break

            if left >= 0 and ((right <= max_index and volumes_by_price[left] > volumes_by_price[right]) or right > max_index):
                summed += sum(volumes_by_price[left][1])
                va_inf_price = volumes_by_price[left][0]
                left -= 1

            elif right <= max_index:
                summed += sum(volumes_by_price[right][1])
                va_sup_price = volumes_by_price[right][0]
                right += 1

        return min(va_inf_price, va_sup_price), max(va_inf_price, va_sup_price)

    #
    # peaks and valleys
    #

    @staticmethod
    def basic_peaks_and_valleys_detection(volumes_by_price: List, distance_rate: float):
        """
        Simplest peaks and valleys detection algorithm.
        """
        if not volumes_by_price:
            return [], []

        peaks = []
        valleys = []

        # avg = np.mean(volumes_by_price)
        min_dist = 2

        last_peak = -1
        last_valley = -1

        for i in range(1, len(volumes_by_price) - 1):
            v = sum(volumes_by_price[i][1])

            vl = v - v * distance_rate
            vh = v + v * distance_rate

            # peaks
            prev_vol = sum(volumes_by_price[i-1][1])
            next_vol = sum(volumes_by_price[i+1][1])

            if prev_vol < vl and next_vol < vl and i - last_valley > 1 and i - last_peak > min_dist:
                peaks.append(volumes_by_price[i][0])
                last_peak = i

            # valleys
            if prev_vol > vh and next_vol > vh and i - last_peak > 1 and i - last_valley > min_dist:
                valleys.append(volumes_by_price[i][0])
                last_valley = i

        return peaks, valleys

    @staticmethod
    def find_peaks_and_valleys_sci_peak(volumes_by_price: List):
        """
        Based on scipy find_peaks method.
        @note Could compute height using mean + stddev
        """
        weights = np.zeros(len(volumes_by_price), dtype=np.double)

        for i, x in enumerate(volumes_by_price):
            weights[i] = sum(x[1])

        l = len(weights)

        distanceP = max(2, l // 6)
        distanceV = max(2, l // 6)

        M = max(weights)

        heightP = M / 4
        heightV = -M / 4

        vs, _ = sg.find_peaks(-weights, heightV, None, distanceV)
        ps, _ = sg.find_peaks(weights, heightP, None, distanceP)

        return ps, vs

    @staticmethod
    def find_peaks_and_valleys_sci_peak_adv(volumes_by_price: List, n_samples=20):
        """
        Based on scipy find_peaks method. Profile is split with n_samples per buck.
        n_sample=20 seems OK in the first tests with btc.
        """
        weights = np.zeros(len(volumes_by_price), dtype=np.double)

        for i, x in enumerate(volumes_by_price):
            weights[i] = sum(x[1])

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

    #
    # helpers
    #

    def poc_price(self, previous: int = 0):
        """Lookup for the current profile POC price or for a previous profile (negative index)"""
        if previous == 0 and self._current:
            return self._current.poc_price()

        if -len(self._vps) <= previous < 0:
            return self._vps[previous].poc

        return 0.0

    def val_price(self, previous: int = 0):
        """
        Lookup for the current profile VAL price or for a previous profile (negative index)
        @warning Standard method does not compute VA for current profile.
        """
        if previous == 0 and self._current:
            return self._current.val_price()

        if -len(self._vps) <= previous < 0:
            return self._vps[previous].val

        return 0.0

    def vah_price(self, previous: int = 0):
        """
        Lookup for the current profile VAH price or for a previous profile (negative index)
        @warning Standard method does not compute VA for current profile.
        """
        if previous == 0 and self._current:
            return self._current.vah_price()

        if -len(self._vps) <= previous < 0:
            return self._vps[previous].vah

        return 0.0

    def _match_for_series(self, series, price: float, distance: float):
        if not series:
            return 0.0

        base_price = self._current.base_price(price)

        min_price = base_price - distance
        max_price = base_price + distance

        best_abs_price = 0.0
        match_price = 0.0

        for p in series:
            if min_price <= p <= max_price:
                dist = abs(price - p)

                if best_abs_price == 0.0 or dist < best_abs_price:
                    best_abs_price = best_abs_price
                    match_price = p

            if p > max_price:
                # ordered by price
                break

        return match_price

    def match_for_peak(self, price: float, distance: float = None, previous: int = -1):
        """
        Lookup on the last finalized profile (or an older one) if a price match with a peak.
        The price in converted into base price and matched is computed over a distance.
        @param price: Price to match
        @param distance: Specific distance in price or use tick_size by default
        @param previous: Negative index for previous profile (-1 default)
        @return: Match price of a peak or 0 is none.

        @note It assumes peaks are ordered by ascending prices.
        """
        if self._current is None:
            return 0.0

        if previous >= 0 or previous < -len(self._vps):
            # idx out of range
            return 0.0

        vp = self._vps[previous]

        if not vp.peaks:
            return 0.0

        if distance is None:
            distance = self._tick_size

        return self._match_for_series(vp.peaks, price, distance)

    def match_for_valley(self, price: float, distance: float = None, previous: int = -1):
        """
        Lookup on the last finalized profile (or an older one) if a price match with a peak.
        The price in converted into base price and matched is computed over a distance.

        @param price: Price to match
        @param distance: Specific distance in price or use tick_size by default
        @param previous: Negative index for previous profile (-1 default)
        @return: Match price of a peak or 0 is none.

        @note It assumes peaks are ordered by ascending prices.
        """
        if self._current is None:
            return 0.0

        if previous >= 0 or previous < -len(self._vps):
            # idx out of range
            return 0.0

        vp = self._vps[previous]

        if not vp.valleys:
            return 0.0

        if distance is None:
            distance = self._tick_size

        return self._match_for_series(vp.valleys, price, distance)


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
    def builder(cls, base_type: int, timeframe: float, *args):
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.volumeprofile.barlogvolumeprofile import BarLogVolumeProfileIndicator
            return BarLogVolumeProfileIndicator(timeframe, *args)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.volumeprofile.barlogvolumeprofile import BarLogVolumeProfileIndicator
            return BarLogVolumeProfileIndicator(timeframe, *args)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.volumeprofile.logvolumeprofile import LogVolumeProfileIndicator
            return LogVolumeProfileIndicator(timeframe, *args)

        return None

    def __init__(self, name: str, timeframe: float,
                 history_size: int = 10,
                 sensibility: int = 10,
                 detect_peaks_and_valleys: bool = False,
                 tick_scale: float = 1.0):
        super().__init__(name, timeframe)
