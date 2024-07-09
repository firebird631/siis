# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging

from terminal.terminal import Color

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def assets_table(trader, style='', offset=None, limit=None, col_ofs=None,
                 filter_low=True, compute_qty=False, percent=False,
                 group=None, ordering=None):
    """
    Returns a table of any non-empty assets.
    """
    columns = ('Asset', 'Locked', 'Free', 'Total', 'Avg price', 'Change', 'P/L', 'Quote', 'Pref Market')

    total_size = (len(columns), 0)
    data = []

    with trader.mutex:
        assets = [asset for asset in trader._assets.values() if asset.quantity > 0.0]
        total_size = (len(columns), len(assets))

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
        computed_qty = {}

        if compute_qty:
            for order_id, order in trader._orders.items():
                market = trader._markets.get(order.symbol)

                if market.has_spot:
                    if order.direction == order.SHORT:
                        # locked asset
                        asset_qty = order.quantity - order.executed

                        if market.base not in computed_qty:
                            computed_qty[market.base] = 0.0

                        computed_qty[market.base] = computed_qty[market.base] + asset_qty
                    else:
                        # locked quote
                        quote_qty = market.effective_cost(order.quantity - order.executed, market.market_price)

                        if market.quote not in computed_qty:
                            computed_qty[market.quote] = 0.0

                        computed_qty[market.quote] = computed_qty[market.quote] + quote_qty

        for asset in assets:
            # use the most appropriate market
            market_id = asset.market_ids[0] if asset.market_ids else asset.symbol+asset.quote if asset.quote else None
            market = trader._markets.get(market_id)

            fmt_change = ""
            fmt_profit_loss = ""

            if market:
                if compute_qty and market.has_spot:
                    locked_qty = computed_qty.get(asset.symbol, 0.0)

                    fmt_locked = market.format_quantity(locked_qty)
                    fmt_free = market.format_quantity(asset.quantity - locked_qty)
                    fmt_quantity = market.format_quantity(asset.quantity)
                else:
                    fmt_locked = market.format_quantity(asset.locked)
                    fmt_free = market.format_quantity(asset.free)
                    fmt_quantity = market.format_quantity(asset.quantity)

                if market.bid and asset.price:
                    fmt_change = market.format_price(market.bid - asset.price) + market.quote_display or market.quote

                    if percent:
                        change_pct = (market.bid - asset.price) / asset.price if asset.price else 0.0
                        fmt_change = "%s %.2f%%" % (fmt_change, change_pct * 100.0)

                        if change_pct > 0.0:
                            fmt_change = Color.colorize(fmt_change, Color.GREEN, style)
                        elif change_pct < 0.0:
                            fmt_change = Color.colorize(fmt_change, Color.RED, style)

                if asset.quantity > 0.0:
                    fmt_profit_loss = market.format_price(asset.profit_loss)

                    if asset.profit_loss > 0.0:
                        if fmt_profit_loss:
                            fmt_profit_loss = Color.colorize(fmt_profit_loss, Color.GREEN, style)
                    elif asset.profit_loss < 0.0:
                        if fmt_profit_loss:
                            fmt_profit_loss = Color.colorize(fmt_profit_loss, Color.RED, style)

                    fmt_profit_loss += market.quote_display or market.quote
            else:
                fmt_locked = ("%.8f" % asset.locked).rstrip('0').rstrip('.')
                fmt_free = ("%.8f" % asset.free).rstrip('0').rstrip('.')
                fmt_quantity = ("%.8f" % asset.quantity).rstrip('0').rstrip('.')

            row = (
                asset.symbol,
                fmt_locked,
                fmt_free,
                fmt_quantity,
                "%s%s" % (asset.format_price(asset.price), asset.quote) if asset.price else '-',  # charmap.HOURGLASS,
                fmt_change or '-',
                fmt_profit_loss or '-',
                asset.quote or '-',
                asset.market_ids[0] if asset.market_ids else '-'
            )

            data.append(row[0:1] + row[1+col_ofs:])

    return columns[0:1] + columns[1+col_ofs:], data, total_size
