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
    columns = ('Market', 'Symbol', 'Base', 'Quote', 'Settlement', 'Type', 'Unit', 'Status',
               'PipMean', 'PerPip',
               'Lot', 'Contract',
               'Size Limits', 'Price Limits', 'Notional Limits',
               'Leverage', 'Hedge')

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

        def float_fmt(value, placeholder='-'):
            return str("%.12f" % value).rstrip('0').rstrip('.') if value else placeholder

        for market in markets:
            status = Color.colorize_cond("Open" if market.is_open else "Close", market.is_open, style=style,
                                         true=Color.GREEN, false=Color.RED)

            min_leverage = market.min_leverage
            max_leverage = market.max_leverage

            if min_leverage != max_leverage and max_leverage > 1.0:
                # have min/max only on live
                leverage = "%.2f (%s..%s)" % ((round(1.0 / market.margin_factor) if market.margin_factor > 0.0 else 1.0),
                                              market.min_leverage, market.max_leverage)
            elif market.margin_factor > 0.0 and market.margin_factor != 1.0:
                # else we have only the default margin factor (usually the max)
                leverage = float_fmt(round(1.0 / market.margin_factor))
            else:
                # invalid or rate of 1.0 mean no leverage
                leverage = '-'

            row = (
                market.market_id,
                market.symbol,
                "%s e%s" % (market.base, -market.base_precision),
                "%s e%s" % (market.quote, -market.quote_precision),
                "%s e%s" % (market.settlement, -market.settlement_precision) if market.settlement else '-',
                market.market_type_str().capitalize(),
                market.unit_type_str().capitalize(),
                status,
                float_fmt(market.one_pip_means),
                float_fmt(market.value_per_pip),
                float_fmt(market.lot_size),
                float_fmt(market.contract_size),
                "%s..%s ±%s" % (float_fmt(market.min_size, '0'),
                                float_fmt(market.max_size, '∞'),
                                float_fmt(market.step_size, float_fmt(market.min_size, '1'))),
                "%s..%s ±%s" % (float_fmt(market.min_price, '0'),
                                float_fmt(market.max_price, '∞'),
                                float_fmt(market.step_price, float_fmt(market.min_price, '1'))),
                "%s..%s ±%s" % (float_fmt(market.min_notional, '0'),
                                float_fmt(market.max_notional, '∞'),
                                float_fmt(market.step_notional, '1')),
                leverage,
                'Yes' if market.hedging else 'No'  # '✓' if market.hedging else '𐄂'
            )

            data.append(row[0:2] + row[2+col_ofs:])

    return columns[0:2] + columns[2+col_ofs:], data, total_size
