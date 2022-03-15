# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def account_table(trader, style='', offset=None, limit=None, col_ofs=None):
    """
    Returns a table of any followed markets.
    """
    columns = ('Broker', 'Account', 'Username', 'Email', 'Asset', 'Free Asset', 'Balance', 'Margin',
               'Level', 'Net worth', 'Risk limit', 'Unrealized P/L', 'Asset U. P/L')
    data = []

    with trader.mutex:
        if offset is None:
            offset = 0

        if limit is None:
            limit = 1

        limit = offset + limit

        cd = trader.account.currency_display or trader.account.currency

        asset_balance = trader.account.format_price(trader.account.asset_balance) + cd
        free_asset_balance = trader.account.format_price(trader.account.free_asset_balance) + cd
        balance = trader.account.format_price(trader.account.balance) + cd
        margin_balance = trader.account.format_price(trader.account.margin_balance) + cd
        net_worth = trader.account.format_price(trader.account.net_worth) + cd
        risk_limit = trader.account.format_price(trader.account.risk_limit) + cd
        upnl = trader.account.format_price(trader.account.profit_loss) + cd
        asset_upnl = trader.account.format_price(trader.account.asset_profit_loss) + cd

        if (trader.account.currency != trader.account.alt_currency and trader.account.currency_ratio != 1.0 and
                trader.account.currency_ratio > 0.0):
            acd = trader.account.alt_currency_display or trader.account.alt_currency

            asset_balance += " (%s)" % trader.account.format_price(
                trader.account.asset_balance * trader.account.currency_ratio) + acd
            free_asset_balance += " (%s)" % trader.account.format_price(
                trader.account.free_asset_balance * trader.account.currency_ratio) + acd
            balance += " (%s)" % trader.account.format_price(
                trader.account.balance * trader.account.currency_ratio) + acd
            margin_balance += " (%s)" % trader.account.format_price(
                trader.account.margin_balance * trader.account.currency_ratio) + acd
            net_worth += " (%s)" % trader.account.format_alt_price(
                trader.account.net_worth * trader.account.currency_ratio) + acd
            risk_limit += " (%s)" % trader.account.format_price(
                trader.account.risk_limit * trader.account.currency_ratio) + acd
            upnl += " (%s)" % trader.account.format_alt_price(
                trader.account.profit_loss * trader.account.currency_ratio) + acd
            asset_upnl += " (%s)" % trader.account.format_alt_price(
                trader.account.asset_profit_loss * trader.account.currency_ratio) + acd

        row = (
            trader.name,
            trader.account.name,
            trader.account.username,
            trader.account.email,
            asset_balance,
            free_asset_balance,
            balance,
            margin_balance,
            "%.2f%%" % (trader.account.margin_level * 100.0),
            net_worth,
            risk_limit,
            upnl,
            asset_upnl
        )

        if offset < 1 and limit > 0:
            data.append(row[0:2] + row[2+col_ofs:])

    return columns[0:2] + columns[2+col_ofs:], data, (len(columns), 1)
