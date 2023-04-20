# @date 2018-09-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

from trader.account import Account


class PaperTraderAccount(Account):
    """
    The account currency must be defined as the real trader, same the initial balance amount.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_ASSET

        self._username = "paper-trader"
        self._email = ""
        self._id = "paper-trader"
        self._name = "paper-trader"

        self._currency = "USD"
        self._currency_display = "$"

        self._currency_ratio = 1.0
        self._account_leverage = 30.0

        self._leverage = [1, 200]    # min/max leverage
        self._risk_limit = 0.0

        self._balance = 1000.0
        self._margin_balance = self._balance

    def update(self, connector):
        if self.parent:
            market = self.parent._markets.get(self._currency+self._alt_currency)
            if market:
                self._currency_ratio = market.price

    def set_currency(self, currency: str, currency_display: str = ""):
        super().set_currency(currency, currency_display)
        self._currency_precision = PaperTraderAccount._get_currency_precision(self._currency)

    def set_alt_currency(self, alt_currency: str, alt_currency_display: str = ""):
        super().set_alt_currency(alt_currency, alt_currency_display)
        self._alt_currency_precision = PaperTraderAccount._get_currency_precision(self._alt_currency)

    @staticmethod
    def _get_currency_precision(currency):
        if currency in ("XBT", "XXBT", "BTC"):
            return 8

        if currency in ("ETH", "XETH"):
            return 8

        if currency in ("USD", "EUR", "CAD", "AUD", "NZD", "ZEUR", "ZUSD", "ZCAD", "ZAUD", "ZNZD"):
            return 2

        return 2
