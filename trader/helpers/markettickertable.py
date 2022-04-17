# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging
import time

from datetime import timedelta, datetime

from terminal.terminal import Color

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def markets_tickers_table(trader, style='', offset=None, limit=None, col_ofs=None, prev_timestamp=None,
                          group=None, ordering=None):
    """
    Returns a table of any followed markets tickers.
    """
    columns = ('Market', 'Symbol', 'Mid', 'Bid', 'Ask', 'Spread', 'Vol24h base', 'Vol24h quote',
               'Time', 'Change(%)', 'Last', 'At')

    total_size = (len(columns), 0)
    data = []
    now = time.time()

    with trader.mutex:
        markets = list(trader._markets.values())
        total_size = (len(columns), len(markets))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(markets)

        limit = offset + limit

        if group:
            markets.sort(key=lambda x: x.price, reverse=True if ordering else False)
        else:
            markets.sort(key=lambda x: x.symbol, reverse=True if ordering else False)

        markets = markets[offset:limit]

        for market in markets:
            # recent = market.recent(trader.timestamp - 0.5 if not prev_timestamp else prev_timestamp)
            recent = market.previous(-2)
            if recent:
                mid = Color.colorize_updn(market.format_price(market.price), (recent[1]+recent[2])*0.5,
                                          market.price, style=style)
                bid = Color.colorize_updn(market.format_price(market.bid), recent[1], market.bid, style=style)
                ask = Color.colorize_updn(market.format_price(market.ask), recent[2], market.ask, style=style)
                spread = Color.colorize_updn(market.format_spread(market.spread),
                                             market.spread, recent[2] - recent[1], style=style)
            else:
                mid = market.format_price(market.price)
                bid = market.format_price(market.bid)
                ask = market.format_price(market.ask)
                spread = market.format_spread(market.spread)

            if market.last_trade_dir != 0:
                last_trade = Color.colorize_cond(market.format_price(market.last_trade), market.last_trade_dir > 0,
                                                 style=style, true=Color.GREEN, false=Color.RED)
            else:
                last_trade = market.format_price(market.last_trade) if market.last_trade else '-'

            if market.vol24h_quote:
                if market.quote in ('USD', 'EUR', 'CAD', 'JPY', 'CHF', 'CHN',
                                    'ZUSD', 'ZEUR', 'ZCAD', 'ZJPY', 'ZCHF',
                                    'USDT', 'PAX', 'DAI', 'USDC', 'USDS', 'BUSD', 'TUSD'):
                    low = 500000
                elif market.quote in ('BTC', 'XBT', 'XXBT'):
                    low = 100
                elif market.quote in ('ETH', 'XETH'):
                    low = 5000
                elif market.quote in ('BNB',):
                    low = 50000
                else:
                    low = 0

                vol24h_quote = Color.colorize_cond("%.2f" % market.vol24h_quote, market.vol24h_quote < low,
                                                   style=style, true=Color.YELLOW, false=Color.WHITE)
            else:
                vol24h_quote = '-'  # charmap.HOURGLASS

            if market.last_update_time > 0:
                last_timestamp = datetime.fromtimestamp(market.last_update_time).strftime("%H:%M:%S")

                # color ticker since last receive (>15m, >30m)
                if trader.timestamp - market.last_update_time > 60*30.0:
                    last_timestamp = Color.colorize(last_timestamp, Color.RED, style)
                elif trader.timestamp - market.last_update_time > 60*15.0:
                    last_timestamp = Color.colorize(last_timestamp, Color.ORANGE, style)
                else:
                    last_timestamp = Color.colorize(last_timestamp, Color.GREEN, style)
            else:
                last_timestamp = '-'  # charmap.HOURGLASS

            if market.last_trade_timestamp > 0:
                last_trade_timestamp = datetime.fromtimestamp(market.last_trade_timestamp).strftime("%H:%M:%S")

                # color last trade since last receive (>15m, >30m)
                if trader.timestamp - market.last_trade_timestamp > 60*30.0:
                    last_trade_timestamp = Color.colorize(last_trade_timestamp, Color.RED, style)
                elif trader.timestamp - market.last_trade_timestamp > 60*15.0:
                    last_trade_timestamp = Color.colorize(last_trade_timestamp, Color.ORANGE, style)
                else:
                    last_trade_timestamp = Color.colorize(last_trade_timestamp, Color.GREEN, style)
            else:
                last_trade_timestamp = '-'  # charmap.HOURGLASS

            # relative change in percent
            if not market.last_mem:
                market.mem_set()

            relative_change = (market.price - market.last_mem) / market.last_mem * 100.0 if market.last_mem else 0

            if relative_change != 0.0:
                relative_change = Color.colorize_cond("%.2f" % relative_change, relative_change > 0,
                                                      style=style, true=Color.GREEN, false=Color.RED)

                relative_change += " since %s" % str(timedelta(seconds=int(now - market.last_mem_timestamp)))

            row = (
                market.market_id,
                market.symbol,
                mid,
                bid,
                ask,
                spread,
                market.format_quantity(market.vol24h_base) if market.vol24h_base else '-',  # charmap.HOURGLASS,
                vol24h_quote,
                last_timestamp,
                relative_change,
                last_trade,
                last_trade_timestamp)

            data.append(row[0:2] + row[2+col_ofs:])

    return columns[0:2] + columns[2+col_ofs:], data, total_size
