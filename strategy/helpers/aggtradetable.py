# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from terminal.terminal import Color

from strategy.helpers.aggtradedataset import get_agg_trades

import logging
logger = logging.getLogger('siis.strategy.helpers.aggtradetable')
error_logger = logging.getLogger('siis.error.strategy.helpers.aggtradetable')


def agg_trades_stats_table(strategy, style='', offset=None, limit=None, col_ofs=None, summ=True,
                           group=None, ordering=None):
    """
    Returns a table of any aggregated active and closes trades.
    """
    columns = ('Symbol', 'P/L(%)', 'Total(%)', 'RPNL', 'Open', 'Best(%)', 'Worst(%)', 'Success', 'Failed', 'ROE',
               'Closed', 'High(%)', 'Low(%)')
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

        if group:
            agg_trades.sort(key=lambda x: x['perf'], reverse=True if ordering else False)
        else:
            agg_trades.sort(key=lambda x: x['sym'], reverse=True if ordering else False)

        pl_sum = 0.0
        perf_sum = 0.0
        best_best = 0.0
        worst_worst = 0.0
        success_sum = 0
        failed_sum = 0
        roe_sum = 0
        num_open_trades_sum = 0
        num_actives_trades_sum = 0

        # total sum before offset:limit
        if summ:
            for t in agg_trades:
                pl_sum += t['pl']
                perf_sum += t['perf']
                best_best = max(best_best, t['best'])
                worst_worst = min(worst_worst, t['worst'])
                success_sum += t['success']
                failed_sum += t['failed']
                roe_sum += t['roe']
                num_open_trades_sum += t['num-open-trades']
                num_actives_trades_sum += t['num-actives-trades']

        agg_trades = agg_trades[offset:limit]

        for t in agg_trades:
            cr = Color.colorize_updn("%.2f" % (t['pl']*100.0), 0.0, t['pl'], style=style)
            cp = Color.colorize_updn("%.2f" % (t['perf']*100.0), 0.0, t['perf'], style=style)
            rpnl = Color.colorize_updn("%g%s" % (t['rpnl'], t['rpnl-currency']), 0.0, t['rpnl'], style=style)

            row = (
                t['sym'],
                cr,
                cp,
                rpnl,
                "%s/%s" % (t['num-actives-trades'], t['num-open-trades']),
                "%.2f" % (t['best']*100.0),
                "%.2f" % (t['worst']*100.0),
                t['success'],
                t['failed'],
                t['roe'],
                t['num-closed-trades'],
                "%.2f" % (t['high']*100.0),
                "%.2f" % (t['low']*100.0),
            )

            data.append(row[0:3] + row[3 + col_ofs:])

        #
        # sum
        #

        if summ:
            row = (
                '------',
                '------',
                '--------',
                '----',
                '----',
                '-------',
                '--------',
                '-------',
                '------',
                '---',
                '------',
                '-------',
                '------',
            )

            data.append(row[0:3] + row[3+col_ofs:])

            cpl_sum = Color.colorize_updn("%.2f" % (pl_sum*100.0), 0.0, pl_sum, style=style)
            cperf_sum = Color.colorize_updn("%.2f" % (perf_sum*100.0), 0.0, perf_sum, style=style)

            row = (
                'TOTAL',
                cpl_sum,
                cperf_sum,
                '-',
                "%s/%s" % (num_actives_trades_sum, num_open_trades_sum),
                "%.2f" % (best_best*100.0),
                "%.2f" % (worst_worst*100.0),
                success_sum,
                failed_sum,
                roe_sum,
                success_sum + failed_sum + roe_sum,
                '-',
                '-',
                '-',
            )

            data.append(row[0:3] + row[3+col_ofs:])

    return columns[0:3] + columns[3+col_ofs:], data, total_size
