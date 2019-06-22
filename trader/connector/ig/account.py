# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import urllib
import json
import time
import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.account import Account

from config import config
from terminal.terminal import Terminal


class IGAccount(Account):

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_MARGIN

        self._currency = 'EUR'
        self._currency_ratio = 1.16  # from USD

        self._last_update = 0.0

    def update(self, connector):
        if connector is None or not connector.connected:
            return

        # initial update and then one per min, the live updated are done by signal and WS
        now = time.time()
        if now - self._last_update >= 1.0*60.0:
            self._last_update = now

            account = connector.funds()
            self._currency = account.get('currency')

            # exchange rate from account currency to USD if possible
            if self._currency != "USD":
                market_info = self.parent.market("CS.D.%s%s.MINI.IP" % (self._currency, "USD"))
                self._currency_ratio = market_info.base_exchange_rate if market_info else 1.0
            else:
                # account is already in USD
                self._currency = 1.0

            self._username = self._email = connector.username
            self._name = account.get('accountName')
            self._account_type = account.get('accountType')  # CFD, PHYSICAL, SPREADBET
            self._account_name = account.get('accountName')

            balance = account.get('balance')
            if balance:
                self._balance = balance.get('balance')
                self._net_worth = balance.get('available')
                self._profit_loss = balance.get('profitLoss')

                self._margin_balance = self._net_worth

                # cannot be computed because leverage depend of the instrument
                self._risk_limit = balance.get('available')
