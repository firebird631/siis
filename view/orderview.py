# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Order view.

from view.tableview import TableView
from trader.helpers.activeordertable import active_orders_table

import logging
error_logger = logging.getLogger('siis.view.order')


class OrderView(TableView):
    """
    Order view.
    """

    def __init__(self, service, trader_service):
        super().__init__("order", service)

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
                columns, table, total_size = active_orders_table(
                    trader, *self.table_format(), quantities=True, datetime_format=self._datetime_format,
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

            self.set_title("[Orders %i] %s::%s <%s>" % (
                num, trader.name, trader.account.name, " - ".join(display_opts)))
        else:
            self.set_title("[Orders 0] No configured trader")
