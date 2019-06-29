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

        # update currency ratio
        xbtusd = connector.ws.get_instrument('XBTUSD')

        if not xbtusd:
            return

        self._currency_ratio = xbtusd['lastPrice']

        self._name = self._id = self._username = funds['account']
        self._username = self._username = funds['account']

        self._currency = funds['currency']
        self._currency_display = funds['currency']

        self._balance = funds['walletBalance']  # diff between walletBalanc and amount ??

        # net worth : balance + unrealized profit/loss
        self._net_worth = funds['amount'] + funds['prevUnrealisedPnl']

        self._margin_balance = funds['marginBalance']   # free margin
        self._risk_limit = funds['riskLimit']  # risk limit

        # we want account in BTC !
        if self._currency == 'XBt':
            self._risk_limit /= 100000000
            self._balance /= 100000000
            self._net_worth /= 100000000
            self._margin_balance /= 100000000

            self._currency = 'BTC'
        elif self._currency != 'XBT' and self._currency == 'BTC':
            logger.warning("Unsupported bitmex.com account currency %s" % (self._currency,))

        # @todo second currency

        now = time.time()
        self._last_update = now

    def set_margin_balance(self, margin_balance):
        self._margin_balance = margin_balance
        # if self._currency == 'XBt':
        #   self._margin_balance = margin_balance / 100000000

    def set_unrealized_profit_loss(self, upnl):
        self._profit_loss = upnl
        # if self._currency == 'XBt':
        #   self._margin_balance = upnl / 100000000
