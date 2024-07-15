# @date 2018-08-24alpha
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
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L', 'Fees', 'OP', 'SL', 'TP',
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

    with strategy.mutex:
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

            entry_price = float(t['avg-entry-price'])
            exit_price = float(t['avg-exit-price'])
            best_price = float(t['stats']['best-price'])
            worst_price = float(t['stats']['worst-price'])
            stop_loss_price = float(t['stop-loss-price'])
            take_profit_price = float(t['take-profit-price'])

            # colorize profit or loss percent
            if round(t['profit-loss-pct'] * 10) == 0.0:  # equity
                cr_cum_pct = "%.2f%%" % t['profit-loss-pct']
                exit_color = None
            elif t['profit-loss-pct'] < 0:  # loss
                if (t['direction'] == 'long' and best_price > entry_price) or (t['direction'] == 'short' and best_price < entry_price):
                    # but was profitable during a time
                    cr_cum_pct = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.ORANGE, style=style)
                    exit_color = Color.ORANGE
                else:
                    cr_cum_pct = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.RED, style=style)
                    exit_color = Color.RED
            elif t['profit-loss-pct'] > 0:  # profit
                if (t['direction'] == 'long' and worst_price < entry_price) or (t['direction'] == 'short' and worst_price > entry_price):
                    # but was in lost during a time
                    cr_cum_pct = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.BLUE, style=style)
                    exit_color = Color.BLUE
                else:
                    cr_cum_pct = Color.colorize("%.2f%%" % t['profit-loss-pct'], Color.GREEN, style=style)
                    exit_color = Color.GREEN
            else:
                cr_cum_pct = "0.0%" if entry_price else "-"
                exit_color = None

            # realized profit or loss
            rpnl = "%g%s" % (t['stats']['profit-loss'], t['stats']['profit-loss-currency'])

            if exit_color:
                rpnl = Color.colorize(rpnl, exit_color, style=style)

            # colorize TP if hit, similarly for SL, color depends on profit or loss, nothing if close at market
            if t['stats']['exit-reason'] in ("stop-loss-market", "stop-loss-limit") and exit_color:
                cr_take_profit_price = t['take-profit-price']
                cr_stop_loss_price = Color.colorize(t['stop-loss-price'], exit_color, style=style)
            elif t['stats']['exit-reason'] in ("take-profit-limit", "take-profit-market") and exit_color:
                cr_take_profit_price = Color.colorize(t['take-profit-price'], exit_color, style=style)
                cr_stop_loss_price = t['stop-loss-price']
            else:
                cr_take_profit_price = t['take-profit-price']
                cr_stop_loss_price = t['stop-loss-price']

            # values in percent
            if t['direction'] == "long" and entry_price:
                stop_loss_pct = (stop_loss_price - entry_price) / entry_price
                take_profit_pct = (take_profit_price - entry_price) / entry_price
            elif t['direction'] == "short" and entry_price:
                stop_loss_pct = (entry_price - stop_loss_price) / entry_price
                take_profit_pct = (entry_price - take_profit_price) / entry_price
            else:
                stop_loss_pct = 0
                take_profit_pct = 0

            def format_with_percent(formatted_value, condition, rate):
                return (("%s %.2f%%" % (formatted_value,
                                        rate * 100)) if percents else formatted_value) if condition else '-'

            row = [
                t['symbol'],
                t['id'],
                direction,
                cr_cum_pct,
                "%.2f%%" % t['stats']['fees-pct'],  # total fees in percent
                t['order-price'] if t['order-price'] != "0" else "-",
                format_with_percent(cr_stop_loss_price, stop_loss_price, stop_loss_pct),
                format_with_percent(cr_take_profit_price, take_profit_price, take_profit_pct),
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
                if t['direction'] == "long" and entry_price and exit_price:
                    mfe_pct = (best_price - entry_price) / entry_price
                    mae_pct = (worst_price - entry_price) / entry_price

                    etd = best_price - exit_price
                    etd_pct = etd / exit_price
                elif t['direction'] == "short" and entry_price and exit_price:
                    mfe_pct = (entry_price - best_price) / entry_price
                    mae_pct = (entry_price - worst_price) / entry_price

                    etd = exit_price - best_price
                    etd_pct = etd / exit_price
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
                en_eff_pct = (best_price - entry_price) / (best_price - worst_price)
                ex_eff_pct = (exit_price - worst_price) / (best_price - worst_price)
                to_eff_pct = (exit_price - entry_price) / (best_price - worst_price)

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
