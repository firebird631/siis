# @date 2023-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Default implementation of on_received_economic_event, mixin

from __future__ import annotations

from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from strategy.strategy import Strategy
    from strategy.strategytraderbase import StrategyTraderBase
    from watcher.event import EconomicEvent

from instrument.instrument import Instrument

import logging

logger = logging.getLogger('siis.strategy.mixins.defaultoneconomiceventmixin')
error_logger = logging.getLogger('siis.error.strategy.defaultoneconomiceventmixin')
traceback_logger = logging.getLogger('siis.traceback.strategy.defaultoneconomiceventmixin')


def importance_str_to_level(importance: str):
    if importance == "low":
        return 1
    elif importance == "medium":
        return 2
    elif importance == "high":
        return 3

    return 0


class DefaultEconomicEventMixin(object):
    """
    Default implementation of on_received_economic_event, mixin
    """
    def __init__(self, strategy: Strategy, instrument: Instrument, base_timeframe: float, params: dict):
        super().__init__(strategy, instrument, base_timeframe, params)

        economic_event_params = params.get('economic-event', {})

        self._economic_event_max_retention_delay = Instrument.TF_30MIN

        self._economic_events_country = ""
        self._economic_events_currency = ""
        self._economic_events_min_level = 0
        self._economic_events_codes = []

        if economic_event_params:
            self._economic_events_codes = economic_event_params.get('code', [])
            self._economic_events_country = economic_event_params.get('country', "")
            self._economic_events_currency = economic_event_params.get('currency', "")
            self._economic_events_min_level = importance_str_to_level(economic_event_params.get('importance', ""))

    def on_received_economic_event(self,  # type: Union[DefaultEconomicEventMixin, StrategyTraderBase]
                                   economic_event: EconomicEvent):
        """
        This method is called by strategy update using a mutex then it is a thread safe slot.
        @param economic_event:
        """
        if economic_event is None:
            return

        # quote currency is not always as expected, uses a dedicated parameter
        # but could have a country code on market/instrument
        if self._economic_events_currency and economic_event.currency != self._economic_events_currency:
            return

        if self._economic_events_country and economic_event.country != self._economic_events_country:
            return

        if self._economic_events_min_level and economic_event.level < self._economic_events_min_level:
            return

        if self._economic_events_codes and economic_event.code not in self._economic_events_codes:
            return

        # event of interest and cleanup eventually older
        new_list = [economic_event]

        logger.info("Filters economic event for %s : %s" % (self.instrument.symbol, economic_event))

        # rewrite the list, clean older than max retention delay
        for evt in self.instrument.economic_events:
            delta_time = evt.date.timestamp() - self.strategy.timestamp
            # keep coming events and previous for max retention delay (default 30 minutes)
            if delta_time > -self._economic_event_max_retention_delay:
                new_list.append(evt)

        self.instrument.set_economic_events(new_list)
