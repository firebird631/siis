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

    NAME = "pricecross"
    ALERT = Alert.ALERT_PRICE_CROSS

    def __init__(self, created, timeframe):
        super().__init__(created, timeframe)

    #
    # dumps for notify/history
    #

    def dumps_notify(self, timestamp, strategy_trader, bid, ofr, timeframes):
        result = super().dumps_notify(timestamp, strategy_trader, bid, ofr, timeframes)

        # @todo

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
