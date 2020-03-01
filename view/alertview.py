# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Alerts view.

import threading
import hashlib

from datetime import datetime

from common.utils import timeframe_to_str
from common.signal import Signal

from terminal.terminal import Terminal, Color
from terminal import charmap

from view.tableview import TableView

import logging
logger = logging.getLogger('siis.view.alert')
error_logger = logging.getLogger('siis.error.view.alert')


class AlertView(TableView):
    """
    Alerts view.
    """

    REFRESH_RATE = 60  # only on alert or 1 minute refresh

    MAX_ALERTS = 200
    COLUMNS = ('#', 'Market', 'Label', charmap.ARROWUPDN, 'TF', 'Last Price', 'Reason', 'User', 'Date')

    def __init__(self, service, strategy_service):
        super().__init__("alert", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._alerts_list = {}

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return (self._strategy_service.get_traders())

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_STRATEGY_ALERT:
                with self._mutex:
                    if signal.data.get('app-id'):
                        if signal.data['app-id'] not in self._alerts_list:
                            self._alerts_list[signal.data['app-id']] = []

                        alerts_list = self._alerts_list[signal.data['app-id']]
                        alerts_list.append(signal.data)

                        if len(alerts_list) > AlertView.MAX_ALERTS:
                            alerts_list.pop(0)

                        self._refresh = 0.0

    def alerts_table(self, appliance, style='', offset=None, limit=None, col_ofs=None):
        data = []

        alerts = self._alerts_list.get(appliance.identifier, [])
        total_size = (len(AlertView.COLUMNS), len(alerts))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(alerts)

        limit = offset + limit

        # sort by timestamp desc
        alerts.sort(key=lambda x: -x['timestamp'])

        alerts = alerts[offset:limit]

        for alert in alerts:
            ldatetime = datetime.fromtimestamp(alert['timestamp']).strftime(self._datetime_format)
            trigger = Color.colorize_cond(charmap.ARROWUP if alert['trigger'] == "up" else charmap.ARROWDN,
                    alert['trigger'] == "up", style, true=Color.GREEN, false=Color.RED)

            symbol_color = int(hashlib.sha1(alert['symbol'].encode("utf-8")).hexdigest(), 16) % Color.count()-1
            id_color = alert['id'] % Color.count()-1

            lid = Color.colorize(str(alert['id']), Color.color(id_color), style)
            lsymbol = Color.colorize(alert['symbol'], Color.color(symbol_color), style)

            row = (
                lid,
                lsymbol,
                alert.get('label', ""),
                trigger,
                alert.get('timeframe', ""),
                alert.get('last-price', ""),
                alert.get('reason', ""),
                alert.get('message', ""),
                ldatetime
            )

            data.append(row[col_ofs:])

        return AlertView.COLUMNS[col_ofs:], data, total_size

    def refresh(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            appliance = appliances[self._item]
            num = 0

            with self._mutex:
                try:
                    columns, table, total_size = self.alerts_table(appliance, *self.table_format())
                    self.table(columns, table, total_size)
                    num = total_size[1]
                except Exception as e:
                    import traceback
                    error_logger.error(str(traceback.format_exc()))
                    error_logger.error(str(e))

            self.set_title("Alert list (%i) for strategy %s - %s" % (num, appliance.name, appliance.identifier))
        else:
            self.set_title("Alert list - No configured strategy")
