# @date 2018-08-21
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import http.client
import urllib
import json
import time

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.account import Account

from config import config
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.trader.bitmex')


class BitMexAccount(Account):
    """
    BitMex trader related account.
    Currency prefered is BTC. Conversion must be done prior and during update.
    """

    CURRENCY = "BTC"
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

        self._last_update = 0

    def update(self, connector):
        if connector is None or not connector.connected or not connector.ws_connected:
            return

        # get results from the data array of the WS object, but now this can be done throught signals
        funds = connector.ws.funds()
        if not funds:
            return

        self._name = funds['account']

        self._currency = funds['currency']
        self._currency_display = funds['currency']

        self._balance = funds['walletBalance']  # diff between walletBalance and amount ??

        # net worth : balance + unrealized profit/loss
        self._net_worth = funds['amount'] + funds['prevUnrealisedPnl']

        self._margin_balance = funds['marginBalance']   # free margin
        self._risk_limit = funds['riskLimit']  # risk limit

        # we want account in BTC !
        if self._currency == 'XBt':
            ratio = 1.0 / 100000000

            self._risk_limit *= ratio
            self._balance *= ratio
            self._net_worth *= ratio
            self._margin_balance *= ratio

            self._currency = 'BTC'

        elif self._currency != 'XBT' and self._currency == 'BTC':
            logger.warning("Unsupported bitmex.com account currency %s" % (self._currency,))

        # update currency ratio
        xbtusd = connector.ws.get_instrument('XBTUSD')

        if not xbtusd:
            return

        self._currency_ratio = xbtusd['lastPrice']

        now = time.time()
        self._last_update = now

    def set_margin_balance(self, margin_balance):
        self._margin_balance = margin_balance
        # if self._currency == 'XBt':
        #   ratio = 1.0 / 100000000
        #   self._margin_balance = margin_balance * ratio

    def set_unrealized_profit_loss(self, upnl):
        self._profit_loss = upnl
        # if self._currency == 'XBt':
        #   ratio = 1.0 / 100000000
        #   self._margin_balance = upnl * ratio
