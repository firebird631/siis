# @date 2024-08-03
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Abstract model with update_bar and update_tick methods to be processed during a bar generator

from instrument.instrument import TickType, Candle


class GeneratorUpdaterMixin(object):
    """
    Abstract model with update_bar and update_tick methods to be processed during a bar generator
    """
    def update_tick(self, tick: TickType, finalize: bool):
        """
        Here put any tick based indicator update.
        Such as bar volume-profile, bar vwap, bar cumulative volume delta...
        @param tick: Last processed tick
        @param finalize: True if the bar just close
        """
        pass

    def update_bar(self, bar: Candle):
        """
        Here put any bar based indicator update.
        Such as bar volume-profile, bar vwap, bar cumulative volume delta...
        @param bar: Last generated bar and closed bar
        """
        pass
