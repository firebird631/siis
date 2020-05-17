# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

from strategy.strategy import Strategy

from strategy.helpers.activetradedataset import get_all_active_trades

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None, quantities=False, percents=False, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any active trades.
    """
    columns = ['Market', '#', charmap.ARROWUPDN, 'P/L(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF', 'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'UPNL']

    if quantities:
        columns += ['Qty', 'Entry Q', 'Exit Q', 'Status']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []

    with strategy._mutex:
        trades = get_all_active_trades(strategy)
        total_size = (len(columns), len(trades))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(trades)

        limit = offset + limit

        trades.sort(key=lambda x: x['eot'])
        trades = trades[offset:limit]

        for t in trades:
            direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN, t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

            aep = float(t['aep'])
            best = float(t['b'])
            worst = float(t['w'])
            op = float(t['l'])
            sl = float(t['sl'])
            tp = float(t['tp'])

            if t['pl'] < 0 and ((t['d'] == 'long' and best > aep) or (t['d'] == 'short' and best < aep)):
                # has been profitable but loss
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.ORANGE, style=style)
            elif t['pl'] < 0:  # loss
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.RED, style=style)
            elif t['pl'] > 0:  # profit
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.GREEN, style=style)
            else:  # equity
                cr = "0.0"

            if t['d'] == 'long' and aep > 0 and best > 0 and worst > 0:
                bpct = (best - aep) / aep - t['fees']
                wpct = (worst - aep) / aep - t['fees']
            elif t['d'] == 'short' and aep > 0 and best > 0 and worst > 0:
                bpct = (aep - best) / aep - t['fees']
                wpct = (aep - worst) / aep - t['fees']
            else:
                bpct = 0
                wpct = 0

            if t['d'] == 'long' and (aep or op):
                slpct = (sl - (aep or op)) / (aep or op)
                tppct = (tp - (aep or op)) / (aep or op)
            elif t['d'] == 'short' and (aep or op):
                slpct = ((aep or op) - sl) / (aep or op)
                tppct = ((aep or op) - tp) / (aep or op)
            else:
                slpct = 0
                tppct = 0

            row = [
                t['mid'],
                t['id'],
                direction,
                cr,
                t['l'],
                "%s (%.2f)" % (t['sl'], slpct * 100) if percents else t['sl'],
                "%s (%.2f)" % (t['tp'], tppct * 100) if percents else t['tp'],
                "%s (%.2f)" % (t['b'], bpct * 100) if percents else t['b'],
                "%s (%.2f)" % (t['w'], wpct * 100) if percents else t['w'],
                t['tf'],
                datetime.fromtimestamp(t['eot']).strftime(datetime_format) if t['eot'] > 0 else "",
                datetime.fromtimestamp(t['freot']).strftime(datetime_format) if t['freot'] > 0 else "",
                t['aep'],
                datetime.fromtimestamp(t['lrxot']).strftime(datetime_format) if t['lrxot'] > 0 else "",
                t['axp'],
                t['label'],
                "%s%s" % (t['upnl'], t['pnlcur'])
            ]

            if quantities:
                row.append(t['q'])
                row.append(t['e'])
                row.append(t['x'])
                row.append(t['s'].capitalize())

            data.append(row[col_ofs:])

    return columns[col_ofs:], data, total_size
