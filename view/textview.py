# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Text view base class.

from terminal.terminal import Terminal
from view.view import View


class TextView(View):
    """
    Text view base class.
    """

    MAX_ROWS = 10000

    def __init__(self, _id, service):
        super().__init__(_id, service)

        self._row = [0, 0]  # offset, limit
        self._col = 0       # offset

        self._content = []  # array of line of content

    def scroll_row(self, n):
        """
        Scroll n row (positive or negative) from current first row.
        The max number of displayed row depend of the height of the view.
        """
        self._row[0] += n

        if self._row[0] < 0:
            self._row[0] = 0

        h = self.height()

        if self._row[0] >= len(self._content) - h:
            self._row[0] = len(self._content) - h - 1

        self._refresh = 0

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if key == 'KEY_PPAGE':
            self.scroll_row(-(self.height()-4))   
        elif key == 'KEY_NPAGE':
            self.scroll_row(self.height()-4)
        elif c == 'KEY_SR':
            self.scroll_row(-1)
        elif c == 'KEY_SF':
            self.scroll_row(1)

    def print(self, rows):
        self._content.append(rows)

        # redraw/memory limit
        if len(self._content) > TextView.MAX_ROWS:
            self._content = self._content[-TextView.MAX_ROWS:]
