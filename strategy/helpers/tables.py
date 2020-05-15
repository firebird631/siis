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
from strategy.helpers.aggtradedataset import get_agg_trades
from strategy.helpers.closedtradedataset import get_closed_trades


import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def agg_trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None, summ=True):
    """
    Returns a table of any aggreged active and closes trades.
    """
    columns = ('Market', 'P/L(%)', 'Total(%)', 'Best(%)', 'Worst(%)', 'Success', 'Failed', 'ROE')
    total_size = (len(columns), 0)
    data = []

    with strategy._mutex:
        agg_trades = get_agg_trades(strategy)
        total_size = (len(columns), len(agg_trades) + (1 if summ else 0))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(agg_trades) + (1 if summ else 0)

        limit = offset + limit

        agg_trades.sort(key=lambda x: x['mid'])

        pl_sum = 0.0
        perf_sum = 0.0
        best_sum = 0.0
        worst_sum = 0.0
        success_sum = 0
        failed_sum = 0
        roe_sum = 0

        # total summ before offset:limit
        if summ:
            for t in agg_trades:
                pl_sum += t['pl']
                perf_sum += t['perf']
                best_sum = max(best_sum, t['best'])
                worst_sum = min(worst_sum, t['worst'])
                success_sum += t['success']
                failed_sum += t['failed']
                roe_sum += t['roe']

        agg_trades = agg_trades[offset:limit]

        for t in agg_trades:
            cr = Color.colorize_updn("%.2f" % (t['pl']*100.0), 0.0, t['pl'], style=style)
            cp = Color.colorize_updn("%.2f" % (t['perf']*100.0), 0.0, t['perf'], style=style)

            row = (
                t['mid'],
                cr,
                cp,
                "%.2f" % (t['best']*100.0),
                "%.2f" % (t['worst']*100.0),
                t['success'],
                t['failed'],
                t['roe']
            )

            data.append(row[col_ofs:])

        #
        # sum
        #

        if summ:
            cpl_sum = Color.colorize_updn("%.2f" % (pl_sum*100.0), 0.0, pl_sum, style=style)
            cperf_sum = Color.colorize_updn("%.2f" % (perf_sum*100.0), 0.0, perf_sum, style=style)

            row = (
                'Total',
                cpl_sum,
                cperf_sum,
                "%.2f" % (best_sum*100.0),
                "%.2f" % (worst_sum*100.0),
                success_sum,
                failed_sum,
                roe_sum)

            data.append(row[col_ofs:])

    return columns[col_ofs:], data, total_size


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
                bpct = (best - aep) / aep
                wpct = (worst - aep) / aep
            elif t['d'] == 'short' and aep > 0 and best > 0 and worst > 0:
                bpct = (aep - best) / aep
                wpct = (aep - worst) / aep
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
