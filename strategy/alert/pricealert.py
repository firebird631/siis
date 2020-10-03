# @date 2020-02-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Strategy price alert

from .alert import Alert
from instrument.instrument import Instrument

from common.utils import direction_to_str

import logging
logger = logging.getLogger('siis.strategy.alert.price')


class PriceCrossAlert(Alert):
    """
    Alert when price cross up or down a specified value, and at a timeframe or each time if no timeframe defined.

    @todo Persistance
    @todo Cancelation price
    """

    __slots__ = '_price', '_price_src', '_cancelation_price', '_last_price', '_last_trigger_timestamp'

    NAME = "price-cross"
    ALERT = Alert.ALERT_PRICE_CROSS

    def __init__(self, created, timeframe):
        super().__init__(created, timeframe)

        self._dir = 0      # price cross-up or down
        self._price = 0.0  # price value
        self._price_src = PriceCrossAlert.PRICE_SRC_BID  # source of the price (bid, ofr or mid)

        self._cancelation_price = 0.0  # Remove the alert if price reach it

        self._last_price = 0.0
        self._last_trigger_timestamp = 0.0

    #
    # processing
    #

    def init(self, parameters):
        self._dir = parameters.get('direction', 0)
        self._price = parameters.get('price', 0.0)
        self._price_src = parameters.get('price-src', 0)
        self._cancelation_price = parameters.get('cancelation', 0.0)
        self._last_price = 0.0

    def check(self):
        return (self._dir in (-1, 1) and
                self._price > 0.0 and
                self._price_src in (PriceCrossAlert.PRICE_SRC_BID, PriceCrossAlert.PRICE_SRC_OFR, PriceCrossAlert.PRICE_SRC_MID))

    def test(self, timestamp, bid, ofr, timeframes):
        trigger = 0

        if self._price_src == PriceCrossAlert.PRICE_SRC_BID:
            ref_price = bid
        elif self._price_src == PriceCrossAlert.PRICE_SRC_OFR:
            result = ofr >= self._price and self._last_price < self._price
            ref_price = ofr
        else:
            ref_price = mid = (bid + ofr) * 0.5

        if self._last_price <= 0.0:
            self._last_price = ref_price

            # need one more sample
            return None

        if self._dir > 0:
            if ref_price >= self._price and self._last_price < self._price:
                trigger = 1
        elif self._dir < 0:
            if ref_price <= self._price and self._last_price > self._price:
                trigger = -1

        self._last_price = ref_price

        if trigger == 0:
            return None

        if self._timeframe > 0:
            # check if occurs many time during the same timeframe
            prev_bt = Instrument.basetime(self._timeframe, self._last_trigger_timestamp)
            cur_bt = Instrument.basetime(self._timeframe, timestamp)

            if cur_bt <= prev_bt:
                return None

        self._last_trigger_timestamp = timestamp

        return {
            'trigger': trigger,
        }

    def can_delete(self, timestamp, bid, ofr):
        return (self._expiry > 0 and timestamp >= self._expiry) or self._countdown == 0

    def str_info(self):
        if self._dir > 0:
            part = "if %s price goes above %s" % (self.price_src_to_str(), self._price)
        elif self._dir < 0:
            part = "if %s price goes below %s" % (self.price_src_to_str(), self._price)
        else:
            part = "?"

        return "Price alert cross, %s, timeframe %s, expiry %s, cancelation %s" % (
            part, self.timeframe_to_str(), self.expiry_to_str(), self._cancelation)

    def cancelation_str(self):
        """
        Dump a string with short alert cancelation str.
        """
        if self._dir > 0 and self._cancelation_price > 0.0:
            return"if %s price > %s" % (self.price_src_to_str(), self._cancelation_price)
        elif self._dir < 0 and self._cancelation_price > 0.0:
            return "if %s price < %s" % (self.price_src_to_str(), self._cancelation_price)
        else:
            return "never"

    def condition_str(self):
        """
        Dump a string with short alert condition str.
        """
        if self._dir > 0:
            return"if %s price > %s" % (self.price_src_to_str(), self._price)
        elif self._dir < 0:
            return "if %s price < %s" % (self.price_src_to_str(), self._price)
        else:
            return ""

    #
    # dumps for notify/history
    #

    def dumps_notify(self, timestamp, alert_result, strategy_trader):
        result = super().dumps_notify(timestamp, alert_result, strategy_trader)

        result['trigger'] = alert_result['trigger']

        if alert_result['trigger'] > 0:
            result['reason'] = "Price cross-up %s" % self._price
        elif alert_result['trigger'] < 0:
            result['reason'] = "Price cross-down %s" % self._price

        return result

    #
    # persistance
    #

    def parameters(self):
        result = super().parameters()

        result['direction'] = direction_to_str(self._dir)
        result['price'] = self._price
        result['price-src'] = self.price_src_to_str()
        result['cancelation-price'] = self._cancelation_price

        return result

    def dumps(self):
        result = super().dumps()

        result['direction'] = self._dir
        result['price'] = self._price
        result['price-src'] = self._price_src
        result['cancelation-price'] = self._cancelation_price

        return result

    def loads(self, data):
        super().loads(data)

        self._dir = result['direction']
        self._price = result['price']
        self._price_src = result['price-src']
        self._cancelation_price = result['cancelation-price']

    #
    # helpers
    #

    def price_src_to_str(self):
        if self._price_src == PriceCrossAlert.PRICE_SRC_BID:
            return "bid"
        elif self._price_src == PriceCrossAlert.PRICE_SRC_OFR:
            return "ofr"
        if self._price_src == PriceCrossAlert.PRICE_SRC_MID:
            return "mid"
        else:
            return "???"
