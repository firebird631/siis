# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from strategy.helpers.activetradedataset import get_all_active_trades

import logging
logger = logging.getLogger('siis.strategy.helpers.activetradetable')
error_logger = logging.getLogger('siis.error.strategy.helpers.activetradetable')


def trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None,
                       quantities=False, stats=False,
                       percents=False, pips=False,
                       group=None, ordering=None,
                       datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any active trades.
    """
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L', 'OP', 'SL', 'TP', 'TF', 'Signal date',
               'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'Status']

    if quantities:
        columns += ['UPNL', 'Qty', 'Entry Q', 'Exit Q', 'Quote']

    if stats:
        columns += ['MFE', 'MAE']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []
    num_actives_trades = 0
    sub_totals = {}

    with strategy._mutex:
        trades = get_all_active_trades(strategy)
        total_size = (len(columns), len(trades))

        for t in trades:
            aep = float(t['aep'])

            # count actives trades for all trades with filled (partial or complete) quantity
            if aep > 0:
                num_actives_trades += 1

            # sum of UPNL per quote/currency
            if t['pnlcur'] not in sub_totals:
                sub_totals[t['pnlcur']] = 0.0

            sub_totals[t['pnlcur']] += float(t['upnl'])

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(trades)

        limit = offset + limit

        if group:
            # filled first, and in alpha order + entry order timestamp
            trades.sort(key=lambda x: x['sym']+str(x['eot']) if x['e'] != "0" else ' '+x['sym']+str(x['eot']),
                        reverse=True if ordering else False)
        else:
            # by entry order timestamp
            trades.sort(key=lambda x: x['eot'], reverse=True if ordering else False)

        trades = trades[offset:limit]

        for t in trades:
            fmt_direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN,
                                            t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

            aep = float(t['aep'])
            best = float(t['b'])
            worst = float(t['w'])
            op = float(t['l'])
            sl = float(t['sl'])
            tp = float(t['tp'])
            leop = float(t['leop'])

            fmt_upnl = "%s%s" % (t['upnl'], t['pnlcur']) if aep else '-'

            if pips:
                fmt_pnl = "%spts" % t['entry-dist-pips']
            else:
                fmt_pnl = "%.2f%%" % (t['pl'] * 100.0)

            if t['pl'] < 0:  # loss
                if (t['d'] == 'long' and best > aep) or (t['d'] == 'short' and best < aep):
                    # but was profitable during a time
                    fmt_pnl = Color.colorize(fmt_pnl, Color.ORANGE, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.ORANGE, style=style)
                else:
                    fmt_pnl = Color.colorize(fmt_pnl, Color.RED, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.RED, style=style)
            elif t['pl'] > 0:  # profit
                if (t['d'] == 'long' and best > aep) or (t['d'] == 'short' and best < aep):
                    # but was in lost during a time
                    fmt_pnl = Color.colorize(fmt_pnl, Color.BLUE, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.BLUE, style=style)
                else:
                    fmt_pnl = Color.colorize(fmt_pnl, Color.GREEN, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.GREEN, style=style)

            else:  # equity
                fmt_pnl = "0.00%" if aep else "-"

            if t['d'] == 'long' and aep > 0 and best > 0 and worst > 0:
                best_pct = (best - aep) / aep - t['fees']
                worst_pct = (worst - aep) / aep - t['fees']
            elif t['d'] == 'short' and aep > 0 and best > 0 and worst > 0:
                best_pct = (aep - best) / aep - t['fees']
                worst_pct = (aep - worst) / aep - t['fees']
            else:
                best_pct = 0
                worst_pct = 0

            if t['d'] == 'long' and (aep or op):
                sl_pct = (sl - (aep or op)) / (aep or op)
                tp_pct = (tp - (aep or op)) / (aep or op)
            elif t['d'] == 'short' and (aep or op):
                sl_pct = ((aep or op) - sl) / (aep or op)
                tp_pct = ((aep or op) - tp) / (aep or op)
            else:
                sl_pct = 0
                tp_pct = 0

            # percent from last exec open price
            if op and (t['s'] in ('new', 'opened', 'filling')):
                if t['d'] == 'long':
                    op_pct = (op - leop) / op
                elif t['d'] == 'short':
                    op_pct = (op - leop) / op
                else:
                    op_pct = 0
            else:
                op_pct = 0

            def format_with_percent(formatted_value, condition, rate):
                return (("%s %.2f%%" % (formatted_value,
                                        rate * 100)) if percents else formatted_value) if condition else '-'

            if pips:
                fmt_op = (("%spts %.2f%%" % (t['order-dist-pips'], op_pct * 100)) if
                          percents and op_pct else t['order-dist-pips'] + "pts") if op else '-'

                fmt_sl = format_with_percent(t['stop-loss-dist-pips'] + "pts", sl, sl_pct)
                fmt_tp = format_with_percent(t['take-profit-dist-pips'] + "pts", tp, tp_pct)
            else:
                fmt_op = (("%s %.2f%%" % (t['l'], op_pct * 100)) if percents and op_pct else t['l']) if op else '-'

                fmt_sl = format_with_percent(t['sl'], sl, sl_pct)
                fmt_tp = format_with_percent(t['tp'], tp, tp_pct)

            row = [
                t['sym'],
                t['id'],
                fmt_direction,
                fmt_pnl if leop else charmap.HOURGLASS,
                fmt_op,
                fmt_sl,
                fmt_tp,
                t['tf'],
                datetime.fromtimestamp(t['eot']).strftime(datetime_format) if t['eot'] > 0 else '-',
                datetime.fromtimestamp(t['freot']).strftime(datetime_format) if t['freot'] > 0 else '-',
                t['aep'] if t['aep'] != '0' else '-',
                datetime.fromtimestamp(t['lrxot']).strftime(datetime_format) if t['lrxot'] > 0 else '-',
                t['axp'] if t['axp'] != '0' else '-',
                t['label'],
                t['s'].capitalize(),
            ]

            if quantities:
                row.append(fmt_upnl)
                row.append(t['q'])
                row.append(t['e'])
                row.append(t['x'])
                row.append(t['qs'])

            if stats:
                # MFE, MAE when active
                if pips:
                    fmt_mfe = format_with_percent(t['mae-dist-pips'] + "pts", best, best_pct)
                    fmt_mae = format_with_percent(t['mfe-dist-pips'] + "pts", worst, worst_pct)
                else:
                    fmt_mfe = format_with_percent(t['b'], best, best_pct)
                    fmt_mae = format_with_percent(t['w'], worst, worst_pct)

                row.append(fmt_mfe)
                row.append(fmt_mae)

            data.append(row[0:4] + row[4+col_ofs:])

    if sub_totals:
        row = [
            "------",
            '-',
            '-',
            '------',
            '--',
            '--',
            '--',
            '--',
            '-----------',
            '----------',
            '------',
            '---------',
            '------',
            '-----',
            '------',
        ]

        if quantities:
            row.append('----')
            row.append('---')
            row.append('-------')
            row.append('------')
            row.append('-----')

        if stats:
            row.append('---')
            row.append('---')

        data.append(row[0:4] + row[4+col_ofs:])

    for currency, sub_total in sub_totals.items():
        if sub_total > 0:
            fmt_upnl = Color.colorize("%g%s" % (sub_total, currency), Color.GREEN, style=style)
        elif sub_total < 0:
            fmt_upnl = Color.colorize("%g%s" % (sub_total, currency), Color.RED, style=style)
        else:
            fmt_upnl = "%g%s" % (sub_total, currency)

        row = [
            "SUB",
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            '-',
            currency,
            '-',
        ]

        if quantities:
            row.append(fmt_upnl)
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')

        data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size, num_actives_trades
