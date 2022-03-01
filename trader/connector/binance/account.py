# @date 2018-10-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import time

from trader.account import Account

import logging
logger = logging.getLogger('siis.trader.account.binance')
error_logger = logging.getLogger('siis.error.trader.account.binance')


class BinanceAccount(Account):
    """
    Binance trader related account.
    Account currency is BTC and alternative currency is USDT.
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

        # update balance each second
        if time.time() - self._last_update >= 1.0:
            # its all what we have... nothing just our internal mapping
            self._name = connector.account_id

            # recompute the balance and free margin for each non-zero account balance
            self._asset_balance = 0.0
            self._free_asset_balance = 0.0

            asset_quantities = self.parent.asset_quantities()

            self._currency_ratio = self.parent.last_price(self._currency+self._alt_currency)
            currency_market = self.parent.market(self._currency+self._alt_currency)

            if currency_market:
                self._currency_precision = currency_market.base_precision
                self._alt_currency_precision = currency_market.quote_precision

            for balance in asset_quantities:
                asset_name = balance[0]
                locked = balance[1]
                free = balance[2]

                if free or locked:
                    # asset price in quote
                    if asset_name == self._alt_currency:
                        # asset USDT
                        base_price = 1.0 / (self.parent.last_price(self._currency+self._alt_currency) or 1.0)
                    elif asset_name != self._currency:
                        # any asset except BTC
                        base_price = self.parent.last_price(asset_name+self._currency) or 1.0
                    else:
                        # asset BTC itself
                        base_price = 1.0

                    self._asset_balance += (free + locked) * base_price
                    self._free_asset_balance += free * base_price

            self._net_worth = self._asset_balance
            self._last_update = time.time()

        # @deprecated old way using a REST API call
        # if time.time() - self._last_update >= 60.0:
        #     # recompute the balance and free margin for each non-zero account balance
        #     self._balance = 0.0
        #     self._margin_balance = 0.0

        #     account = connector.client.get_account()

        #     self._currency_ratio = self.parent.last_price(self._currency+self._alt_currency)
        #     currency_market = self.parent.market(self._currency+self._alt_currency)

        #     if currency_market:
        #         self._currency_precision = currency_market.base_precision
        #         self._alt_currency_precision = currency_market.quote_precision

        #     for balance in account.get('balances', []):
        #         asset_name = balance['asset']
        #         free = float(balance['free'])
        #         locked = float(balance['locked'])

        #         if free or locked:
        #             # asset price in quote
        #             if asset_name == self._alt_currency:
        #                 # asset USDT
        #                 base_price = 1.0 / self.parent.last_price(self._currency+self._alt_currency)
        #             elif asset_name != self._currency:
        #                 # any asset except BTC
        #                 base_price = self.parent.last_price(asset_name+self._currency) or 1.0
        #             else:
        #                 # asset BTC itself
        #                 base_price = 1.0

        #             self._balance += (free + locked) * base_price
        #             self._margin_balance += free * base_price

        #     self._last_update = time.time()
