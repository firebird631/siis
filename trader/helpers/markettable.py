# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging

from terminal.terminal import Color

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def markets_table(trader, style='', offset=None, limit=None, col_ofs=None, group=None, ordering=None):
    """
    Returns a table of any followed markets.
    """
    columns = ('Market', 'Symbol', 'Base', 'Quote', 'Rate', 'Type', 'Unit', 'Status', 'PipMean', 'PerPip',
               'Lot', 'Contract', 'Min Size', 'Max Size', 'Step Size', 'Min Price', 'Max Price', 'Step Price',
               'Min Notional', 'Max Notional', 'Step Notional', 'Leverage', 'Base ER', 'Hedge')

    total_size = (len(columns), 0)
    data = []

    with trader.mutex:
        markets = list(trader._markets.values())
        total_size = (len(columns), len(markets))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(markets)

        limit = offset + limit

        markets.sort(key=lambda x: x.symbol, reverse=True if ordering else False)
        markets = markets[offset:limit]

        for market in markets:
            status = Color.colorize_cond("Open" if market.is_open else "Close", market.is_open, style=style,
                                         true=Color.GREEN, false=Color.RED)

            min_leverage = market.min_leverage
            max_leverage = market.max_leverage

            if min_leverage != max_leverage and max_leverage > 1.0:
                leverage = "%.2f (%s..%s)" % ((1.0 / market.margin_factor if market.margin_factor > 0.0 else 1.0),
                                              market.min_leverage, market.max_leverage)
            else:
                leverage = '-'

            row = (
                market.market_id,
                market.symbol,
                market.base,
                market.quote,
                str("%.8f" % market.base_exchange_rate).rstrip('0').rstrip('.'),
                market.market_type_str().capitalize(),
                market.unit_type_str().capitalize(),
                status,
                str("%.8f" % market.one_pip_means).rstrip('0').rstrip('.'),
                str("%.8f" % market.value_per_pip).rstrip('0').rstrip('.'),
                str("%.8f" % market.lot_size).rstrip('0').rstrip('.'),
                str("%.12f" % market.contract_size).rstrip('0').rstrip('.'),
                market.min_size or '-',
                market.max_size or '-',
                market.step_size or '-',
                market.min_price or '-',
                market.max_price or '-',
                market.step_price or '-',
                market.min_notional or '-',
                market.max_notional or '-',
                market.step_notional or '-',
                leverage,
                "%.g" % market.base_exchange_rate,
                'Yes' if market.hedging else 'No'
            )

            data.append(row[0:2] + row[2+col_ofs:])

    return columns[0:2] + columns[2+col_ofs:], data, total_size
