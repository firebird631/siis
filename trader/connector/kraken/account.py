# @date 2018-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Account/user model

import time

from trader.account import Account

import logging
logger = logging.getLogger('siis.trader.kraken')


class KrakenAccount(Account):
    """
    Kraken trader related account.
    """

    CURRENCY = "ZUSD"
    CURRENCY_SYMBOL = "$"
    ALT_CURRENCY = "XXBT"
    ALT_CURRENCY_SYMBOL = "₿"

    UPDATE_TIMEOUT = 60

    def __init__(self, parent):
        super().__init__(parent)

        self._account_type = Account.TYPE_ASSET | Account.TYPE_MARGIN

        self._currency = KrakenAccount.CURRENCY
        self._currency_display = KrakenAccount.CURRENCY_SYMBOL
        self._alt_currency = KrakenAccount.ALT_CURRENCY
        self._alt_currency_display = KrakenAccount.ALT_CURRENCY_SYMBOL

        self._currency_precision = 2
        self._alt_currency_precision = 8

        self._last_update = 0.0

    def update(self, connector):
        if connector is None or not connector.connected or not connector.ws_connected:
            return

        if time.time() - self._last_update >= KrakenAccount.UPDATE_TIMEOUT:
            # its all what we have... nothing just our internal mapping
            self._name = connector.account_id

            data = connector.get_account(self._currency)
            alt_data = connector.get_account(self._alt_currency)

            if data:
                self._asset_balance = float(data.get('eb', '0.0'))
                self._balance = float(data.get('e', '0.0'))
                self._net_worth = float(data.get('e', '0.0'))
                self._margin_balance = float(data.get('mf', '0.0'))
                self._profit_loss = float(data.get('n', '0.0'))
                self._risk_limit = float(data.get('mf', '0.0'))
                self._margin_level = float(data.get('ml', '0.0')) * 0.01

            # eb = solde équivalent (solde combiné de toutes les devises) 
            # tb = balance de trade (balance combinée de toutes les devises capital) 
            # m = montant de la marge des positions ouvertes
            # n = résultat net non réalisé profit/perte de positions ouvertes
            # c = coût de base des positions ouvertes
            # v = valeur flottante actuelle des positions ouvertes 
            # e = capital = balance de trade + résultat net non réalisé profit/perte de positions ouvertes
            # mf = marge libre = capital - marge initiale (marge maximale disponible pour ouvrir de nouvelles positions)
            # ml = niveau de marge = (capital / marge initiale) * 100

            # self._net_worth = 0.0

            # self._profit_loss = 0.0
            # self._asset_profit_loss = 0.0

            # self._asset_balance = 0.0
            # self._free_asset_balance = 0.0

            if alt_data:
                alt_balance = float(alt_data.get('eb', '0.0'))
                if alt_balance and self._asset_balance:
                    self._currency_ratio = alt_balance / self._asset_balance

            self._last_update = time.time()

    def set_margin_balance(self, margin_balance):
        self._margin_balance = margin_balance

    def set_unrealized_profit_loss(self, upnl):
        self._profit_loss = upnl
