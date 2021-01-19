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
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L(%)', 'Fees(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF', 'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'RPNL']

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

            aep = float(t['aep'])
            best = float(t['b'])
            worst = float(t['w'])
            sl = float(t['sl'])
            tp = float(t['tp'])

            if t['pl'] < 0 and ((t['d'] == 'long' and best > aep) or (t['d'] == 'short' and best < aep)):
                # has been profitable but loss
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.ORANGE, style=style)
            elif t['pl'] < 0:  # loss
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.RED, style=style)
            elif t['pl'] > 0:  # profit
                cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.GREEN, style=style)
            else:
                cr = "0.0" if aep else "-" 

            # color TP in green if hitted, similarely in red for SL
            # @todo not really exact, could use the exit reason
            if t['d'] == "long" and aep:
                _tp = Color.colorize_cond(t['tp'], tp > 0 and float(t['axp']) >= tp, style=style, true=Color.GREEN)
                _sl = Color.colorize_cond(t['sl'], sl > 0 and float(t['axp']) <= sl, style=style, true=Color.RED)
                slpct = (sl - aep) / aep
                tppct = (tp - aep) / aep
            elif t['d'] == "short" and aep:
                _tp = Color.colorize_cond(t['tp'], tp > 0 and float(t['axp']) <= tp, style=style, true=Color.GREEN)
                _sl = Color.colorize_cond(t['sl'], sl > 0 and float(t['axp']) >= sl, style=style, true=Color.RED)
                slpct = (aep - sl) / aep
                tppct = (aep - tp) / aep
            else:
                _tp = str(t['sl'])
                _sl = str(t['tp'])
                slpct = 0
                tppct = 0

            if t['d'] == 'long' and aep:
                bpct = (best - aep) / aep - t['fees']
                wpct = (worst - aep) / aep - t['fees']
            elif t['d'] == 'short' and aep:
                bpct = (aep - best) / aep - t['fees']
                wpct = (aep - worst) / aep - t['fees']
            else:
                bpct = 0
                wpct = 0

            def format_with_percent(formated_value, condition, rate):
                return (("%s (%.2f%%)" % (formated_value, rate * 100)) if percents else formated_value) if condition else '-'

            row = [
                t['sym'],
                t['id'],
                direction,
                cr,
                "%.2f%%" % (t['fees'] * 100),  # fee rate converted in percent
                t['l'],
                format_with_percent(_sl, sl, slpct),
                format_with_percent(_tp, tp, tppct),
                format_with_percent(t['b'], best, bpct),
                format_with_percent(t['w'], worst, wpct),
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

            data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size
