# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Composite Volume Profile indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.models import VolumeProfile
from instrument.instrument import Instrument

from database.database import Database

from common.utils import truncate

import numpy as np

from strategy.indicator.volumeprofile.volumeprofilebase import VolumeProfileBaseIndicator


class CompositeVolumeProfile(object):
    """
    Composite volume profile.

    The composite volume profile is managed by a volume profile indicator,
    automatically or manually.

    The timeframe is the base timeframe, not the cumulated duration.
    Then the cumulated duration is timeframe x length.

    Due to the nature of the volume profile it means too many calculation per price changes to maintains up to date
    a composite, then it is actualized only when a new volume profile is added, and it this last is consolidated.

    The main usage of composite in mostly for big timeframe, many days or weeks or month, then it is not important
    to update at every tick. You can consider combining the composite plus a current volume profile.

    @todo Update using new format of VolumeProfile
    """

    __slots__ = '_timeframe', '_length', '_use_current', '_vp', '_volume_profile', \
        '_last_timestamp', '_last_base_timestamp'

    def __init__(self, timeframe: float, length: int, volume_profile: VolumeProfileBaseIndicator, merge_current=False):
        """

        @param timeframe: Base timeframe of the composite VP. Must be a multiple of the used indicator.
        @param length: Number of last profiles to merge.
        @param volume_profile: Related volume profile indicator as source.
        @param merge_current: During composite if true the current (non consolidated) VP is merged into.
        """
        self._timeframe = timeframe
        self._length = length
        self._use_current = merge_current

        self._last_timestamp = 0.0
        self._last_base_timestamp = 0.0

        self._volume_profile = volume_profile

        self._vp = VolumeProfile(0, timeframe)

    @property
    def vp(self):
        return self._vp

    def is_update_needed(self, timestamp: float, partial_update: bool = True) -> bool:
        """
        Returns true when the closing timestamp is reached.

        @param timestamp Current timestamp.
        @param partial_update If True it will return true at each intermediate volume profile realized,
               else it will wait for the length of new volumes profiles completed.
        """
        if partial_update:
            return timestamp >= self._last_base_timestamp + self._timeframe
        else:
            return timestamp >= self._last_base_timestamp + self._timeframe * self._length

    def process(self, timestamp: float):
        """
        Append the last volume profile if it is consolidated. This method is incremental.
        @param timestamp:
        @return:
        """
        # @todo

        return self._vp

    def composite(self, timestamp: float) -> VolumeProfile:
        """
        Build a complete composite profile of the given length. Never add a non consolidated volume profile.
        This method is only for initial setup, after it is preferred to uses the process incremental method to avoid
        too many calculations.
        """
        if self._volume_profile is None or not self._volume_profile.vps:
            return self._vp

        volume_profile = self._volume_profile

        poc_vol = 0.0

        base_index = max(-self._length, -len(volume_profile.vps))
        base_timestamp = volume_profile.vps[base_index]

        if self._timeframe > 0:
            # adjust for fixe timeframe
            cvp = VolumeProfile(Instrument.basetime(self._timeframe, base_timestamp), self._timeframe)
        else:
            # simply use timestamp of the first VP
            cvp = VolumeProfile(base_timestamp, 0.0)

        for vp in volume_profile.vps[base_index:]:
            for b, v in vp.volumes.items():
                if b not in cvp.volumes:
                    cvp.volumes[b] = v
                else:
                    cvp.volumes[b] += v

                if cvp.volumes[b] > poc_vol:
                    poc_vol = cvp.volumes[b]
                    vp.poc = b

        self._last_base_timestamp = volume_profile.vps[-1].timestamp
        self._last_timestamp = timestamp

        # current
        self._vp = cvp
        return cvp

    def finalize(self):
        """
        Finalize the computation of the current VP.
        Does by update when the last trade timestamp open a new session.
        """
        # todo
        pass
        # # volumes arranged by price
        # volumes_by_price = VolumeProfileBaseIndicator._sort_volumes_by_price(composite)

        # # # find peaks and valley
        # # composite.peaks, composite.valleys = VolumeProfileBaseIndicator.basic_peaks_and_valleys_detection(
        # #     volume_profile.bins, volume_profile.sensibility, composite)

        # # find peaks and valley
        # # # composite.peaks, composite.valleys = self.basic_peaks_and_valleys_detection(
        # #     volume_profile.bins, volume_profile.sensibility, composite)
        # # composite.peaks, composite.valleys = self.scipy_peaks_and_valleys_detection(vp)

        # # find the low and high of the volume area
        # # composite.low_area, composite.high_area = self.single_volume_area(composite, volumes_by_price, composite.poc)
