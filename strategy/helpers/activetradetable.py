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
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'P/L', 'OP', 'SL', 'TP', 'Signal date',
               'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'Status']

    if quantities:
        columns += ['UPNL', 'Qty', 'Entry Q', 'Exit Q', 'Quote']

    if stats:
        columns += ['MFE', 'MAE', 'ETD']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []
    num_actives_trades = 0
    sub_totals = {}

    with strategy.mutex:
        trades = get_all_active_trades(strategy)
        total_size = (len(columns), len(trades))

        if stats:
            for t in trades:
                entry_price = float(t['aep'])

                # count actives trades for all trades with filled (partial or complete) quantity
                if entry_price > 0:
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

            entry_price = float(t['aep'])
            best_price = float(t['b'])
            worst_price = float(t['w'])
            order_price = float(t['l'])
            stop_loss = float(t['sl'])
            take_profit = float(t['tp'])
            last_open_exec_price = float(t['loep'])
            last_close_exec_price = float(t['lcep'])

            # compute P/L in currency, pips and percentage
            fmt_upnl = "%s%s" % (t['upnl'], t['pnlcur']) if entry_price else '-'

            if pips:
                fmt_pnl = "%spts" % t['entry-dist-pips']
            else:
                fmt_pnl = "%.2f%%" % (t['pl'] * 100.0)

            if t['pl'] < 0:  # loss
                if (t['d'] == 'long' and best_price > entry_price) or (t['d'] == 'short' and best_price < entry_price):
                    # but was profitable during a time
                    fmt_pnl = Color.colorize(fmt_pnl, Color.ORANGE, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.ORANGE, style=style)
                else:
                    fmt_pnl = Color.colorize(fmt_pnl, Color.RED, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.RED, style=style)
            elif t['pl'] > 0:  # profit
                if (t['d'] == 'long' and best_price > entry_price) or (t['d'] == 'short' and best_price < entry_price):
                    # but was in lost during a time
                    fmt_pnl = Color.colorize(fmt_pnl, Color.BLUE, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.BLUE, style=style)
                else:
                    fmt_pnl = Color.colorize(fmt_pnl, Color.GREEN, style=style)
                    fmt_upnl = Color.colorize(fmt_upnl, Color.GREEN, style=style)
            else:  # equity
                fmt_pnl = "0.00%" if entry_price else "-"

            # compute stats with percentage versions
            if t['d'] == 'long' and entry_price > 0 and best_price > 0 and worst_price > 0:
                mfe_pct = (best_price - entry_price) / entry_price - t['fees']
                mae_pct = (worst_price - entry_price) / entry_price - t['fees']

                if last_close_exec_price:
                    etd = last_close_exec_price - best_price
                    etd_pct = etd / last_close_exec_price - t['fees']
                else:
                    etd = 0
                    etd_pct = 0
            elif t['d'] == 'short' and entry_price > 0 and best_price > 0 and worst_price > 0:
                mfe_pct = (entry_price - best_price) / entry_price - t['fees']
                mae_pct = (entry_price - worst_price) / entry_price - t['fees']

                if last_close_exec_price:
                    etd = best_price - last_close_exec_price  # in price but gross
                    etd_pct = etd / last_close_exec_price - t['fees']  # percentage net
                else:
                    etd = 0
                    etd_pct = 0
            else:
                mfe_pct = 0
                mae_pct = 0
                etd_pct = 0

            # compute exit targets in percentage
            if t['d'] == 'long' and (entry_price or order_price):
                stop_loss_pct = (stop_loss - (entry_price or order_price)) / (entry_price or order_price)
                take_profit_pct = (take_profit - (entry_price or order_price)) / (entry_price or order_price)
            elif t['d'] == 'short' and (entry_price or order_price):
                stop_loss_pct = ((entry_price or order_price) - stop_loss) / (entry_price or order_price)
                take_profit_pct = ((entry_price or order_price) - take_profit) / (entry_price or order_price)
            else:
                stop_loss_pct = 0
                take_profit_pct = 0

            # compute distance from entry and last exec open price in percentage
            if order_price and (t['s'] in ('new', 'opened', 'filling')):
                if t['d'] == 'long':
                    order_price_pct = (order_price - last_open_exec_price) / order_price
                elif t['d'] == 'short':
                    order_price_pct = (order_price - last_open_exec_price) / order_price
                else:
                    order_price_pct = 0
            else:
                order_price_pct = 0

            def format_with_percent(formatted_value, condition, rate):
                return (("%s %.2f%%" % (formatted_value,
                                        rate * 100)) if percents else formatted_value) if condition else '-'

            # display in pips or price, with or without percentage
            if pips:
                fmt_order_price = (("%spts %.2f%%" % (t['order-dist-pips'], order_price_pct * 100)) if
                                   percents and order_price_pct
                                   else t['order-dist-pips'] + "pts") if order_price else '-'

                fmt_stop_loss = format_with_percent(t['stop-loss-dist-pips'] + "pts", stop_loss, stop_loss_pct)
                fmt_take_profit = format_with_percent(t['take-profit-dist-pips'] + "pts", take_profit, take_profit_pct)
            else:
                fmt_order_price = (("%s %.2f%%" % (t['l'], order_price_pct * 100)) if
                                   percents and order_price_pct else t['l']) if order_price else '-'

                fmt_stop_loss = format_with_percent(t['sl'], stop_loss, stop_loss_pct)
                fmt_take_profit = format_with_percent(t['tp'], take_profit, take_profit_pct)

            row = [
                t['sym'],
                t['id'],
                fmt_direction,
                fmt_pnl if last_open_exec_price else charmap.HOURGLASS,
                fmt_order_price,
                fmt_stop_loss,
                fmt_take_profit,
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
                # MFE, MAE, ETD if active
                if pips:
                    fmt_mfe = format_with_percent(t['mfe-dist-pips'] + "pts", best_price, mfe_pct)
                    fmt_mae = format_with_percent(t['mae-dist-pips'] + "pts", worst_price, mae_pct)
                    fmt_etd = format_with_percent(t['etd-dist-pips'] + "pts", etd, etd_pct)
                else:
                    fmt_mfe = format_with_percent(t['b'], best_price, mfe_pct)
                    fmt_mae = format_with_percent(t['w'], worst_price, mae_pct)
                    fmt_etd = format_with_percent(t['etd'], etd, etd_pct)

                row.append(fmt_mfe)
                row.append(fmt_mae)
                row.append(fmt_etd)

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
            currency,
            '-',
        ]

        if quantities:
            row.append(fmt_upnl)
            row.append('-')
            row.append('-')
            row.append('-')
            row.append('-')

        if stats:
            row.append('---')
            row.append('---')
            row.append('---')

        data.append(row[0:4] + row[4+col_ofs:])

    return columns[0:4] + columns[4+col_ofs:], data, total_size, num_actives_trades
