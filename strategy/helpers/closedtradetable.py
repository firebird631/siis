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
    @todo cumulative pnl in percentage could have an option to compute relative to its notional size. like this it
     could compare performance x size and not only performance between trades (use toggles opt2)
    @todo fmt_etd no have price formatter
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

            fmt_direction = Color.colorize_cond(charmap.ARROWUP if t['direction'] == "long" else charmap.ARROWDN,
                                                t['direction'] == "long", style=style,
                                                true=Color.GREEN, false=Color.RED)

            direction = 1 if t['direction'] == "long" else -1 if t['direction'] == "short" else 0
            entry_price = float(t['avg-entry-price'])
            exit_price = float(t['avg-exit-price'])
            best_price = float(t['stats']['best-price'])
            worst_price = float(t['stats']['worst-price'])
            stop_loss = float(t['stop-loss-price'])
            take_profit = float(t['take-profit-price'])
            fees_pct = float(t['stats']['fees-pct'])

            # colorize profit or loss percent
            if round(t['profit-loss-pct'] * 10) == 0.0:  # equity
                exit_color = None
            elif t['profit-loss-pct'] < 0:  # loss
                if (direction > 0 and best_price > entry_price) or (direction < 0 and best_price < entry_price):
                    # but was profitable during a time
                    exit_color = Color.ORANGE
                else:
                    exit_color = Color.RED
            elif t['profit-loss-pct'] > 0:  # profit
                if (direction > 0 and worst_price < entry_price) or (direction < 0 and worst_price > entry_price):
                    # but was in lost during a time
                    exit_color = Color.BLUE
                else:
                    exit_color = Color.GREEN
            else:
                exit_color = None

            # realized profit or loss percentage and currency
            fmt_pnl_pct = "%.2f%%" % t['profit-loss-pct']
            fmt_rpnl = "%g%s" % (t['stats']['profit-loss'], t['stats']['profit-loss-currency'])

            # values in percent
            if entry_price:
                stop_loss_pct = direction * (stop_loss - entry_price) / entry_price
                take_profit_pct = direction * (take_profit - entry_price) / entry_price
            else:
                stop_loss_pct = 0
                take_profit_pct = 0

            def format_with_percent(formatted_value, condition, rate):
                return (("%s %.2f%%" % (formatted_value,
                                        rate * 100)) if percents else formatted_value) if condition else '-'

            def fmt_pips(value):
                return ("%.2f" % value).rstrip('0').rstrip('.')

            # display in pips or price, with or without percentage
            if pips:
                # pips w/wo percentage
                pip_means = t['stats'].get('one-pip-means', 1.0) or 1.0

                if entry_price:
                    stop_loss_dist_pips = (direction * (stop_loss - entry_price)) / pip_means
                    take_profit_dist_pips = (direction * (take_profit - entry_price)) / pip_means
                else:
                    stop_loss_dist_pips = 0.0
                    take_profit_dist_pips = 0.0

                fmt_stop_loss = format_with_percent(fmt_pips(stop_loss_dist_pips) + "pts",
                                                    stop_loss, stop_loss_pct)
                fmt_take_profit = format_with_percent(fmt_pips(take_profit_dist_pips) + "pts",
                                                      take_profit, take_profit_pct)
            else:
                # price w/wo percentage
                fmt_stop_loss = format_with_percent(t['stop-loss-price'], stop_loss, stop_loss_pct)
                fmt_take_profit = format_with_percent(t['take-profit-price'], take_profit, take_profit_pct)

            #
            # colorize
            #

            # SL/TP if hit, color depends on profit or loss, none if close at market
            if t['stats']['exit-reason'] in ("stop-loss-market", "stop-loss-limit") and exit_color:
                fmt_stop_loss = Color.colorize(fmt_stop_loss, exit_color, style=style)
            elif t['stats']['exit-reason'] in ("take-profit-limit", "take-profit-market") and exit_color:
                fmt_take_profit = Color.colorize(fmt_take_profit, exit_color, style=style)

            # PNL (percentage and currency)
            if exit_color:
                fmt_pnl_pct = Color.colorize(fmt_pnl_pct, exit_color, style=style)
                fmt_rpnl = Color.colorize(fmt_rpnl, exit_color, style=style)

            row = [
                t['symbol'],
                t['id'],
                fmt_direction,
                fmt_pnl_pct,
                "%.2f%%" % t['stats']['fees-pct'],  # total fees in percent
                t['order-price'] if t['order-price'] != "0" else "-",
                fmt_stop_loss,
                fmt_take_profit,
                localize_datetime(t['entry-open-time']),
                localize_datetime(t['stats']['first-realized-entry-datetime']),
                t['avg-entry-price'],
                localize_datetime(t['stats']['last-realized-exit-datetime']),
                t['avg-exit-price'],
                t['label'],
                t['state'].capitalize(),
            ]

            if quantities:
                row.append(fmt_rpnl)
                row.append(t['order-qty'])
                row.append(t['filled-entry-qty'])
                row.append(t['filled-exit-qty'])

            if stats:
                if entry_price:
                    mfe_pct = direction * (best_price - entry_price) / entry_price - fees_pct
                    mae_pct = direction * (worst_price - entry_price) / entry_price - fees_pct
                else:
                    mfe_pct = 0
                    mae_pct = 0

                if exit_price:
                    etd = direction * (exit_price - best_price)
                    etd_pct = etd / exit_price - fees_pct
                else:
                    etd = 0
                    etd_pct = 0

                # display in pips or price, with or without percentage
                if pips:
                    # pips w/wo percentage
                    pip_means = t['stats'].get('one-pip-means', 1.0) or 1.0

                    if entry_price:
                        # gross but could compute fees in pts...
                        mfe_dist_pips = direction * (best_price - entry_price) / pip_means
                        mae_dist_pips = direction * (worst_price - entry_price) / pip_means
                    else:
                        mfe_dist_pips = 0.0
                        mae_dist_pips = 0.0

                    if exit_price:
                        etd_dist_pips = min(0.0, direction * (exit_price - best_price) / pip_means)
                    else:
                        etd_dist_pips = 0.0

                    fmt_mfe = format_with_percent(fmt_pips(mfe_dist_pips) + "pts", best_price, mfe_pct)
                    fmt_mae = format_with_percent(fmt_pips(mae_dist_pips) + "pts", worst_price, mae_pct)
                    fmt_etd = format_with_percent(fmt_pips(etd_dist_pips) + "pts", etd, etd_pct)
                else:
                    # price w/wo percentage

                    fmt_mfe = format_with_percent(t['stats']['best-price'], best_price, mfe_pct)
                    fmt_mae = format_with_percent(t['stats']['worst-price'], worst_price, mae_pct)
                    # don't have here the instrument price formatting
                    fmt_etd = format_with_percent("%g" % etd, etd, etd_pct)

                # look at cumulative P/L percent
                cum_pnl = cum_pnls[trade_key]

                # colorize cumulative P/L percentage
                if round(cum_pnl * 10) == 0.0:  # equity
                    fmt_cum_pnl = "%.2f%%" % cum_pnl
                elif cum_pnl < 0:  # loss
                    fmt_cum_pnl = Color.colorize("%.2f%%" % cum_pnl, Color.RED, style=style)
                elif cum_pnl > 0:  # profit
                    fmt_cum_pnl = Color.colorize("%.2f%%" % cum_pnl, Color.GREEN, style=style)
                else:
                    fmt_cum_pnl = "-"

                # efficiency
                en_eff_pct = (best_price - entry_price) / (best_price - worst_price)
                ex_eff_pct = (exit_price - worst_price) / (best_price - worst_price)
                to_eff_pct = (exit_price - entry_price) / (best_price - worst_price)

                row.append(fmt_cum_pnl)
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
            row.append('---')
            row.append('---')
            row.append('---')

        data.append(row[0:4] + row[4+col_ofs:])

    for currency, sub_total in sub_totals.items():
        if sub_total > 0:
            fmt_rpnl = Color.colorize("%g%s" % (sub_total, currency), Color.GREEN, style=style)
        elif sub_total < 0:
            fmt_rpnl = Color.colorize("%g%s" % (sub_total, currency), Color.RED, style=style)
        else:
            fmt_rpnl = "%g%s" % (sub_total, currency)

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
            row.append(fmt_rpnl)
            row.append('-')
            row.append('-')
            row.append('-')

        if stats:
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')

        data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size
