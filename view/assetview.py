# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Asset view.

from terminal.terminal import Terminal
from view.tableview import TableView
from trader.helpers.assettable import assets_table

import logging
logger = logging.getLogger('siis.view.asset')
error_logger = logging.getLogger('siis.error.view.asset')


class AssetView(TableView):
    """
    Asset view.
    """

    def __init__(self, service, trader_service):
        super().__init__("asset", service)

        self._trader_service = trader_service

    def count_items(self):
        if not self._trader_service:
            return 0

        return 1

    def refresh(self):
        if not self._trader_service:
            return

        trader = self._trader_service.trader()
        if trader:
            num = 0

            try:
                columns, table, total_size = assets_table(
                    trader, *self.table_format(),
                    filter_low=self._opt2, compute_qty=self._opt1, percent=self._percent,
                    group=self._group, ordering=self._ordering)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            # display options
            display_opts = []
            if self._group:
                display_opts.append("Group")
            if self._ordering:
                display_opts.append("Desc.")
            else:
                display_opts.append("Asc.")
            if self._percent:
                display_opts.append("%")
            if self._opt1:
                display_opts.append("Local size")

            self.set_title("[Assets %i] %s::%s <%s>" % (
                num, trader.name, trader.account.name, " - ".join(display_opts)))
        else:
            self.set_title("[Assets 0] No configured trader")
