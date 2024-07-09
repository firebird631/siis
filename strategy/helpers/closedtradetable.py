# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import UTC

from strategy.helpers.closedtradedataset import get_closed_trades

import logging
logger = logging.getLogger('siis.strategy.helpers.closedtradetable')
error_logger = logging.getLogger('siis.error.strategy.helpers.closedtradetable')


def closed_trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None,
                              quantities=False, stats=False, percents=False, pips=False,
                              group=None, ordering=None, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any closed trades.
    @todo cumulative pnl might be computed using trade notional quantity and average by total notional quantity
        to make the difference between strategy having trades of different quantities. could be an option toggle 2
    """
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L', 'Fees', 'OP', 'SL', 'TP', 'TF',
               'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'Status']

    if quantities:
        columns += ['RPNL', 'Qty', 'Entry Q', 'Exit Q']

    if stats:
        columns += ['Cum', 'MFE', 'MAE', 'ETD', 'EEF', 'XEF', 'TEF']

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

        cum_pnl = 0.0
        cum_pnls = {}

        # sort by exit datetime to compute statistics
        if stats:
            closed_trades.sort(key=lambda x: str(x['stats']['last-realized-exit-datetime']))

            for t in closed_trades:
                trade_key = t['symbol']+str(t['id'])

                # sum of RPNL per quote/currency
                if t['stats']['profit-loss-currency'] not in sub_totals:
                    sub_totals[t['stats']['profit-loss-currency']] = 0.0

                sub_totals[t['stats']['profit-loss-currency']] += float(t['stats']['profit-loss'])

                # PNL over the trades and map it to its trade unique key
                cum_pnl += t['profit-loss-pct']
                cum_pnls[trade_key] = cum_pnl

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(closed_trades)

        limit = offset + limit

        if group:
            # in alpha order + last realized exit datetime
            closed_trades.sort(key=lambda x: x['symbol']+str(x['stats']['last-realized-exit-datetime']),
                               reverse=True if ordering else False)
        else:
            closed_trades.sort(key=lambda x: str(x['stats']['last-realized-exit-datetime']),
                               reverse=True if ordering else False)

        closed_trades = closed_trades[offset:limit]

        for t in closed_trades:
            trade_key = t['symbol']+str(t['id'])

            direction = Color.colorize_cond(charmap.ARROWUP if t['direction'] == "long" else charmap.ARROWDN,
                                            t['direction'] == "long", style=style, true=Color.GREEN, false=Color.RED)

            aep = float(t['avg-entry-price'])
            axp = float(t['avg-exit-price'])
            best = float(t['stats']['best-price'])
            worst = float(t['stats']['worst-price'])
            sl = float(t['stop-loss-price'])
            tp = float(t['take-profit-price'])

            # colorize profit or loss percent
            if round(t['profit-loss-pct'] * 10) == 0.0:  # equity
                cr = "%.2f%%" % t['profit-loss-pct']
                exit_color = None
            elif t['profit-loss-pct'] < 0:  # loss
                if (t['direction'] == 'long' and best > aep) or (t['direction'] == 'short' and best < aep):
                    # but was profitable during a time
                    cr = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.ORANGE, style=style)
                    exit_color = Color.ORANGE
                else:
                    cr = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.RED, style=style)
                    exit_color = Color.RED
            elif t['profit-loss-pct'] > 0:  # profit
                if (t['direction'] == 'long' and worst < aep) or (t['direction'] == 'short' and worst > aep):
                    # but was in lost during a time
                    cr = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.BLUE, style=style)
                    exit_color = Color.BLUE
                else:
                    cr = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.GREEN, style=style)
                    exit_color = Color.GREEN
            else:
                cr = "0.0%" if aep else "-"
                exit_color = None

            # realized profit or loss
            rpnl = "%g%s" % (t['stats']['profit-loss'], t['stats']['profit-loss-currency'])

            if exit_color:
                rpnl = Color.colorize(rpnl, exit_color, style=style)

            # colorize TP if hit, similarly for SL, color depends on profit or loss, nothing if close at market
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
                sl_pct = (sl - aep) / aep
                tp_pct = (tp - aep) / aep
            elif t['direction'] == "short" and aep:
                sl_pct = (aep - sl) / aep
                tp_pct = (aep - tp) / aep
            else:
                sl_pct = 0
                tp_pct = 0

            def format_with_percent(formatted_value, condition, rate):
                return (("%s %.2f%%" % (formatted_value,
                                        rate * 100)) if percents else formatted_value) if condition else '-'

            row = [
                t['symbol'],
                t['id'],
                direction,
                cr,
                "%.2f%%" % t['stats']['fees-pct'],  # total fees in percent
                t['order-price'] if t['order-price'] != "0" else "-",
                format_with_percent(_sl, sl, sl_pct),
                format_with_percent(_tp, tp, tp_pct),
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

            if stats:
                # values in percent
                if t['direction'] == "long" and aep and axp:
                    mfe_pct = (best - aep) / aep - (t['stats']['fees-pct'] * 0.01)
                    mae_pct = (worst - aep) / aep - (t['stats']['fees-pct'] * 0.01)

                    etd = best - axp
                    etd_pct = etd / axp - (t['stats']['fees-pct'] * 0.01)
                elif t['direction'] == "short" and aep and axp:
                    mfe_pct = (aep - best) / aep - (t['stats']['fees-pct'] * 0.01)
                    mae_pct = (aep - worst) / aep - (t['stats']['fees-pct'] * 0.01)

                    etd = axp - best
                    etd_pct = etd / axp - (t['stats']['fees-pct'] * 0.01)
                else:
                    mfe_pct = 0
                    mae_pct = 0

                    etd = 0
                    etd_pct = 0

                # Cumulative, MFE, MAE during active...
                fmt_mfe = format_with_percent(t['stats']['best-price'], mfe_pct, mfe_pct)
                fmt_mae = format_with_percent(t['stats']['worst-price'], mae_pct, mae_pct)
                # don't have here the instrument price formatting
                fmt_etd = format_with_percent("%g" % etd, etd_pct, etd_pct)

                # cumulative PNL percent
                cum_pnl = cum_pnls[trade_key]

                # colorize profit or loss percent
                if round(cum_pnl * 10) == 0.0:  # equity
                    fmt_cum_cr = "%.2f%%" % cum_pnl
                elif cum_pnl < 0:  # loss
                    fmt_cum_cr = Color.colorize("%.2f%%" % cum_pnl, Color.RED, style=style)
                elif cum_pnl > 0:  # profit
                    fmt_cum_cr = Color.colorize("%.2f%%" % cum_pnl, Color.GREEN, style=style)
                else:
                    fmt_cum_cr = "-"

                # efficiency
                en_eff_pct = (best - aep) / (best - worst)
                ex_eff_pct = (axp - worst) / (best - worst)
                to_eff_pct = (axp - aep) / (best - worst)

                row.append(fmt_cum_cr)
                row.append(fmt_mfe)
                row.append(fmt_mae)
                row.append(fmt_etd)
                row.append("%.2f%%" % (en_eff_pct * 100.0))
                row.append("%.2f%%" % (ex_eff_pct * 100.0))
                row.append("%.2f%%" % (to_eff_pct * 100.0))

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

        if stats:
            row.append('------')
            row.append('---')
            row.append('---')
            row.append('---')

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
            currency or '-',
            '-',
        ]

        if quantities:
            row.append(rpnl)
            row.append('-')
            row.append('-')
            row.append('-')

        if stats:
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')

        data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size
