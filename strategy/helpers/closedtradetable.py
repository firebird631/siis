# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import UTC

from strategy.strategy import Strategy
from strategy.helpers.closedtradedataset import get_closed_trades

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def closed_trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None, quantities=False,
                              percents=False, group=False, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any closed trades.
    """
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L(%)', 'Fees(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF',
               'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'Status']

    if quantities:
        columns += ['RPNL', 'Qty', 'Entry Q', 'Exit Q']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []
    sub_totals = {}

    def localize_datetime(dt):
        return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC()).astimezone().strftime(
            datetime_format) if dt else "-"

    with strategy._mutex:
        closed_trades = get_closed_trades(strategy)
        total_size = (len(columns), len(closed_trades))

        for t in closed_trades:
            # sum of RPNL per quote/currency
            if t['stats']['profit-loss-currency'] not in sub_totals:
                sub_totals[t['stats']['profit-loss-currency']] = 0.0

            sub_totals[t['stats']['profit-loss-currency']] += float(t['stats']['profit-loss'])

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(closed_trades)

        limit = offset + limit

        if group:
            # in alpha order
            closed_trades.sort(key=lambda x: x['symbol'])
        else:
            closed_trades.sort(key=lambda x: x['stats']['last-realized-exit-datetime'], reverse=True)

        closed_trades = closed_trades[offset:limit]

        for t in closed_trades:
            direction = Color.colorize_cond(charmap.ARROWUP if t['direction'] == "long" else charmap.ARROWDN,
                                            t['direction'] == "long", style=style, true=Color.GREEN, false=Color.RED)

            aep = float(t['avg-entry-price'])
            axp = float(t['avg-exit-price'])
            best = float(t['stats']['best-price'])
            worst = float(t['stats']['worst-price'])
            sl = float(t['stop-loss-price'])
            tp = float(t['take-profit-price'])

            # colorize profit or loss percent
            if t['profit-loss-pct'] < 0:  # loss
                if (t['direction'] == 'long' and best > aep) or (t['direction'] == 'short' and best < aep):
                    # but was profitable during a time
                    cr = Color.colorize("%.2f" % t['profit-loss-pct'], Color.ORANGE, style=style)
                    exit_color = Color.ORANGE
                else:
                    cr = Color.colorize("%.2f" % t['profit-loss-pct'], Color.RED, style=style)
                    exit_color = Color.RED

            elif t['profit-loss-pct'] > 0:  # profit
                if (t['direction'] == 'long' and worst < aep) or (t['direction'] == 'short' and worst > aep):
                    # but was in lost during a time
                    cr = Color.colorize("%.2f" % t['profit-loss-pct'], Color.BLUE, style=style)
                    exit_color = Color.BLUE
                else:
                    cr = Color.colorize("%.2f" % t['profit-loss-pct'], Color.GREEN, style=style)
                    exit_color = Color.GREEN

            else:  # equity
                cr = "0.0" if aep else "-"
                exit_color = None

            # realized profit or loss
            rpnl = "%g%s" % (t['stats']['profit-loss'], t['stats']['profit-loss-currency'])

            if exit_color:
                rpnl = Color.colorize(rpnl, exit_color, style=style)

            # colorize TP if hit, similarly for SL, color depend if profit or loss, nothing if close at market
            if t['stats']['exit-reason'] in ("stop-loss-market", "stop-loss-limit") and exit_color:
                _tp = t['take-profit-price']
                _sl = Color.colorize(t['stop-loss-price'], exit_color, style=style)

            elif t['stats']['exit-reason'] in ("take-profit-limit", "take-profit-market") and exit_color:
                _tp = Color.colorize(t['take-profit-price'], exit_color, style=style)
                _sl = t['stop-loss-price']

            else:
                _tp = t['take-profit-price']
                _sl = t['stop-loss-price']

            # values in percent
            if t['direction'] == "long" and aep:
                slpct = (sl - aep) / aep
                tppct = (tp - aep) / aep

                bpct = (best - aep) / aep - (t['stats']['fees-pct'] * 0.01)
                wpct = (worst - aep) / aep - (t['stats']['fees-pct'] * 0.01)

            elif t['direction'] == "short" and aep:
                slpct = (aep - sl) / aep
                tppct = (aep - tp) / aep

                bpct = (aep - best) / aep - (t['stats']['fees-pct'] * 0.01)
                wpct = (aep - worst) / aep - (t['stats']['fees-pct'] * 0.01)

            else:
                slpct = 0
                tppct = 0

                bpct = 0
                wpct = 0

            def format_with_percent(formatted_value, condition, rate):
                return (("%s (%.2f%%)" % (formatted_value,
                                          rate * 100)) if percents else formatted_value) if condition else '-'

            row = [
                t['symbol'],
                t['id'],
                direction,
                cr,
                "%.2f%%" % t['stats']['fees-pct'],  # total fees in percent
                t['order-price'],
                format_with_percent(_sl, sl, slpct),
                format_with_percent(_tp, tp, tppct),
                format_with_percent(t['stats']['best-price'], best, bpct),
                format_with_percent(t['stats']['worst-price'], worst, wpct),
                t['timeframe'],
                localize_datetime(t['entry-open-time']),
                localize_datetime(t['stats']['first-realized-entry-datetime']),
                t['avg-entry-price'],
                localize_datetime(t['stats']['last-realized-exit-datetime']),
                t['avg-exit-price'],
                t['label'],
                t['state'].capitalize(),
            ]

            if quantities:
                row.append(rpnl)
                row.append(t['order-qty'])
                row.append(t['filled-entry-qty'])
                row.append(t['filled-exit-qty'])

            data.append(row[0:4] + row[4+col_ofs:])

    if sub_totals:
        row = [
            "------",
            '-',
            '-',
            '------',
            '-------',
            '--',
            '--',
            '--',
            '----',
            '-----',
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

        data.append(row[0:4] + row[4+col_ofs:])

    for currency, sub_total in sub_totals.items():
        if sub_total > 0:
            rpnl = Color.colorize("%g%s" % (sub_total, currency), Color.GREEN, style=style)
        elif sub_total < 0:
            rpnl = Color.colorize("%g%s" % (sub_total, currency), Color.RED, style=style)
        else:
            rpnl = "%g%s" % (sub_total, currency)

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
            '-',
            currency,
            '-',
        ]

        if quantities:
            row.append(rpnl)
            row.append('-')
            row.append('-')
            row.append('-')

        data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size
