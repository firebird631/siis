# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader display table formatter helpers for views or notifiers

import logging
import traceback

from datetime import datetime

from terminal import charmap
from terminal.terminal import Color

from .activeorderdataset import get_active_orders

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


def active_orders_table(trader, style='', offset=None, limit=None, col_ofs=None, quantities=False,
                        percents=False, datetime_format='%y-%m-%d %H:%M:%S', group=None, ordering=None):
    """
    Returns a table of any active orders.
    """
    columns = ['Symbol', '#', 'ref #', charmap.ARROWUPDN, 'Type', 'x', 'Limit', 'Stop', 'SL', 'TP',
               'TR', 'Created date', 'Transac date', 'Reduce', 'Post', 'Hedge', 'Close', 'Margin',
               'TIF', 'Price', 'Key']

    if quantities:
        columns += ['Qty']
        columns += ['Exec']

    columns = tuple(columns)
    total_size = (len(columns), 0)
    data = []

    with trader.mutex:
        try:
            orders = get_active_orders(trader)
            total_size = (len(columns), len(orders))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(orders)

            limit = offset + limit

            if group:
                orders.sort(key=lambda x: x['sym'] + str(x['ct']), reverse=True if ordering else False)
            else:
                orders.sort(key=lambda x: x['ct'], reverse=True if ordering else False)

            orders = orders[offset:limit]

            for t in orders:
                direction = Color.colorize_cond(
                    charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN, t['d'] == "long",
                    style=style, true=Color.GREEN, false=Color.RED)

                op = float(t['op']) if t['op'] else 0.0
                sl = float(t['sl']) if t['sl'] else 0.0
                tp = float(t['tp']) if t['tp'] else 0.0

                if t['d'] == 'long' and op:
                    slpct = (sl - op) / op if sl else 0.0
                    tppct = (tp - op) / op if tp else 0.0
                elif t['d'] == 'short' and op:
                    slpct = (op - sl) / op if sl else 0.0
                    tppct = (op - tp) / op if tp else 0.0
                else:
                    slpct = 0
                    tppct = 0

                row = [
                    t['sym'],
                    t['id'],
                    t['refid'],
                    direction,
                    t['ot'],
                    "%.2f" % t['l'] if t['l'] else '-',
                    t['op'],
                    t['sp'],
                    "%s (%.2f)" % (t['sl'], slpct * 100) if percents else t['sl'],
                    "%s (%.2f)" % (t['tp'], tppct * 100) if percents else t['tp'],
                    t['tr'],
                    datetime.fromtimestamp(t['ct']).strftime(datetime_format) if t['ct'] > 0 else "",
                    datetime.fromtimestamp(t['tt']).strftime(datetime_format) if t['tt'] > 0 else "",
                    "Yes" if t['ro'] else "No",
                    "Yes" if t['po'] else "No",
                    "Yes" if t['he'] else "No",
                    "Yes" if t['co'] else "No",
                    "Yes" if t['mt'] else "No",
                    t['tif'],
                    t['pt'],
                    t['key']
                ]

                if quantities:
                    row.append(t['q'])
                    row.append(t['xq'])

                data.append(row[0:2] + row[2 + col_ofs:])

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

    return columns[0:2] + columns[2+col_ofs:], data, total_size
