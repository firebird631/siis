# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging

from terminal.terminal import Color

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def assets_table(trader, style='', offset=None, limit=None, col_ofs=None, filter_low=True, group=None, ordering=None):
    """
    Returns a table of any non empty assets.
    """
    COLUMNS = ('Asset', 'Locked', 'Free', 'Total', 'Avg price', 'Change', 'Change %', 'P/L', 'Quote', 'Pref Market')

    total_size = (len(COLUMNS), 0)
    data = []

    with trader.mutex:
        assets = [asset for asset in trader._assets.values() if asset.quantity > 0.0]
        total_size = (len(COLUMNS), len(assets))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(assets)

        limit = offset + limit

        if group:
            assets.sort(key=lambda x: x.quantity, reverse=True if ordering else False)
        else:
            assets.sort(key=lambda x: x.symbol, reverse=True if ordering else False)

        assets = assets[offset:limit]

        for asset in assets:
            # use the most appropriate market
            market_id = asset.market_ids[0] if asset.market_ids else asset.symbol+asset.quote if asset.quote else None
            market = trader._markets.get(market_id)

            change = ""
            change_percent = ""
            profit_loss = ""

            if market:
                locked = market.format_quantity(asset.locked)
                free = market.format_quantity(asset.free)
                quantity = market.format_quantity(asset.quantity)

                if market.bid and asset.price:
                    change = market.format_price(market.bid - asset.price) + market.quote_display or market.quote
                    change_percent = (market.bid - asset.price) / asset.price * 100.0 if asset.price else 0.0

                    if change_percent > 0.0:
                        change_percent = Color.colorize("%.2f" % change_percent, Color.GREEN, style)
                    elif change_percent < 0.0:
                        change_percent = Color.colorize("%.2f" % change_percent, Color.RED, style)
                    else:
                        change_percent = "%.2f" % change_percent

                if asset.quantity > 0.0:
                    profit_loss = market.format_price(asset.profit_loss)

                    if asset.profit_loss > 0.0:
                        if profit_loss:
                            profit_loss = Color.colorize(profit_loss, Color.GREEN, style)
                    elif asset.profit_loss < 0.0:
                        if profit_loss:
                            profit_loss = Color.colorize(profit_loss, Color.RED, style)

                    profit_loss += market.quote_display or market.quote
            else:
                locked = "%.8f" % asset.locked
                free = "%.8f" % asset.free
                quantity = "%.8f" % asset.quantity

            row = (
                asset.symbol,
                locked,
                free,
                quantity,
                "%s%s" % (asset.format_price(asset.price), asset.quote) if asset.price else '-',  # charmap.HOURGLASS,
                change or '-',
                change_percent or '-',
                profit_loss or '-',
                asset.quote or '-',
                asset.market_ids[0] if asset.market_ids else '-'
            )

            data.append(row[0:1] + row[1+col_ofs:])

    return COLUMNS[0:1] + COLUMNS[1+col_ofs:], data, total_size
