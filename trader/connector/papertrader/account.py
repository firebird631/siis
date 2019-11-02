# @date 2018-09-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

from trader.account import Account
from terminal.terminal import Terminal


class PaperTraderAccount(Account):
    """
    The account currency must be defined as the real trader, same the the initial balance amount.
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
        self._risk_limit = 0

        self._balance = 1000.0
        self._margin_balance = self._balance

    def update(self, connector):
        if self.parent:
            market = self.parent._markets.get(self._currency+self._alt_currency)
            if market:
                self._currency_ratio = market.price
