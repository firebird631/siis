# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# TAble view base class.

from terminal.terminal import Terminal
from view.view import View


class TableView(View):
    """
    Table view base class.
    """

    def __init__(self, _id):
        super().__init__(_id)

        self._row = [0, 0]  # offset, limit
        self._col = 0       # offset

        self._table = [0, 0]  # for table view, number of columns, number of rows

    def scroll_row(self, n):
        """
        Scroll n row (positive or negative) from current first row.
        The max number of displayed row depend of the height of the view.
        """
        self._row[0] += n

        if self._row[0] < 0:
            self._row[0] = 0

        if self._row[0] >= self._table[1]:
            self._row[0] = self._table[1] - 1

        self._refresh = True

    def scroll_col(self, n):
        """
        Scroll n columnes (positive or negative) from current first columns.
        """
        self._col += n

        if self._col < 0:
            self._col = 0

        if self._col > self._table[0]:
            self._col = self._table[0]

        self._refresh = True

    def table_format(self):
        return Terminal.inst().style(), self._row[0], self.height()-4, self._col

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if key == 'KEY_PPAGE':
            self.scroll_row(-(self.height()-4))   
        elif key == 'KEY_NPAGE':
            self.scroll_row(self.height()-4)
        elif c == 'KEY_SR' or c == 'J':
            self.scroll_row(-1)
        elif c == 'KEY_SF' or c == 'K':
            self.scroll_row(1)
        elif c == 'KEY_SLEFT' or c == 'H':
            self.scroll_col(-1)
        elif c == 'KEY_SRIGHT' or c == 'L':
            self.scroll_col(1)

    def table(self, columns, data):
        """
        Draw a table in this view.
        """
        if not columns or data is None:
            return

        self._table = (len(columns), len(data))

        table = tabulate(data, headers=columns, tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

        # draw the table
        vt = Terminal.inst().view(self._id)
        if vt:
            vt.draw('', table, True)
