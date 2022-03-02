# @date 2018-08-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import time

from trader.account import Account

import logging
logger = logging.getLogger('siis.trader.bitmex')


class BitMexAccount(Account):
    """
    BitMex trader related account.
    """

    CURRENCY = "XBT"
    CURRENCY_SYMBOL = "₿"
    ALT_CURRENCY = "USD"
    ALT_CURRENCY_SYMBOL = "$"

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_MARGIN

        self._currency = BitMexAccount.CURRENCY
        self._currency_display = BitMexAccount.CURRENCY_SYMBOL
        self._alt_currency = BitMexAccount.ALT_CURRENCY
        self._alt_currency_display = BitMexAccount.ALT_CURRENCY_SYMBOL

        self._currency_precision = 8
        self._alt_currency_precision = 2

        self._ratio = 1.0 / 100000000
        self._last_update = 0

    def update(self, connector):
        if connector is None or not connector.connected or not connector.ws_connected:
            return

        # get results from the data array of the WS object, but now this can be done through signals
        funds = connector.ws.funds()
        if not funds:
            return

        self._currency = funds['currency']
        self._name = funds['account']

        self._balance = funds['walletBalance']  # diff between walletBalance and amount ??

        # net worth : balance + unrealized profit/loss
        self._net_worth = funds['amount'] + funds['prevUnrealisedPnl']

        self._margin_balance = funds['marginBalance']   # free margin
        self._risk_limit = funds['riskLimit']  # risk limit

        used_margin = funds['walletBalance'] - funds['availableMargin']
        if used_margin > 0.0:
            self._margin_level = funds['marginBalance'] / used_margin
        else:
            self._margin_level = 0.0

        # we want account in XBt
        if funds['currency'] == 'XBt':
            self._ratio = 1.0 / 100000000
            self._risk_limit *= self._ratio
            self._balance *= self._ratio
            self._net_worth *= self._ratio
            self._margin_balance *= self._ratio
        else:
            logger.error("Unsupported bitmex.com account currency %s" % funds['currency'])

        # update currency ratio
        xbtusd = connector.ws.get_instrument('XBTUSD')

        if not xbtusd:
            return

        self._currency_ratio = xbtusd['lastPrice']

        now = time.time()
        self._last_update = now

    def set_currency(self, currency, currency_display=""):
        self._currency = currency

        if currency == BitMexAccount.CURRENCY:
            self._currency_display = BitMexAccount.CURRENCY_SYMBOL

    def set_margin_balance(self, margin_balance):
        self._margin_balance = margin_balance
        # if self._currency == 'XBt':
        #   self._margin_balance = margin_balance * self._ratio

    def set_unrealized_profit_loss(self, upnl):
        self._profit_loss = upnl
        # if self._currency == 'XBt':
        #   self._margin_balance = upnl * self._ratio
