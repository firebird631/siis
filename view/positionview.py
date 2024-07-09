# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Position view.

from view.tableview import TableView
from trader.helpers.positionstatstable import positions_stats_table

import logging
error_logger = logging.getLogger('siis.view.position')


class PositionView(TableView):
    """
    Position view.
    """

    def __init__(self, service, trader_service):
        super().__init__("position", service)

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
                columns, table, total_size = positions_stats_table(
                    trader, *self.table_format(),
                    quantities=True, percents=self._percent,
                    datetime_format=self._datetime_format)

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

            self.set_title("[Positions %i] %s::%s <%s>" % (
                num, trader.name, trader.account.name, " - ".join(display_opts)))
        else:
            self.set_title("[Positions 0] No configured trader <>")
