# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# terminal displayer

import os
import sys
# import colorama
import time
import threading
import platform

import curses
from curses.textpad import Textbox, rectangle
from tabulate import tabulate

import logging
error_logger = logging.getLogger('siis.error.terminal')


class Color(object):

    WHITE = '\033[0;0m'    # '\\0'
    RED = '\033[31m'       # '\\1'
    ORANGE = '\033[33m'    # '\\2'
    YELLOW = '\033[33;1m'  # '\\3'
    BLUE = '\033[34;1m'    # '\\4'
    GREEN = '\033[32m'     # '\\5'
    PURPLE = '\033[35m'    # '\\6'
    CYAN = '\033[36m'      # '\\7'
    HIGHLIGHT = '\033[0;1m'   # '\\8'
    LIGHTRED = '\033[31m;1m'  # '\\9'

    UTERM_COLORS_MAP = {
        WHITE: '\\0',     # white (normal)
        RED: '\\1',       # red
        ORANGE: '\\2',    # orange
        YELLOW: '\\3',    # yellow
        BLUE: '\\4',      # blue
        GREEN: '\\5',     # green
        PURPLE: '\\6',    # purple
        CYAN: '\\7',      # cyan
        HIGHLIGHT: '\\8', # hightlight
        LIGHTRED: '\\9',  # light-red
    }

    FROM_INT = (
        WHITE,
        RED,
        GREEN,
        ORANGE,
        BLUE,
        PURPLE,
        YELLOW,
        CYAN,
        HIGHLIGHT,
        LIGHTRED
    )

    # colorama.Style.RESET_ALL,  # Terminal.DEFAULT
    # colorama.Fore.RED,  # Terminal.ERROR
    # colorama.Fore.YELLOW + colorama.Style.BRIGHT,  # Terminal.WARNING
    # colorama.Fore.YELLOW,  # Terminal.ACTION
    # colorama.Fore.CYAN,  # Terminal.NOTICE
    # colorama.Fore.GREEN,  # Terminal.HIGH
    # colorama.Fore.MAGENTA,  # Terminal.LOW
    # colorama.Fore.WHITE,  # Terminal.NEUTRAL
    # colorama.Fore.WHITE + colorama.Style.BRIGHT,  # Terminal.HIGHLIGHT

    @staticmethod
    def count():
        return len(Color.FROM_INT)

    @staticmethod
    def color(value):
        return Color.FROM_INT[value] if -1 < value < len(Color.FROM_INT) else Color.WHITE

    @staticmethod
    def colorize(value, color, style=None):
        if style is None:
            style = Terminal.inst().style()

        if style == 'uterm' or style == 'curses':
            return color + value + Color.WHITE

        return value

    @staticmethod
    def colorize_updn(value, v0, v1, style=None, up=GREEN, down=RED):
        if style is None:
            style = Terminal.inst().style()

        if style == 'uterm' or style == 'curses':
            if v0 is None or v1 is None:
                return value

            if v0 < v1:
                return up + value + Color.WHITE
            elif v0 > v1:
                return down + value + Color.WHITE
            else:
                return value

        return value

    @staticmethod
    def colorize_cond(value, cond, style=None, true=GREEN, false=WHITE):
        if style is None:
            style = Terminal.inst().style()

        if style == 'uterm' or style == 'curses':
            if cond:
                return true + value + Color.WHITE
            else:
                return false + value + Color.WHITE

        return value


