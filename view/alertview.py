# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Alerts view.

import copy
import threading
import hashlib

from datetime import datetime
from typing import List

from common.signal import Signal

from terminal.terminal import Color
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

    MAX_ALERTS = 500
    COLUMNS = ('Symbol', '#', 'Label', charmap.ARROWUPDN, 'TF', 'Last Price', 'Reason', 'User', 'Date')

    def __init__(self, service, strategy_service):
        super().__init__("alert", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._alerts_list = []

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return 1

    def on_char(self, char):
        if char == 'C':
            # empty history and refresh
            with self._mutex:
                if self._alerts_list:
                    self._alerts_list.clear()

            self._refresh = 0.0

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_STRATEGY_ALERT:
                with self._mutex:
                    self._alerts_list.append(signal.data)

                    if len(self._alerts_list) > AlertView.MAX_ALERTS:
                        self._alerts_list.pop(0)

                    self._refresh = 0.0

    def alerts_table(self, strategy, style='', offset=None, limit=None, col_ofs=None):
        """
        Generate the table of alert according to current alerts list.
        @note This method is not thread safe.
        @param strategy:
        @param style:
        @param offset:
        @param limit:
        @param col_ofs:
        @return:
        """
        data = []

        alerts = self._alerts_list
        total_size = (len(AlertView.COLUMNS), len(alerts))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(alerts)

        limit = offset + limit

        # sort by timestamp desc
        alerts.sort(key=lambda x: x['timestamp'], reverse=self._ordering)

        alerts = alerts[offset:limit]

        for alert in alerts:
            ldatetime = datetime.fromtimestamp(alert['timestamp']).strftime(self._datetime_format)
            trigger = Color.colorize_cond(charmap.ARROWUP if alert['trigger'] > 0 else charmap.ARROWDN,
                                          alert['trigger'] > 0, style, true=Color.GREEN, false=Color.RED)

            symbol_color = int(hashlib.sha1(alert['symbol'].encode("utf-8")).hexdigest(), 16) % Color.count()
            id_color = alert['id'] % Color.count()

            lid = Color.colorize(str(alert['id']), Color.color(id_color), style)
            lsymbol = Color.colorize(alert['symbol'], Color.color(symbol_color), style)

            row = (
                lsymbol,
                lid,
                alert.get('name', ""),
                trigger,
                alert.get('timeframe', ""),
                alert.get('last-price', ""),
                alert.get('reason', ""),
                alert.get('message', ""),
                ldatetime
            )

            data.append(row[0:2] + row[2+col_ofs:])

        return AlertView.COLUMNS[0:2] + AlertView.COLUMNS[2+col_ofs:], data, total_size

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            with self._mutex:
                try:
                    columns, table, total_size = self.alerts_table(strategy, *self.table_format())
                    self.table(columns, table, total_size)
                    num = total_size[1]
                except Exception as e:
                    import traceback
                    error_logger.error(str(traceback.format_exc()))
                    error_logger.error(str(e))

            self.set_title("Alert list (%i)%s for strategy %s - %s" % (
                num, self.display_mode_str(), strategy.name, strategy.identifier))
        else:
            self.set_title("Alert list - No configured strategy")

    def dumps_alerts(self) -> List[dict]:
        alerts = []

        with self._mutex:
            for alert in self._alerts_list:
                alerts.append(copy.copy(alert))

        return alerts
