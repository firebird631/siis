# @date 2020-05-30
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Active alerts view.

import threading
import hashlib

from datetime import datetime

from common.utils import timeframe_to_str
from common.signal import Signal

from terminal.terminal import Terminal, Color
from terminal import charmap

from view.tableview import TableView

from strategy.helpers.activealerttable import actives_alerts_table

import logging
logger = logging.getLogger('siis.view.activealert')
error_logger = logging.getLogger('siis.error.view.activealert')


class ActiveAlertView(TableView):
    """
    Active alerts view.
    """

    def __init__(self, service, strategy_service):
        super().__init__("activealert", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._alerts_list = {}

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return len(self._strategy_service.get_appliances())

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_STRATEGY_ALERT:
                with self._mutex:
                    if signal.data.get('app-id'):
                        self._refresh = 0.0

    def refresh(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            appliance = appliances[self._item]
            num = 0

            with self._mutex:
                try:
                    columns, table, total_size = actives_alerts_table(appliance, *self.table_format(), datetime_format=self._datetime_format)

                    for row in table:
                        # colorize by market-id
                        symbol_color = int(hashlib.sha1(row[0].encode("utf-8")).hexdigest(), 16) % Color.count()-1
                        row[0] = Color.colorize(row[0], Color.color(symbol_color), Terminal.inst().style())

                    self.table(columns, table, total_size)
                    num = total_size[1]
                except Exception as e:
                    import traceback
                    error_logger.error(str(traceback.format_exc()))
                    error_logger.error(str(e))

            self.set_title("Actives alerts list (%i) for strategy %s - %s" % (num, appliance.name, appliance.identifier))
        else:
            self.set_title("Actrives alerts list - No configured strategy")
