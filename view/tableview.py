# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Table view base class.

from tabulate import tabulate

from terminal.terminal import Terminal, Color
from view.view import View


class TableView(View):
    """
    Table view base class.
    """

    def __init__(self, _id, service):
        super().__init__(_id, service)

        self._row = [0, 0]  # offset, limit
        self._col = 0       # offset

        self._table = [0, 0]  # for table view, number of columns, number of rows

    def scroll_row(self, n):
        """
        Scroll n row (positive or negative) from current first row.
        The max number of displayed row depend on the height of the view.
        """
        self._row[0] += n

        if self._row[0] < 0:
            self._row[0] = 0

        if self._row[0] >= self._table[1]:
            self._row[0] = self._table[1] - 1

        self._refresh = 0

    def scroll_col(self, n):
        """
        Scroll n columns (positive or negative) from current first columns.
        """
        self._col += n

        if self._col < 0:
            self._col = 0

        if self._col > self._table[0]:
            self._col = self._table[0]

        self._refresh = 0

    def table_format(self):
        return Terminal.inst().style(), self._row[0], self.height()-4, self._col

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if Terminal.inst().mode == Terminal.MODE_DEFAULT:
            if key == 'KEY_PPAGE':
                self.scroll_row(-(self.height()-4))   
            elif key == 'KEY_NPAGE':
                self.scroll_row(self.height()-4)
            elif key == 'KEY_SR' or key == 'j':
                self.scroll_row(-1)
            elif key == 'KEY_SF' or key == 'k':
                self.scroll_row(1)
            elif key == 'KEY_SLEFT' or key == 'h':
                self.scroll_col(-1)
            elif key == 'KEY_SRIGHT' or key == 'l':
                self.scroll_col(1)
            elif key == 'KEY_SPREVIOUS':
                self.prev_item()
            elif key == 'KEY_SNEXT':
                self.next_item()

    def table(self, columns, table, total_size=None):
        """
        Draw a table in this view.
        """
        if not columns or table is None:
            return

        self._table = total_size if total_size else (len(columns), len(table))

        table_data = tabulate(table, headers=columns, tablefmt='psql', showindex=False,
                              floatfmt=".2f", disable_numparse=True)

        # replace color space code before drawing
        for k, v in Color.UTERM_COLORS_MAP.items():
            table_data = table_data.replace(k, v)

        # draw the table
        vt = Terminal.inst().view(self._id)
        if vt:
            vt.draw('', table_data, True)

    def display_mode_str(self):
        """
        Helper that return a str according to group and ordering state for the view.
        From : G+, G-, +, -
        """
        return "%s%s" % ("G" if self._group else "", "-" if self._ordering else '+')
