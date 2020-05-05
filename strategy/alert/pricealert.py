# @date 2020-02-29
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Strategy price alert

from .alert import Alert

import logging
logger = logging.getLogger('siis.strategy.alert.price')


class PriceCrossAlert(Alert):
    """
    @todo Complete
    """

    __slots__ = '_price', '_price_src', '_last_price'

    NAME = "price-cross"
    ALERT = Alert.ALERT_PRICE_CROSS

    def __init__(self, created, timeframe):
        super().__init__(created, timeframe)

        self._dir = 0      # price cross-up or down
        self._price = 0.0  # price value
        self._price_src = PriceCrossAlert.PRICE_SRC_BID  # source of the price (bid, ofr or mid)

        self._last_price = 0.0

    #
    # processing
    #

    def init(self, parameters):
        self._dir = parameters['direction']
        self._price = parameters['price']
        self._price_src = parameters['price-src']
        self._last_price = 0.0

    def check(self):
        return (self._dir in (-1, 1) and
                self._price > 0.0 and
                self._price_src in (PriceCrossAlert.PRICE_SRC_BID, PriceCrossAlert.PRICE_SRC_OFR, PriceCrossAlert.PRICE_SRC_MID))

    def test(self, timestamp, bid, ofr, timeframes):
        result = False

        if self._last_price <= 0.0:
            if self._price_src == PriceCrossAlert.PRICE_SRC_BID:
                self._last_price = bid
            elif self._price_src == PriceCrossAlert.PRICE_SRC_OFR:
                self._last_price = ofr
            else:
                mid = (bid + ofr) * 0.5
                self._last_price = mid

            # need one more sample
            return False

        if self._dir > 0:
            if self._price_src == PriceCrossAlert.PRICE_SRC_BID:
                result = bid >= self._price and self._last_price < self._price
                self._last_price = bid
            elif self._price_src == PriceCrossAlert.PRICE_SRC_OFR:
                result = ofr >= self._price and self._last_price < self._price
                self._last_price = ofr
            else:
                mid = (bid + ofr) * 0.5
                result = mid > self._price and self._last_price < self._price
                self._last_price = mid

        elif self._dir < 0:
            if self._price_src == PriceCrossAlert.PRICE_SRC_BID:
                result = bid <= self._price and self._last_price < self._price
                self._last_price = bid
            elif self._price_src == PriceCrossAlert.PRICE_SRC_OFR:
                result = ofr <= self._price and self._last_price < self._price
                self._last_price = ofr
            else:
                mid = (bid + ofr) * 0.5
                result = mid < self._price and self._last_price > self._price
                self._last_price = mid

        return result

    def can_delete(self, timestamp, bid, ofr):
        return (self._expiry > 0 and timestamp >= self._expiry) or self._countdown == 0

    def str_info(self):
        if self._dir >= 0:
            part = "if %s price goes above %s" % (self.price_src_to_str(), self._price)
        elif self._dir <= 0:
            part = "if %s price goes below %s" % (self.price_src_to_str(), self._price)

        return "Price alert cross, %s, timeframe %s, expiry %s, cancelation %s" % (
            part, self.timeframe_to_str(), self.expiry_to_str(), self._cancelation)

    #
    # dumps for notify/history
    #

    def dumps_notify(self, timestamp, result, strategy_trader):
        result = super().dumps_notify(timestamp, result, strategy_trader)

        # result['trigger'] =
        # result['reason'] = 

        return result

    #
    # persistance
    #

    def parameters(self):
        result = super().parameters()

        # @todo

        return result

    def dumps(self):
        result = super().dumps()

        # @todo

        return result

    def loads(self, data):
        super().loads(data)

        # @todo

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
