# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging
import traceback

from datetime import datetime

from terminal import charmap
from terminal.terminal import Color

from .activepositiondataset import get_active_positions

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


def positions_stats_table(trader, style='', offset=None, limit=None, col_ofs=None, quantities=False,
                          percents=False, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any active positions.
    """
    columns = ['Symbol', '#', charmap.ARROWUPDN, 'x', 'P/L(%)', 'SL', 'TP', 'TR', 'Entry date', 'Avg EP',
               'Exit date', 'Avg XP', 'UPNL', 'Cost', 'Margin', 'Key']

    if quantities:
        columns += ['Qty']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []

    with trader.mutex:
        try:
            positions = get_active_positions(trader)
            total_size = (len(columns), len(positions))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(positions)

            limit = offset + limit

            positions.sort(key=lambda x: x['et'])
            positions = positions[offset:limit]

            for t in positions:
                direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN,
                                                t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

                aep = float(t['aep']) if t['aep'] else 0.0
                sl = float(t['sl']) if t['sl'] else 0.0
                tp = float(t['tp']) if t['tp'] else 0.0

                if t['pl'] < 0:  # loss
                    cr = Color.colorize("%.2f" % (t['pl'] * 100.0), Color.RED, style=style)
                    pnl = Color.colorize("%s%s" % (t['pnl'], t['pnlcur']), Color.RED, style=style)
                elif t['pl'] > 0:  # profit
                    cr = Color.colorize("%.2f" % (t['pl'] * 100.0), Color.GREEN, style=style)
                    pnl = Color.colorize("%s%s" % (t['pnl'], t['pnlcur']), Color.GREEN, style=style)
                else:  # equity
                    cr = "0.0"
                    pnl = "%s%s" % (t['pnl'], t['pnlcur'])

                if t['d'] == 'long' and aep:
                    slpct = (sl - aep) / aep
                    tppct = (tp - aep) / aep
                elif t['d'] == 'short' and aep:
                    slpct = (aep - sl) / aep
                    tppct = (aep - tp) / aep
                else:
                    slpct = 0
                    tppct = 0

                row = [
                    t['sym'],
                    t['id'],
                    direction,
                    "%.2f" % t['l'] if t['l'] else '-',
                    cr,
                    "%s (%.2f)" % (t['sl'], slpct * 100) if percents else t['sl'],
                    "%s (%.2f)" % (t['tp'], tppct * 100) if percents else t['tp'],
                    t['tr'],
                    datetime.fromtimestamp(t['et']).strftime(datetime_format) if t['et'] > 0 else "",
                    t['aep'],
                    datetime.fromtimestamp(t['xt']).strftime(datetime_format) if t['xt'] > 0 else "",
                    t['axp'],
                    pnl,
                    t['cost'],
                    t['margin'],
                    t['key']
                ]

                # @todo xx / market.base_exchange_rate and pnl_currency

                if quantities:
                    row.append(t['q'])

                data.append(row[0:4] + row[4 + col_ofs:])

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

    return columns[0:4] + columns[4+col_ofs:], data, total_size
