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

    NAME = "price-cross"
    ALERT = Alert.ALERT_PRICE_CROSS

    PRICE_SRC_BID = 0
    PRICE_SRC_OFR = 1
    PRICE_SRC_MID = 2

    def __init__(self, created, timeframe):
        super().__init__(created, timeframe)

        self._dir = 0    # price cross-up or down
        self._price = 0  # price value
        self._price_src = PriceCrossAlert.PRICE_SRC_BID  # source of the price (bid, ofr or mid)

    #
    # processing
    #

    def init(self, parameters):
        self._dir = parameters['dir']
        self._price = parameters['price']
        self._price_src = parameters['price-src']

    def check(self):
        return (self._dir in (-1, 1) and
                self._price > 0.0 and
                self._price_src in (PriceCrossAlert.PRICE_SRC_BID, PriceCrossAlert.PRICE_SRC_OFR, PriceCrossAlert.PRICE_SRC_MID))

    def test(self, timestamp, bid, ofr, timeframes):
        if self._dir > 0:
            if self._price_src == PRICE_SRC_BID:
                return bid > self._price
            elif self._price_src == PRICE_SRC_OFR:
                return ofr > self._price
            else:
                return (bid + ofr) * 0.5 > self._price
        elif self._dir < 0:
            if self._price_src == PRICE_SRC_BID:
                return bid < self._price
            elif self._price_src == PRICE_SRC_OFR:
                return  ofr < self._price
            else:
                return  (bid + ofr) * 0.5 < self._price

        return False

    def can_delete(self, timestamp, bid, ofr):
        return self._expiry > 0 and timestamp >= self._expiry

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
        result = super().dumps_notify(timestamp, result, strategy_trader):

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
