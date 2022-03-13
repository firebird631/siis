# @date 2020-05-09
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Account/user model for binance futures

import time

from trader.account import Account

import logging
logger = logging.getLogger('siis.trader.binancefutures')


class BinanceFuturesAccount(Account):
    """
    Binance futures trader related account.
    """

    CURRENCY = "USDT"
    CURRENCY_SYMBOL = "Ť"
    ALT_CURRENCY = "BTC"
    ALT_CURRENCY_SYMBOL = "₿"

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_MARGIN

        self._currency = BinanceFuturesAccount.CURRENCY
        self._currency_display = BinanceFuturesAccount.CURRENCY_SYMBOL
        self._alt_currency = BinanceFuturesAccount.ALT_CURRENCY
        self._alt_currency_display = BinanceFuturesAccount.ALT_CURRENCY_SYMBOL

        self._currency_precision = 2
        self._alt_currency_precision = 8

        self._last_update = 0.0

    def update(self, connector):
        if connector is None or not connector.connected:
            return

        # update balance each second
        if time.time() - self._last_update >= 1.0:
            # its all what we have... nothing just our internal mapping
            self._name = connector.account_id

            if self._last_update <= 0:
                # does the initial using REST API
                account = connector.futures_account()
                if account:
                    # @ref https://binance-docs.github.io/apidocs/futures/en/#account-information-user_data
                    self._balance = float(account['totalWalletBalance'])

                    # net worth : balance + unrealized profit/loss
                    self._net_worth = float(account['totalWalletBalance']) + float(account['totalUnrealizedProfit'])
                    self._margin_balance = float(account['totalMarginBalance'])   # free margin

                    self._risk_limit = float(account['totalMarginBalance'])

                    currency_market = self.parent.market(self._alt_currency+self._currency)
                    if currency_market:
                        self._currency_precision = currency_market.base_precision
                        self._alt_currency_precision = currency_market.quote_precision

                balance = connector.futures_balance()
                if balance:
                    self._name = balance[0]["accountAlias"]
            else:
                # next through WS updates, get_balances impl for this trader
                balances = self.parent.watcher.get_balances()

                self._balance = balances['totalWalletBalance']

                # net worth : balance + unrealized profit/loss
                self._net_worth = balances['totalWalletBalance'] + balances['totalUnrealizedProfit']

                # free margin
                self._margin_balance = balances['totalCrossMarginBalance'] + balances['totalIsolatedMarginBalance']

                self._risk_limit = balances['totalCrossMarginBalance'] + balances['totalIsolatedMarginBalance']

            # margin level
            used_margin = self._balance - self._margin_balance
            if used_margin > 0.0:
                self._margin_level = self._margin_balance / used_margin
            else:
                self._margin_level = 0.0

            self._currency_ratio = 1.0 / (self.parent.last_price(self._alt_currency+self._currency) or 1.0)
            self._last_update = time.time()