class View(object):

    MODE_STREAM = 0
    MODE_BLOCK = 1

    # UTERM_COLORS = [
    #     colorama.Style.RESET_ALL,  # Terminal.DEFAULT
    #     colorama.Fore.RED,  # Terminal.ERROR
    #     colorama.Fore.YELLOW + colorama.Style.BRIGHT,  # Terminal.WARNING
    #     colorama.Fore.YELLOW,  # Terminal.ACTION
    #     colorama.Fore.CYAN,  # Terminal.NOTICE
    #     colorama.Fore.GREEN,  # Terminal.HIGH
    #     colorama.Fore.MAGENTA,  # Terminal.LOW
    #     colorama.Fore.WHITE,  # Terminal.NEUTRAL
    #     colorama.Fore.WHITE + colorama.Style.BRIGHT,  # Terminal.HIGHLIGHT
    # ]

    def __init__(self, name, mode=MODE_STREAM, stdscr=None, pos=(0, 0), size=(80, 25), active=True, right_align=False, border=False, bg=None, window=False):
        self._name = name
        self._mode = mode
        self._active = active

        self._mutex = threading.RLock()
        self._content = []

        self._right_align = right_align
        self._border = border
        self._win = None
        self._dirty = False
        self._need_nl = False

        self._rect = (-1, -1, 0, 0)
        self._n = 0

        self._first_row = 0
        self._first_col = 0

        self._table_first_row = 0
        self._table_first_col = 0
        self._cur_table = (0, 0)

        self._parent_win = stdscr
        self._parent_size = (0, 0)

        if stdscr:
            # H, W, Y, X...
            height, width = stdscr.getmaxyx()

            # std resolution if empty area (screen, tmux, daemon...)
            if width <= 0:
                width = 80

            if height <= 0:
                height = 25

            self._rect = (size[1] or height, size[0] or width, pos[1], pos[0])
            self._parent_size = (height, width)

            if 1: # window:
                self._win = curses.newwin(*self._rect)
            else:
                self._win = stdscr.subwin(*self._rect)
                # self._win = stdscr.subpad(*self._rect)

            if mode == View.MODE_STREAM:
                # self._win.scrollok(1)
                self._win.scrollok(0)
            elif mode == View.MODE_BLOCK:
                self._win.scrollok(0)

            # WINDOW *subpad(WINDOW *orig, int nlines, int ncols, int begin_y, int begin_x);
            # int prefresh(WINDOW *pad, int pminrow, int pmincol, int sminrow, int smincol, int smaxrow, int 

            # self._win = curses.subpad(self._win, *self._rect)
            # self._win = curses.newpad(size[])

            if bg:
                pass  # self._win.bkgd()

            # self.clear()

    @property
    def mode(self):
        return self._mode

    @property
    def name(self):
        return self._name

    def erase(self):
        if self._win:
            self._dirty = True
            self._win.erase()

    def clear(self):
        if self._win:
            # if self._border:
            #     self._win.hline(0, 0, curses.ACS_HLINE, self._rect[1])
            #     self._n = 1
            # else:
            #     self._n = 0
            self._n = 0

            if self._mode == View.MODE_STREAM:
                self._content = []
                self._first_row = 0

            elif self._mode == View.MODE_BLOCK:
                self._content = []

            self._dirty = True
            self._win.erase()

    @property
    def height(self):
        return self._rect[0]

    @property
    def width(self):
        return self._rect[1]

    #
    # drawing
    #

    def __cprint(self, n, x, content, x_ofs=0):
        # self._win.move(n, x)

        elts = []

        color = curses.color_pair(0)
        next_is_color = False
        buf = ""
        xp = x
        ix = 0

        for c in content:
            if c == '\\':
                next_is_color = True
                if buf:
                    elts.append((buf, color))
                    buf = ""
            else:
                if next_is_color:
                    next_is_color = False

                    if ord('0') <= ord(c) <= ord('9'):
                        color = curses.color_pair(int(c))
                    else:
                        buf += '\\'

                elif xp < self.width + x_ofs:
                    if ix >= x_ofs:
                        buf += c

                    xp += 1
                    ix += 1

        if buf:
            # remaining part
            elts.append((buf, color))

        for elt in elts:
            self._win.addstr(elt[0], elt[1])

    def __uprint(self, n, x, content):
        elts = []

        color = ""
        next_is_color = False
        buf = ""
        xp = x

        for c in content:
            if c == '\\':
                next_is_color = True
                if buf:
                    elts.append((buf, color))
                    buf = ""
            else:
                if next_is_color:
                    next_is_color = False

                    if ord('0') <= ord(c) <= ord('9'):
                        color = Color.color(int(c))  #  View.UTERM_COLORS[int(c)]
                    else:
                        buf += '\\'
                elif xp < 200: # self.width:
                    buf += c

        if buf:
            elts.append((buf, color))

        for elt in elts:
            sys.stdout.write(elt[1])
            sys.stdout.write(elt[0])
            sys.stdout.write(Color.color(0))  # View.UTERM_COLORS[0])

    def draw(self, color, content, endl):
        with self._mutex:
            try:
                self._dirty = True

                if self._win:
                    if self._mode == View.MODE_STREAM:
                        self.erase()

                        rows = content.split('\n')
                        n = 0

                        for row in rows:
                            self._content.append(color+row+Terminal.DEFAULT)

                        if len(self._content) > Terminal.MAX_NUM_ENTRIES:
                            m = len(self._content) - Terminal.MAX_NUM_ENTRIES
                            self._content = self._content[-Terminal.MAX_NUM_ENTRIES:]

                            self._n -= m
                            self._first_row -= m

                        self._first_row = 0  # auto scroll
                        start = max(0, len(self._content)-self.height+self._first_row)

                        for row in self._content[start:]:
                            if self._active:
                                if self._right_align:
                                    # @todo not perfect because count non color escapes
                                    rm = row.count('\\')
                                    x = max(0, self.width - len(row) - rm - 1)
                                else:
                                    x = 0

                                try:
                                    self._win.move(n, x)
                                    self.__cprint(n, x, row, self._first_col)
                                except:
                                    pass

                                self._n += 1
                                n += 1

                    elif self._mode == View.MODE_BLOCK:
                        self.clear()

                        rows = content.split('\n')
                        self._content = []  # reset content
                        self._n = 0

                        n = 0

                        for row in rows:
                            self._content.append(color+row+Terminal.DEFAULT)

                            if self._active:
                                if n >= self._first_row and n < self.height:
                                    if self._right_align:
                                        # not perfect because count non color escapes
                                        rm = row.count('\\')
                                        x = max(0, self.width - len(row) - rm - 1)
                                    else:
                                        x = 0

                                    try:
                                        self._win.move(self._n, x)
                                        self.__cprint(self._n, x, color+row, self._first_col)
                                    except:
                                        pass

                                    self._n += 1

                                n += 1

                else:
                    rows = content.split('\n')

                    for row in rows:
                        self._content.append(color+row+Terminal.DEFAULT)

                    if len(self._content) > Terminal.MAX_NUM_ENTRIES:
                        m = len(self._content) - Terminal.MAX_NUM_ENTRIES
                        self._content = self._content[-Terminal.MAX_NUM_ENTRIES:]

                        self._first_row -= m
                        self._n -= m  # to refresh the newest

            except Exception as e:
                error_logger.error(str(e))

    def reshape(self, h, w):
        """
        When terminal size changes.
        @todo Have to reshape any of the views and redraw the actives.
        """
        self._n = 0

        self._first_row = 0
        self._first_col = 0

        self._table_first_row = 0
        self._table_first_col = 0

        self._win = None

        if self._parent_win:
            height, width = self._parent_win.getmaxyx()

            # std resolution if empty area (screen, tmux, daemon...)
            if width <= 0:
                width = 80

            if height <= 0:
                height = 25

            hr = height / self._parent_size[0]
            wr = width / self._parent_size[1]

            self._parent_size = (height, width)

            # H, W, Y, X...
            self._rect = (
                int(round(self._rect[0] * hr)),
                int(round(self._rect[1] * wr)),
                int(round(self._rect[2] * hr)),
                int(round(self._rect[3] * wr))
            )

            if 1: # window:
                self._win = curses.newwin(*self._rect)
            else:
                self._win = stdscr.subwin(*self._rect)
                # self._win = stdscr.subpad(*self._rect)

            if self._mode == View.MODE_STREAM:
                self._win.scrollok(0)
                self._first_row = 0
            elif self._mode == View.MODE_BLOCK:
                self._win.scrollok(0)

    def redraw(self):
        with self._mutex:
            try:
                if self._win:
                    self.erase()

                    if self._mode == View.MODE_STREAM:
                        if self._active:
                            # max n rows
                            n = 0

                            start = max(0, len(self._content)-self.height+self._first_row)

                            for row in self._content[start:]:
                                if self._right_align:
                                    rm = row.count('\\')
                                    x = max(0, self.width - len(row) - rm - 1)
                                else:
                                    x = 0

                                try:
                                    self._win.move(n, x)
                                    self.__cprint(n, x, row, self._first_col)
                                    n += 1
                                except:
                                    pass

                    elif self._mode == View.MODE_BLOCK:
                        if self._active:
                            self._n = 0

                            for row in self._content[self._first_row : self._first_row+self.height]:
                                if self._right_align:
                                    rm = row.count('\\')
                                    x = max(0, self.width - len(row) - rm - 1)
                                else:
                                    x = 0

                                try:
                                    self._win.move(self._n, x)
                                    self.__cprint(self._n, x, row, self._first_col)
                                    self._n += 1
                                except:
                                    pass
                else:
                    self.clear()

                    if self._mode == View.MODE_STREAM:
                        if self._active:
                            for row in self._content:
                                self.__uprint(0, 0, row)

                    elif self._mode == View.MODE_BLOCK:
                        if self._active:
                            for row in self._content:
                                self.__uprint(0, 0, row)

            except Exception as e:
                error_logger.error(str(e))

    def refresh(self):
        with self._mutex:
            try:
                if self._win:
                    if self._active and self._dirty:
                        self._win.refresh()
                        self._dirty = False
                else:
                    if self._active and self._dirty:
                        for row in self._content[self._n:]:
                            self.__uprint(0, 0, row)
                            sys.stdout.write('\n')

                        sys.stdout.flush()

                        # next row to display
                        self._n = len(self._content)
                        self._dirty = False

            except Exception as e:
                error_logger.error(str(e))

    #
    # hard scrolling
    #

    def scroll(self, n):
        """
        Vertical hard scrolling.
        Scroll n row of text.
        """
        with self._mutex:
            try:
                if self._mode == View.MODE_STREAM:
                    if n < 0:
                        self._first_row += n

                        if self._first_row < -len(self._content)+self.height:
                            self._first_row = -len(self._content)+self.height

                        self._dirty = True

                    elif n > 0:
                        self._first_row += n

                        if self._first_row > 0:
                            self._first_row = 0

                        self._dirty = True

                elif self._mode == View.MODE_BLOCK:
                    if n < 0:
                        self._first_row += n

                        if self._first_row < 0:
                            self._first_row = 0

                        self._dirty = True

                    elif n > 0:
                        self._first_row += n

                        if self._first_row >= len(self._content):
                            self._first_row = len(self._content)-1

                        self._dirty = True

            except Exception as e:
                error_logger.error(str(e))

    def hor_scroll(self, n):
        """
        Horizontal hard scrolling.
        Scroll of n characters from left or right.
        """
        if self._mode == View.MODE_BLOCK:
            if n < 0:
                self._first_col += n

                if self._first_col < 0:
                    self._first_col = 0

                self._dirty = True

            elif n > 0:
                self._first_col += n

                if self._first_col >= self.width:
                    self._first_col = self.width - 1

                self._dirty = True

    #
    # table
    #

    def draw_table(self, dataframe):
        """
        Display a table with a header header and a body,
        """
        if not dataframe:
            return

        HEADER_SIZE = 3

        # count rows
        data_rows = len(next(iter(dataframe.values())))

        # count columns
        num_columns = len(dataframe)
        num_rows = min(self.height - HEADER_SIZE - 1, data_rows)

        if self._table_first_row >= num_rows:
            self._table_first_row = 0

        if self._table_first_col >= num_columns:
            self._table_first_col = 0
      
        df = {}

        n = 0
        for k, v in dataframe.items():
            # ignore first columns
            if n >= self._table_first_col:
                # rows offset:limit
                df[k] = v[self._table_first_row:self._table_first_row+num_rows]
                n += 1

        # self._cur_table = (len(columns), len(data))

        table = tabulate(df, headers=columns, tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

        # draw the table
        self.draw('', table)

    def draw_table(self, columns, data, total_size=None):
        """
        Display a table with a header header and a body,
        """
        if not columns or data is None:
            return

        # HEADER_SIZE = 3

        # # count rows
        # data_rows = len(data)

        # # count columns
        # num_columns = len(columns)
        # num_rows = min(self.height - HEADER_SIZE - 1, data_rows)

        # if self._table_first_row >= num_rows:
        #     self._table_first_row = 0

        # if self._table_first_col >= num_columns:
        #     self._table_first_col = 0

        # columns = columns[self._table_first_col:]
        # data_arr = []

        # for d in data[self._table_first_row:self._table_first_row+num_rows]:
        #     # ignore some columns and some rows
        #     data_arr.append(d[self._table_first_col:])

        self._cur_table = total_size if total_size else (len(columns), len(data))

        table = tabulate(data, headers=columns, tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

        # replace color espace code before drawing
        for k, v in Color.UTERM_COLORS_MAP.items():
            table = table.replace(k, v)

        # draw the table
        self.draw('', table, True)

    def table_scroll_row(self, n):
        """
        Scroll n row (positive or negative) from current first row.
        The max number of displayed row depend of the height of the view.
        """
        self._table_first_row += n

        if self._table_first_row < 0:
            self._table_first_row = 0

        if self._table_first_row >= self._cur_table[1]:
            self._table_first_row = self._cur_table[1] - 1

    def table_scroll_cols(self, n):
        """
        Scroll n columnes (positive or negative) from current first columns.
        """
        self._table_first_col += n

        if self._table_first_col < 0:
            self._table_first_col = 0

        if self._table_first_col >= self._cur_table[0]:
            self._table_first_col = self._cur_table[0] -1

    def format(self):
        return Terminal.inst().style(), self._table_first_row, self.height - 4, self._table_first_col
  

class Terminal(object):
    """
    Terminal display helper, but could uses curses.
    """

    MAX_NUM_ENTRIES = 1000
    USE_NCURSE = True

    DEFAULT = '\\0'
    ERROR = '\\1'
    WARNING = '\\2'
    ACTION = '\\3'
    NOTICE = '\\4'
    HIGH = '\\5'
    LOW = '\\6'
    NEUTRAL = '\\7'
    HIGHLIGHT = '\\8'

    MODE_DEFAULT = 0
    MODE_COMMAND = 1
    MODE_LOCKED = 2

    @classmethod
    def inst(cls):
        global terminal
        return terminal

    @classmethod
    def terminate(cls):
        global terminal
        # colorama.deinit()

        if terminal:
            terminal.restore_term()
            terminal.cleanup()
            terminal = None

    def __init__(self):
        global terminal  # singleton
        terminal = self

        self._mutex = threading.RLock()

        self._views = {
            'default': View('default', View.MODE_STREAM, False),
            'content': View('content', View.MODE_STREAM, False),
            'debug': View('debug', View.MODE_STREAM, False)
        }

        self._fd = None
        self._stdscr = None
        self._direct_draw = True
        self._active_content = 'content'
        self._old_default = None
        self._key = None
        self._mode = Terminal.MODE_DEFAULT
        self._query_reshape = 0.0

    def upgrade(self):
        self.setup_term(True)
        self._direct_draw = False

    def setup_term(self, use_ncurses: bool):
        # install key grabber
        height, width = 0, 0

        if not self._fd and not use_ncurses:
            fd = sys.stdin.fileno()

            oldterm = termios.tcgetattr(fd)
            newattr = termios.tcgetattr(fd)
            newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, newattr)

            oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

            self._fd = fd

            # colorama.init()

        elif not self._stdscr and use_ncurses:
            os.environ.setdefault('ESCDELAY', '25')
            self._stdscr = curses.initscr()
            self._stdscr.keypad(True)
            self._stdscr.nodelay(True)

            # curses.mousemask(1)
            # self._stdscr.scrollok(True)

            curses.noecho()
            curses.curs_set(0)

            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()

                if curses.can_change_color():
                    try:
                        curses.init_color(curses.COLOR_BLUE, 384, 384, 800)
                    except Exception as e:
                        error_logger.error(str(e))

                curses.init_pair(0, curses.COLOR_WHITE, -1)
                curses.init_pair(1, curses.COLOR_RED, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_BLUE, -1)
                curses.init_pair(4, curses.COLOR_CYAN, -1)
                curses.init_pair(5, curses.COLOR_GREEN, -1)
                curses.init_pair(6, curses.COLOR_MAGENTA, -1)
                curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
                curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)
                curses.init_pair(9, curses.COLOR_YELLOW, curses.COLOR_BLUE)

            height, width = self._stdscr.getmaxyx()

            # std resolution if empty area (screen, tmux, daemon...)
            if width <= 0:
                width = 80

            if height <= 0:
                height = 25

        # to restore at terminate
        self._old_default = self._views

        w1 = int(width*0.9)
        w2 = width-w1

        free_h = 4
        h1 = height - 2 - 2 - free_h

        old_default_content = self._views['default']._content
        old_content_content = self._views['content']._content
        old_debug_content = self._views['debug']._content

        self._views = {
            # top
            'info': View('info', View.MODE_BLOCK, self._stdscr, pos=(0, 0), size=(width//2, 1), active=True),
            'help': View('help', View.MODE_BLOCK, self._stdscr, pos=(width//2, 0), size=(width//2, 1), active=True, right_align=True),

            # body
            'content-head': View('content-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 1), active=True),
            'content': View('content', View.MODE_STREAM, self._stdscr, pos=(0, 2), size=(w1, h1), active=True, border=True),

            'debug-head': View('debug-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 1), active=False),
            'debug': View('debug', View.MODE_STREAM, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            # right panel
            'panel-head': View('panel-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w2, 1), active=True),
            'panel': View('panel', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w2, h1), active=True, border=True),

            # bottom 
            'default': View('default', View.MODE_STREAM, self._stdscr, pos=(0, height-6), size=(width, free_h), active=True),

            'command': View('command', View.MODE_BLOCK, self._stdscr, pos=(0, height-2), size=(width, 1), active=True, window=True),
            'status': View('status', View.MODE_BLOCK, self._stdscr, pos=(0, height-1), size=(width//2, 1), active=True),
            'notice': View('notice', View.MODE_BLOCK, self._stdscr, pos=(width//2+1, height-1), size=(width//2, 1), active=True, right_align=True),
        }

        self._views['default']._content = old_default_content
        self._views['content']._content = old_content_content
        self._views['debug']._content = old_debug_content

        self.set_view('default')
        self._active_content = 'content'

        Terminal.inst().info("Console", view='content-head')
        Terminal.inst().info("Debug", view='debug-head')
        Terminal.inst().info("Signal", view='signal-head')

    def restore_term(self):
        if self._fd:
            termios.tcsetattr(self._fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(self._fd, fcntl.F_SETFL, oldflags)

        if self._stdscr:
            curses.nocbreak()
            curses.echo()
            curses.endwin()
            curses.curs_set(1)

            self._stdscr = None

        if self._old_default:
            self._views = self._old_default
            self._old_default = None

        # clear content
        if 'default' in self._views:
            self._views['default']._content = []
        if 'content' in self._views:
            self._views['content']._content = []
        if 'debug' in self._views:
            self._views['debug']._content = []

        self._direct_draw = True

    def cleanup(self):
        if self._stdscr:
            self._stdscr.keypad(False)

    def create_content_view(self, name):
        if name in self._views:
            raise Exception("View %s already exists" % name)

        if self._stdscr:
            height, width = self._stdscr.getmaxyx()
        else:
            height, width = 0, 0

        w1 = int(width*0.9)
        w2 = width-w1

        free_h = 4
        h1 = height - 2 - 2 - free_h

        head_view = View(name+'-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 1), active=False)
        view = View(name, View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True)

        self._views[name] = view
        self._views[name+'-head'] = head_view

        return view

    def set_title(self, name, title):
        self.info(title, view=name+'-head')

    def destroy_content_view(self, name):
        if name in ('content', 'debug'):
            # system views, undeletable
            return

        # a content view has a head view
        if name in self._views and name+'-head' in self._views:
            if self._active_content == name:
                # if active content switch to default content
                self.switch_view('content')

            del self._views[name]
            del self._views[name+'-head']

    def active_content(self):
        if self._active_content in self._views:
            return self._views[self._active_content]
        else:
            return None

    def is_active(self, view):
        view = self._views.get(view)
        return view and view._active

    def view(self, view):
        return self._views.get(view)

    def clear(self):
        if self._fd and not self._stdscr:
            if platform.system()=="Windows":
                os.system('cls')
            else:  # Linux and Mac
                # print("\033c")
                print(chr(27) + "[2J", end='')
        elif self._stdscr:
            self._win.erase()

    def style(self):
        if self._stdscr and not self._direct_draw:
            return "curses"
        else:
            return "uterm"

    def set_view(self, view='default'):
        _view = self._views.get(view)     
        if _view:
            _view.redraw()

    def switch_view(self, view):
        """
        Switch the active content + header-content views to another couple.
        """
        with self._mutex:
            if view != self._active_content:
                av = self._views.get(self._active_content)
                hav = self._views.get(self._active_content + '-head')

                bv = self._views.get(view)
                hbv = self._views.get(view + '-head')

                if av and bv and hav and hbv:
                    if av._active:
                        av._active = False
                        hav._active = False
                        bv._active = True
                        hbv._active = True

                        hbv.redraw()
                        bv.redraw()
                    else:
                        av._active = True
                        hav._active = True
                        bv._active = False
                        hbv._active = False

                        hav.redraw()
                        av.redraw()

                self._active_content = view

    def _append(self, color, content, endl, view):
        _view = self._views.get(view)

        if _view:
            _view.draw(color, content or "", endl)

            if self._direct_draw:
                _view.refresh()

    def message(self, message, endl=True, view='default'):
        self._append(Terminal.DEFAULT, message, endl, view)

    def info(self, message, endl=True, view='default'):
        self._append(Terminal.HIGHLIGHT, message, endl, view)

    def error(self, message, endl=True, view='default'):
        self._append(Terminal.ERROR, message, endl, view)
    
    def notice(self, message, endl=True, view='default'):
        self._append(Terminal.NOTICE, message, endl, view)

    def warning(self, message, endl=True, view='default'):
        self._append(Terminal.WARNING, message, endl, view)

    def high(self, message, endl=True, view='default'):
        self._append(Terminal.HIGH, message, endl, view)

    def low(self, message, endl=True, view='default'):
        self._append(Terminal.LOW, message, endl, view)

    def action(self, message, endl=True, view='default'):
        self._append(Terminal.ACTION, message, endl, view)

    def table(self, columns, data, total_size=None, view='content'):
        _view = self._views.get(view)

        if _view:
            _view.draw_table(columns, data,  total_size)

            if self._direct_draw:
                _view.refresh()

    def read(self):
        c = None
        self._key = None

        if self._fd:
            c = sys.stdin.read(1)
        elif self._stdscr:
            try:
                # ch = self._stdscr.getch()
                c = self._stdscr.getkey()

                # if ch == curses.ascii.ESC:
                if ord(c[0]) == 27:
                    self._key = 'KEY_ESCAPE'
                    return None

                if c[0] == '\t':
                    self._key = 'KEY_STAB'
                    return None

                if c[0] == '\n':
                    self._key = 'KEY_ENTER'
                    return '\n'

            except:
                pass

            # https://docs.python.org/2/library/curses.html keys list
            if c and (c.startswith('KEY_') or (c in ('h', 'j', 'k', 'l') and self._mode == Terminal.MODE_DEFAULT)):
                if c == 'KEY_BACKSPACE':
                    self._key = c
                    return '\b'

                elif c == 'KEY_ENTER':
                    self._key = c
                    return '\n'

                elif c == 'KEY_BTAB':
                    self._key = 'KEY_BTAB'
                    return None

                elif c == 'KEY_RESIZE':  # ch == curses.KEY_RESIZE:
                    if not self._query_reshape:
                        self._query_reshape = time.time() + 0.5

                # shift + keys arrows for table navigation only in default mode (ch == curses.KEY_SUP)
                elif (c == 'KEY_SR' or c == 'j'):
                    if self._active_content and self._mode == Terminal.MODE_DEFAULT:
                        view = self._views.get(self._active_content)
                        if view:
                            if view.mode == View.MODE_STREAM:
                                view.scroll(-1)
                                view.redraw()
                            elif view.mode == View.MODE_BLOCK:
                                view.table_scroll_row(-1)

                    self._key = c
                elif (c == 'KEY_SF' or c == 'k'):
                    if self._active_content and self._mode == Terminal.MODE_DEFAULT:
                        view = self._views.get(self._active_content)
                        if view:
                            if view.mode == View.MODE_STREAM:
                                view.scroll(1)
                                view.redraw()
                            elif view.mode == View.MODE_BLOCK:
                                view.table_scroll_row(1)

                    self._key = c
                elif (c == 'KEY_SLEFT' or c == 'h'):
                    if self._active_content and self._mode == Terminal.MODE_DEFAULT:
                        view = self._views.get(self._active_content)
                        if view:
                            view.table_scroll_cols(-1)

                    self._key = c
                elif (c == 'KEY_SRIGHT' or c == 'l'):
                    if self._active_content and self._mode == Terminal.MODE_DEFAULT:
                        view = self._views.get(self._active_content)
                        if view:
                            view.table_scroll_cols(1)

                    self._key = c

                # pageup/pagedown
                elif c == 'KEY_PPAGE':
                    if self._active_content and self._mode == Terminal.MODE_DEFAULT:
                        view = self._views.get(self._active_content)
                        if view:
                            if view.mode == View.MODE_STREAM:
                                view.scroll(-(view.height-4))
                                view.redraw()
                            elif view.mode == View.MODE_BLOCK:
                                view.table_scroll_row(-(view.height-4))

                    self._key = c
                elif c == 'KEY_NPAGE':
                    if self._active_content and self._mode == Terminal.MODE_DEFAULT:
                        view = self._views.get(self._active_content)
                        if view:
                            if view.mode == View.MODE_STREAM:
                                view.scroll((view.height-4))
                                view.redraw()
                            elif view.mode == View.MODE_BLOCK:
                                view.table_scroll_row(view.height-4)

                    self._key = c

                # keys arrows
                elif c in ('KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT'):
                    self._key = c

                # home/end key
                elif c in ('KEY_HOME', 'KEY_END', 'KEY_SNEXT', 'KEY_SPREVIOUS'):
                    self._key = c

                # F1 to F24
                elif c.startswith('KEY_F(') and c[-1] == ')':
                    self._key = c

                c = None

        return c

    def key(self):
        return self._key

    def flush(self, view='default'):
        with self._mutex:
            _view = self._views.get(view)
            if _view:
                _view.refresh()

    def update(self):
        if self._query_reshape < 0 and time.time() > -self._query_reshape:
            self._query_reshape = 0.0

        if self._query_reshape > 0 and time.time() > self._query_reshape + 0.5:
            height, width = self._stdscr.getmaxyx()

            self._stdscr.clear()
            curses.resizeterm(height, width)

            for k, view in self._views.items():
                # reshape any views
                view.reshape(height, width)

            self._views.get('info').redraw()
            self._views.get('help').redraw()
            self._views.get('default').redraw()
            self._views.get('command').redraw()
            self._views.get('status').redraw()
            self._views.get('notice').redraw()
            self._views.get('panel').redraw()
            self._views.get('panel-head').redraw()

            if self._active_content:
                view = self._views.get(self._active_content)
                if view:
                    view.redraw()

            self._stdscr.refresh()
            self._query_reshape = -time.time() - 0.5

        for k, view in self._views.items():
            view.refresh()

    def clear_content(self):
        if self._active_content:
            view = self._views.get(self._active_content)
            if view:
                view.clear()

    def set_mode(self, mode):
        self._mode = mode

    @property
    def mode(self):
        return self._mode
