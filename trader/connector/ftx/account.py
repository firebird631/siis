# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Account/user model

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .trader import FTXTrader

import time

from trader.account import Account

import logging
logger = logging.getLogger('siis.trader.account.ftx')
error_logger = logging.getLogger('siis.error.trader.account.ftx')


class FTXAccount(Account):
    """
    FTX trader related account.
    Account currency is USDT and alternative currency is BTC.
    """

    CURRENCY = "USDT"
    CURRENCY_SYMBOL = "Ť"
    ALT_CURRENCY = "BTC"
    ALT_CURRENCY_SYMBOL = "₿"

    _parent: FTXTrader

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_ASSET

        self._currency = FTXAccount.CURRENCY
        self._currency_display = FTXAccount.CURRENCY_SYMBOL
        self._alt_currency = FTXAccount.ALT_CURRENCY
        self._alt_currency_display = FTXAccount.ALT_CURRENCY_SYMBOL

        self._currency_precision = 2
        self._alt_currency_precision = 8

        self._last_update = 0.0

    @property
    def parent(self) -> FTXTrader:
        return self._parent

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

            # @todo

            self._net_worth = self._asset_balance
            self._last_update = time.time()
