# @date 2020-05-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from strategy.helpers.activealertdataset import get_all_active_alerts

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def actives_alerts_table(strategy, style='', offset=None, limit=None, col_ofs=None,
                         group=None, ordering=None, datetime_format='%y-%m-%d %H:%M:%S'):
    """
    Returns a table of any active alerts.
    """
    COLUMNS = ('Symbol', '#', 'Label', 'TF', 'Created', 'Expiry', 'Countdown', 'Condition', 'Cancellation', 'Message')

    columns = tuple(COLUMNS)
    total_size = (len(columns), 0)
    data = []

    with strategy._mutex:
        alerts = get_all_active_alerts(strategy)
        total_size = (len(columns), len(alerts))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(alerts)

        limit = offset + limit

        if group:
            # in alpha order then by created
            alerts.sort(key=lambda x: x['sym']+str(x['ts']), reverse=True if ordering else False)
        else:
            # by created timestamp descending
            alerts.sort(key=lambda x: x['ts'], reverse=True if ordering else False)

        alerts = alerts[offset:limit]

        for t in alerts:
            row = [
                t['sym'],
                t['id'],
                t['name'], 
                t['tf'],
                datetime.fromtimestamp(t['ts']).strftime(datetime_format) if t['ts'] > 0 else "?",
                datetime.fromtimestamp(t['expiry']).strftime(datetime_format) if t['expiry'] > 0 else "never",
                t['ctd'],
                t['cond'],
                t['cancel'],
                t['msg'],
            ]

            data.append(row[0:3] + row[3+col_ofs:])

    return columns[0:3] + columns[3+col_ofs:], data, total_size
