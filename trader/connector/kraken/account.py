# @date 2018-08-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
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
logger = logging.getLogger('siis.trader.kraken')


class KrakenAccount(Account):
    """
    Kraken trader related account.
    """

    CURRENCY = "ZUSD"
    CURRENCY_SYMBOL = "$"
    ALT_CURRENCY = "ZEUR"
    ALT_CURRENCY_SYMBOL = "€"

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_ASSET | Account.TYPE_MARGIN

        self._currency = KrakenAccount.CURRENCY
        self._currency_display = KrakenAccount.CURRENCY_SYMBOL
        self._alt_currency = KrakenAccount.ALT_CURRENCY
        self._alt_currency_display = KrakenAccount.ALT_CURRENCY_SYMBOL

        self._currency_precision = 2
        self._alt_currency_precision = 2

        self._last_update = 0

    def update(self, connector):
        if connector is None or not connector.connected or not connector.ws_connected:
            return

        # @todo

        # self._free_asset_balance
        # self._asset_balance

        # self._balance = 0.0
        # self._net_worth = 0.0
        # self._margin_balance = 0.0
        # self._risk_limit = 0.0

        now = time.time()
        self._last_update = now

    def set_currency(self, currency, currency_display=""):
        self._currency = currency

    def set_margin_balance(self, margin_balance):
        self._margin_balance = margin_balance

    def set_unrealized_profit_loss(self, upnl):
        self._profit_loss = upnl
