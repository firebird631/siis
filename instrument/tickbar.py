# @date 2020-09-19
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Instrument tickbar models.

import math

from datetime import datetime, timedelta
from common.utils import UTC, timeframe_to_str, truncate, decimal_place

import logging
logger = logging.getLogger('siis.instrument.tickbar')


class TickBarBase(object):
    """
    Tick-bar base model for an instrument.
    @note Ofr is a synonym for ask.

    @note 11 floats + 1 bool
    """

    __slots__ = '_timestamp', '_last_timestamp', '_volume', '_ended', '_open_bid', '_open_ofr', '_close_bid', '_close_ofr'

    def __init__(self, timestamp):
        self._timestamp = timestamp
        self._last_timestamp = timestamp

        self._ticks = []  # array of ticks

        self._open_bid = 0.0
        self._open_ofr = 0.0

        self._close_bid = 0.0
        self._close_ofr = 0.0

        # or in tickbar indicators (could use X=Full or X>=VolumeFilter)
        self._volume = 0  # total volume for any ticks of the bar

        # volume delta from prev
        # volume change from prev
        # average size

        self._ended = True

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def last_timestamp(self):
        return self._last_timestamp

    @property
    def ended(self):
        return self._ended
