# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

from strategy.strategy import Strategy
from strategy.helpers.closedtradedataset import get_closed_trades

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def closed_trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None, quantities=False, percents=False, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any closed trades.
    """
    columns = ['Market', '#', charmap.ARROWUPDN, 'P/L(%)', 'Fees(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF', 'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'RPNL']

    if quantities:
        columns += ['Qty', 'Entry Q', 'Exit Q', 'Status']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []
    
    with strategy._mutex:
        closed_trades = get_closed_trades(strategy)
        total_size = (len(columns), len(closed_trades))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(closed_trades)

        limit = offset + limit

        closed_trades.sort(key=lambda x: -x['lrxot'])
        closed_trades = closed_trades[offset:limit]

        for t in closed_trades:
            direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN, t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

            # @todo direction
            if t['pl'] < 0 and float(t['b']) > float(t['aep']):  # has been profitable but loss
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.ORANGE, style=style)
            elif t['pl'] < 0:  # loss
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.RED, style=style)
            elif t['pl'] > 0:  # profit
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.GREEN, style=style)
            else:
                cr = "0.0"

            aep = float(t['aep'])
            sl = float(t['sl'])
            tp = float(t['tp'])

            # color TP in green if hitted, similarely in red for SL
            # @todo not really true, could store the exit reason in trade stats
            if t['d'] == "long":
                _tp = Color.colorize_cond(t['tp'], tp > 0 and float(t['axp']) >= tp, style=style, true=Color.GREEN)
                _sl = Color.colorize_cond(t['sl'], sl > 0 and float(t['axp']) <= sl, style=style, true=Color.RED)
                slpct = (sl - aep) / aep
                tppct = (tp - aep) / aep
            else:
                _tp = Color.colorize_cond(t['tp'], tp > 0 and float(t['axp']) <= tp, style=style, true=Color.GREEN)
                _sl = Color.colorize_cond(t['sl'], sl > 0 and float(t['axp']) >= sl, style=style, true=Color.RED)
                slpct = (aep - sl) / aep
                tppct = (aep - tp) / aep

            if t['d'] == 'long':
                bpct = (float(t['b']) - aep) / aep
                wpct = (float(t['w']) - aep) / aep
            elif t['d'] == 'short':
                bpct = (aep - float(t['b'])) / aep
                wpct = (aep - float(t['w'])) / aep

            row = [
                t['mid'],
                t['id'],
                direction,
                cr,
                "%.2f%%" % (t['fees'] * 100),
                t['l'],
                "%s (%.2f)" % (_sl, slpct * 100) if percents else _sl,
                "%s (%.2f)" % (_tp, tppct * 100) if percents else _tp,
                "%s (%.2f)" % (t['b'], bpct * 100) if percents else t['b'],
                "%s (%.2f)" % (t['w'], wpct * 100) if percents else t['w'],
                t['tf'],
                datetime.fromtimestamp(t['eot']).strftime(datetime_format),
                datetime.fromtimestamp(t['freot']).strftime(datetime_format),
                t['aep'],
                datetime.fromtimestamp(t['lrxot']).strftime(datetime_format),
                t['axp'],
                t['label'],
                "%s%s" % (t['rpnl'], t['pnlcur'])
            ]

            if quantities:
                row.append(t['q'])
                row.append(t['e'])
                row.append(t['x'])
                row.append(t['s'].capitalize())

            data.append(row[col_ofs:])

    return columns[col_ofs:], data, total_size
