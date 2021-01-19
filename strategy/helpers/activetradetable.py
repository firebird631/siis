# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
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
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF', 'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'UPNL']

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
                cr = "0.00" if aep else "-" 

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

            # pct from last exec open price
            if op and (t['s'] in ('new', 'opened', 'filling')):
                if t['d'] == 'long':
                    leop = float(t['leop'])
                    oppct = (op - leop) / op
                elif t['d'] == 'short':
                    leop = float(t['leop'])
                    oppct = (op - leop) / op
                else:
                    oppct = 0
            else:
                oppct = 0

            def format_with_percent(formated_value, condition, rate):
                return (("%s (%.2f%%)" % (formated_value, rate * 100)) if percents else formated_value) if condition else '-'

            op = (("%s (%.2f%%)" % (t['l'], oppct * 100)) if percents and oppct else t['l']) if op else '-'

            sl = format_with_percent(t['sl'], sl, slpct)
            tp = format_with_percent(t['tp'], tp, tppct)

            b = format_with_percent(t['b'], best, bpct)
            w = format_with_percent(t['w'], worst, wpct)

            upnl = "%s%s" % (t['upnl'], t['pnlcur']) if aep else '-'

            row = [
                t['sym'],
                t['id'],
                direction,
                cr,
                op,
                sl,
                tp,
                b,
                w,
                t['tf'],
                datetime.fromtimestamp(t['eot']).strftime(datetime_format) if t['eot'] > 0 else '-',
                datetime.fromtimestamp(t['freot']).strftime(datetime_format) if t['freot'] > 0 else '-',
                t['aep'] if t['aep'] != '0' else '-',
                datetime.fromtimestamp(t['lrxot']).strftime(datetime_format) if t['lrxot'] > 0 else '-',
                t['axp'] if t['axp'] != '0' else '-',
                t['label'],
                upnl,
            ]

            if quantities:
                row.append(t['q'])
                row.append(t['e'])
                row.append(t['x'])
                row.append(t['s'].capitalize())

            data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size
