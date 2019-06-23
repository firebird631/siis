# @date 2018-10-10
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import http.client
import urllib
import json
import time
import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.account import Account

from config import config
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.trader.binance')


class BinanceAccount(Account):
    """
    Binance trader related account.
    Account currency is in USDT.
    """

    CURRENCY = "BTC"
    CURRENCY_SYMBOL = "₿"
    ALT_CURRENCY = "USDT"
    ALT_CURRENCY_SYMBOL = "Ť"

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_ASSET
        
        self._currency = BinanceAccount.CURRENCY
        self._currency_display = BinanceAccount.CURRENCY_SYMBOL
        self._alt_currency = BinanceAccount.ALT_CURRENCY
        self._alt_currency_display = BinanceAccount.ALT_CURRENCY_SYMBOL

        self._currency_precision = 8
        self._alt_currency_precision = 2

        self._last_update = 0

    def update(self, connector):
        if connector is None or not connector.connected:
            return

        # initial update and then one per min
        now = time.time()
        if now - self._last_update >= 60.0:
            self._last_update = now

            self._username = self.parent.name
            self._email = ''
            self._account_name = ''

            # recompute the balance and free margin for each non-zero account balance
            self._balance = 0.0
            self._margin_balance = 0.0

            account = connector.client.get_account()

            self._currency_ratio = self.parent.price(self._currency+self._alt_currency)

            currency_market = self.parent.market(self._currency+self._alt_currency)

            if currency_market:
                self._currency_precision = currency_market.base_precision
                self._alt_currency_precision = currency_market.quote_precision

            for balance in account.get('balances', []):
                asset_name = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])

                if free or locked:
                    # asset price in quote
                    if asset_name == self._alt_currency:
                        # asset USDT
                        base_price = 1.0 / self.parent.price(self._currency+self._alt_currency)
                    elif asset_name != self._currency:
                        # any asset except BTC
                        base_price = self.parent.price(asset_name+self._currency) or 1.0
                    else:
                        # asset BTC itself
                        base_price = 1.0

                    self._balance += (free + locked) * base_price
                    self._margin_balance += free * base_price
