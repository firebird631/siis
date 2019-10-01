# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import urllib
import json
import time

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.account import Account
from terminal.terminal import Terminal


class IGAccount(Account):
    """
    Done once per minute, but could be done more frequently using data get through WS and avoiding the extra API call.
    """

    CURRENCY = "EUR"
    CURRENCY_SYMBOL = "€"

    UPDATE_TIMEOUT = 60

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_MARGIN

        self._currency = IGAccount.CURRENCY
        self._currency_display = IGAccount.CURRENCY_SYMBOL
        self._currency_ratio = 1.16  # initial, from USD

        self._last_update = 0.0

    def update(self, connector):
        if connector is None or not connector.connected:
            return

        # initial update and then one per min, the live updated are done by signal and WS
        if time.time() - self._last_update >= IGAccount.UPDATE_TIMEOUT:
            # cause a REST API query
            account = connector.funds()

            self._name = account.get('accountName')
            self._username = self._email = connector.username

            account_type = account.get('accountType', '')
            if account_type == "CFD":
                self._account_type = IGAccount.TYPE_MARGIN
            elif account_type == "PHYSICAL":
                self._account_type = IGAccount.TYPE_ASSET
            elif account_type == "SPREADBET":
                self._account_type = IGAccount.TYPE_SPREADBET

            self._currency = account.get('currency')

            # exchange rate from account currency to USD if possible
            if self._currency != "USD":
                market_info = self.parent.market("CS.D.%s%s.MINI.IP" % (self._currency, "USD"))
                self._currency_ratio = market_info.base_exchange_rate if market_info else 1.0
            else:
                # account is already in USD
                self._currency = 1.0

            balance = account.get('balance')
            if balance:
                self._balance = balance.get('balance')
                self._margin_balance = balance.get('available')
                self._profit_loss = balance.get('profitLoss')

                self._net_worth = self._balance + self._profit_loss

                # cannot be computed because leverage depend of the instrument
                self._risk_limit = balance.get('available')

            self._last_update = time.time()
