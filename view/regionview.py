# @date 2021-11-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Active alerts view.

import threading
import hashlib

from terminal.terminal import Terminal, Color

from view.tableview import TableView

from strategy.helpers.regiontable import region_table

import logging
logger = logging.getLogger('siis.view.region')
error_logger = logging.getLogger('siis.error.view.region')


class RegionView(TableView):
    """
    Region view.
    """

    def __init__(self, service, strategy_service):
        super().__init__("region", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service

    def count_items(self):
        if not self._strategy_service:
            return 0

        return 1

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            with self._mutex:
                try:
                    columns, table, total_size = region_table(
                        strategy, *self.table_format(), group=self._group, ordering=self._ordering,
                        datetime_format=self._datetime_format)

                    for row in table:
                        # colorize by symbol
                        symbol_color = int(hashlib.sha1(row[0].encode("utf-8")).hexdigest(), 16) % Color.count()
                        row[0] = Color.colorize(row[0], Color.color(symbol_color), Terminal.inst().style())

                    self.table(columns, table, total_size)
                    num = total_size[1]
                except Exception as e:
                    import traceback
                    error_logger.error(str(traceback.format_exc()))
                    error_logger.error(str(e))

            # display options
            display_opts = []
            if self._group:
                display_opts.append("Group")
            if self._ordering:
                display_opts.append("Desc.")
            else:
                display_opts.append("Asc.")

            self.set_title("[Regions %i] %s::%s <%s>" % (
                num, strategy.name, strategy.identifier, " - ".join(display_opts)))
        else:
            self.set_title("[Regions 0] No configured strategy <>")
