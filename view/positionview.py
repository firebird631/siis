# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Position view.

from terminal.terminal import Terminal
from view.tableview import TableView

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
                columns, table, total_size = trader.positions_stats_table(*self.table_format(),
                        quantities=True, datetime_format=self._datetime_format)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            self.set_title("Position list (%i) trader %s on account %s" % (num, trader.name, trader.account.name))
        else:
            self.set_title("Position list - No configured trader")
