# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Asset view.

from view.tableview import TableView
from trader.helpers.assettable import assets_table

import logging
error_logger = logging.getLogger('siis.view.asset')


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
                    trader, *self.table_format(), group=self._group, ordering=self._ordering)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            self.set_title("Asset list (%i)%s trader %s on account %s" % (
                num, self.display_mode_str(), trader.name, trader.account.name))
        else:
            self.set_title("Asset list - No configured trader")
