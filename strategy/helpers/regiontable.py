# @date 2021-11-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from strategy.helpers.regiondataset import get_all_regions
from terminal.terminal import Color

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def region_table(strategy, style='', offset=None, limit=None, col_ofs=None,
                 group=None, ordering=None, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any active alerts.
    """
    COLUMNS = ('Symbol', '#', 'Name', 'Dir', 'Stage', 'TF', 'Created', 'Expiry', 'Cancellation', 'Inside', 'Condition')

    columns = tuple(COLUMNS)
    total_size = (len(columns), 0)
    data = []

    with strategy._mutex:
        regions = get_all_regions(strategy)
        total_size = (len(columns), len(regions))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(regions)

        limit = offset + limit

        if group:
            # in alpha order then by created
            regions.sort(key=lambda x: x['sym']+str(x['ts']), reverse=True if ordering else False)
        else:
            # by created timestamp descending
            regions.sort(key=lambda x: x['ts'], reverse=True if ordering else False)

        regions = regions[offset:limit]

        for t in regions:
            if t['inside']:
                inside = Color.colorize('IN', Color.GREEN, style=style)
            else:
                inside = Color.colorize('OUT', Color.RED, style=style)

            row = [
                t['sym'],
                t['id'],
                t['name'],
                t['dir'],
                t['stage'],
                t['tf'],
                datetime.fromtimestamp(t['ts']).strftime(datetime_format) if t['ts'] > 0 else "?",
                datetime.fromtimestamp(t['expiry']).strftime(datetime_format) if t['expiry'] > 0 else "never",
                t['cancel'],
                inside,
                t['cond'],
            ]

            data.append(row[0:3] + row[3+col_ofs:])

    return columns[0:3] + columns[3+col_ofs:], data, total_size
