# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal displayer

import os
import sys
import colorama
import time
import threading
import platform

import curses
from curses.textpad import Textbox, rectangle
from tabulate import tabulate


class View(object):

    MODE_STREAM = 0
    MODE_BLOCK = 1

    UTERM_COLORS_MAP = {
        '\033[0m': '\\0',   # white (normal)
        '\033[31m': '\\1',  # red
        '\033[32m': '\\5',  # green
        '\033[33m': '\\6',  # orange
        '\033[34m': '\\4',  # blue
        '\033[35m': '\\2'   # purple
    }

    UTERM_COLORS = [
        colorama.Style.RESET_ALL,  # Terminal.DEFAULT
        colorama.Fore.RED,  # Terminal.ERROR
        colorama.Back.YELLOW + colorama.Fore.WHITE,  # Terminal.WARNING
        colorama.Fore.YELLOW,  # Terminal.ACTION
        colorama.Fore.CYAN,  # Terminal.NOTICE
        colorama.Fore.GREEN,  # Terminal.HIGH
        colorama.Fore.MAGENTA,  # Terminal.LOW
        colorama.Fore.WHITE,  # Terminal.NEUTRAL
        colorama.Fore.WHITE + colorama.Style.BRIGHT,  # Terminal.HIGHLIGHT
    ]

    def __init__(self, name, mode=MODE_STREAM, stdscr=None, pos=(0, 0), size=(80, 25), active=True, right_align=False, border=False, bg=None, window=False):
        self._name = name
        self._mode = mode
        self._active = active

        self._mutex = threading.Lock()

        if mode == View.MODE_STREAM:
            self._content = [""]
        elif mode == View.MODE_BLOCK:
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

        self._parent_win = stdscr

        if stdscr:
            height, width = stdscr.getmaxyx()
            # H, W, Y, X...
            self._rect = (size[1] or height, size[0] or width, pos[1], pos[0])

            if 1: # window:
                self._win = curses.newwin(*self._rect)
            else:
                self._win = stdscr.subwin(*self._rect)
                # self._win = stdscr.subpad(*self._rect)

            if mode == View.MODE_STREAM:
                self._win.scrollok(1)
            elif mode == View.MODE_BLOCK:
                self._win.scrollok(0)

            # WINDOW *subpad(WINDOW *orig, int nlines, int ncols, int begin_y, int begin_x);
            # int prefresh(WINDOW *pad, int pminrow, int pmincol, int sminrow, int smincol, int smaxrow, int 

            # self._win = curses.subpad(self._win, *self._rect)
            # self._win = curses.newpad(size[])

            if bg:
                pass  # self._win.bkgd()

            # self.clear()

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    @property
    def mode(self):
        return self._mode
    
    @property
    def content(self):
        return self._content
    
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
                self._content = [""]
                self._first_row = 0
            elif self._mode == View.MODE_BLOCK:
                self._content = []
                # self._first_row = 0

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
                        color = View.UTERM_COLORS[int(c)]
                    else:
                        buf += '\\'
                elif xp < 200: # self.width:
                    buf += c

        if buf:
            elts.append((buf, color))

        for elt in elts:
            sys.stdout.write(elt[1])
            sys.stdout.write(elt[0])
            sys.stdout.write(View.UTERM_COLORS[0])

    def draw(self, color, content, endl):
        self.lock()

        self._dirty = True

        if self._win:
            if self._mode == View.MODE_STREAM:
                rows = content.split('\n')
                nl = self._need_nl

                n = 0  # relative row count because scroll auto in stream mode

                for row in rows:
                    if nl:
                        # new line needed
                        self._content.append("")
                        self._win.addstr('\n')
                        nl = False

                    self._content[-1] += color+row+Terminal.DEFAULT

                    if self._active:
                        _y, _x = self._win.getyx()
                        if _y >= self.height:
                            self.clear()

                        if self._right_align:
                            # @todo not perfect because count non color escapes
                            rm = row.count('\\')
                            x = max(0, self.width - len(row) - rm)
                        else:
                            x = 0

                        try:
                            self._win.move(_y-self._first_row, x)
                            self.__cprint(self._first_row+n+_y, x, row)
                            n += 1
                            # self._n += 1
                        except:
                            pass

                    # self._n += 1
                    #n += 1
                    nl = True

                    # self._first_row = max(0, self._n - self.height)

                self._n, _x = self._win.getyx()

                # new line for the next draw call
                self._need_nl = endl

            elif self._mode == View.MODE_BLOCK:
                self.clear()

                rows = content.split('\n')
                self._content = []  # reset content
                self._n = 0

                n = 0

                for row in rows:
                    self._content.append(color+content+Terminal.DEFAULT)

                    if self._active:
                        if n >= self._first_row and n < self.height:
                            if self._right_align:
                                # not perfect because count non color escapes
                                rm = row.count('\\')
                                x = max(0, self.width - len(row) - rm)
                            else:
                                x = 0

                            try:
                                self._win.move(self._n, x)
                                self.__cprint(self._n, x, row, self._first_col)
                            except:
                                pass

                            self._n += 1

                        n += 1

        else:
            rows = content.split('\n')
            nl = self._need_nl

            n = 0  # relative row count because scroll auto in stream mode

            for row in rows:
                if nl:
                    # new line needed
                    self._content.append("")
                    nl = False

                self._content[-1] += color+row+Terminal.DEFAULT
                nl = True

            # new line for the next draw call
            self._need_nl = endl

            if len(self._content) > Terminal.MAX_NUM_ENTRIES:
                self._content.pop(0)
                self._first_row -= 1

                if self._first_row < 0:
                    self._first_row = 0

        self.unlock()

    def reshape(self, w, h):
        """
        When terminal size changes.
        @todo Have to reshape any of the views and redraw the actives.
        """
        pass

    def redraw(self):
        self.lock()

        if self._win:
            self.erase()  # self.clear()

            if self._mode == View.MODE_STREAM:
                if self._active:
                    # max n rows
                    self._n = self._first_row
                    start = max(0, len(self._content) - self.height)

                    for row in self._content[self._first_row+start : self._first_row+start+self.height]:
                        try:
                            if self._right_align:
                                rm = row.count('\\')
                                x = max(0, self.width - len(row) - rm - 1)
                            else:
                                x = 0

                            if self._n > 0:
                                self._win.addstr('\n')

                            self.__cprint(self._n, x, row)
                            self._n += 1
                        except:
                            pass

            elif self._mode == View.MODE_BLOCK:
                if self._active:
                    self._n = 0

                    for row in self._content[self._first_row : self._first_row+self.height]:
                        if self._right_align:
                            rm = row.count('\\')
                            x = max(0, self.width - len(row) - rm)
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

        self.unlock()

    def refresh(self):
        self.lock()

        if self._win:
            if self._active and self._dirty:
                self._win.refresh()
                self._dirty = False
        else:
            if self._active and self._dirty:
                for row in self._content[self._n:]:
                    self.__uprint(0, 0, row)

                if self._need_nl:
                    sys.stdout.write('\n')

                sys.stdout.flush()
                self._n = len(self._content)

                self._dirty = False

        self.unlock()

    #
    # hard scrolling
    #

    def scroll(self, n):
        """
        Vertical hard scrolling.
        Scroll n row of text.
        """
        self.lock()

        if self._mode == View.MODE_STREAM:
            if n < 0:
                self._first_row += n

                if self._first_row < 0:
                    self._first_row = 0

                if self._win:
                    self._win.scroll(n)

                self._dirty = True

            elif n > 0:
                self._first_row += n

                if self._first_row > len(self._content):
                    self._first_row = len(self._content)-1

                if self._win:
                    self._win.scroll(n)

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

        self.unlock()

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

        table = tabulate(df, headers=columns, tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

        # draw the table
        self.draw('', table)

    def draw_table(self, columns, data):
        """
        Display a table with a header header and a body,
        """
        if not columns or data is None:
            return

        HEADER_SIZE = 3

        # count rows
        data_rows = len(data)

        # count columns
        num_columns = len(columns)
        num_rows = min(self.height - HEADER_SIZE - 1, data_rows)

        if self._table_first_row >= num_rows:
            self._table_first_row = 0

        if self._table_first_col >= num_columns:
            self._table_first_col = 0
      
        columns = columns[self._table_first_col:]
        data_arr = []

        for d in data[self._table_first_row:self._table_first_row+num_rows]:
            # ignore some columns and some rows
            data_arr.append(d[self._table_first_col:])

        table = tabulate(data, headers=columns, tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

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

    def table_scroll_cols(self, n):
        """
        Scroll n columnes (positive or negative) from current first columns.
        """
        self._table_first_col += n

        if self._table_first_col < 0:
            self._table_first_col = 0


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

    @classmethod
    def inst(cls):
        global terminal
        return terminal

    @classmethod
    def terminate(cls):
        global terminal
        colorama.deinit()

        if terminal:
            terminal.restore_term()
            terminal.cleanup()
            terminal = None

    def __init__(self):
        global terminal  # singleton
        terminal = self

        self._mutex = threading.Lock()

        self._views = {
            'default': View('default', View.MODE_STREAM, False),
            'content': View('content', View.MODE_STREAM, False),
            'message': View('message', View.MODE_STREAM, False),
            'error': View('error', View.MODE_STREAM, False),
            'debug': View('debug', View.MODE_STREAM, False),
            'grid': View('grid', View.MODE_BLOCK, False),            
        }

        self._fd = None
        self._stdscr = None
        self._active_view = self._views['default']
        self._direct_draw = True
        self._active_content = 'content'
        self._old_default = None
        self._key = None

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

            colorama.init()

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
                # curses.init_pair(0, curses.COLOR_WHITE, curses.COLOR_BLACK)
                curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
                curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_WHITE)
                curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
                curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
                curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
                curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
                curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
                # curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_BLACK)  # @todo and need bright
                curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)  # then use that for now

            height, width = self._stdscr.getmaxyx()

        # to restore at terminate
        self._old_default = self._views

        # @todo view must be in percent for reshape
        w1 = int(width*0.9)
        w2 = width-w1

        free_h = 4
        h1 = height - 2 - 2 - free_h

        self._views = {
            # top
            'info': View('info', View.MODE_BLOCK, self._stdscr, pos=(0, 0), size=(width//2, 1), active=True),
            'help': View('help', View.MODE_BLOCK, self._stdscr, pos=(width//2, 0), size=(width//2, 1), active=True, right_align=True),

            # body
            'content-head': View('content-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=True),
            'content': View('content', View.MODE_STREAM, self._stdscr, pos=(0, 2), size=(w1, h1), active=True, border=True),

            'trader-head': View('trader-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'trader': View('trader', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'stats-head': View('stats-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'stats': View('stats', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'perf-head': View('perf-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'perf': View('perf', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'strategy-head': View('strategy-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'strategy': View('strategy', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'account-head': View('account-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'account': View('account', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'market-head': View('market-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'market': View('market', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'ticker-head': View('ticker-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'ticker': View('ticker', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            'panel-head': View('panel', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w2, 2), active=True),
            'panel': View('panel', View.MODE_BLOCK, self._stdscr, pos=(0, 2), size=(w2, h1), active=True, border=True),

            'debug-head': View('debug-head', View.MODE_BLOCK, self._stdscr, pos=(0, 1), size=(w1, 2), active=False),
            'debug': View('debug', View.MODE_STREAM, self._stdscr, pos=(0, 2), size=(w1, h1), active=False, border=True),

            # bottom 
            'default': View('default', View.MODE_STREAM, self._stdscr, pos=(0, height-6), size=(width, free_h), active=True),
            
            'command': View('command', View.MODE_BLOCK, self._stdscr, pos=(0, height-2), size=(width, 1), active=True, window=True),
            'status': View('status', View.MODE_BLOCK, self._stdscr, pos=(0, height-1), size=(width//2, 1), active=True),
            'notice': View('notice', View.MODE_BLOCK, self._stdscr, pos=(width//2+1, height-1), size=(width//2, 1), active=True, right_align=True),
        }

        Terminal.inst().info("Content", view='content-head')
        Terminal.inst().info("Debug", view='debug-head')

        self.set_view('default')
        self._active_content = 'content'

    def restore_term(self):
        if self._fd:
            termios.tcsetattr(self._fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(self._fd, fcntl.F_SETFL, oldflags)

        if self._stdscr:
            curses.nocbreak()
            # curses.cbreak()
            curses.echo()
            curses.endwin()
            curses.curs_set(1)

            self._stdscr = None

        if self._old_default:
            self._views = self._old_default
            self._old_default = None
            self._active_view = self._views.get('default')

        self._direct_draw = True

    def cleanup(self):
        if self._stdscr:
            self._stdscr.keypad(False)

    def add_view(self, name, mode=View.MODE_STREAM):
        if not name in self._views:
            self._views[name] = View(name, mode)

    def remove_view(self, name):
        if name == 'default':
            return

        if self._active_view and self._active_view.name == name:
            self._active_view = self._views['default']

        if name in self._views:
            del self._views[name]

    def active_view(self):
        return self._active_view

    def is_active(self, view):
        view = self._views.get(view)
        return view and view._active

    def clear(self):
        if self._fd and not self._stdscr:
            if platform.system()=="Windows":
                os.system('cls')
            else:  # Linux and Mac
                # print("\033c")
                print(chr(27) + "[2J", end='')
        elif self._stdscr:
            # self._stdscr.clear()
            self._win.erase()

    def style(self):
        if self._stdscr and not self._direct_draw:
            return "curses"
        else:
            return "uterm"

    def set_view(self, view='default'):
        if self._active_view:
            if view != self._active_view.name:
                self._active_view = self._active_view.get(view)
        else:
            return

        _view = self._views.get(view)
        
        if _view:
            _view.redraw()

    def switch_view(self, view):
        self._mutex.acquire()

        if view != self._active_content:
            av = self._views.get(self._active_content)
            hav = self._views.get(self._active_content + '-head')

            bv = self._views.get(view)
            hbv = self._views.get(view + '-head')

            if 1:#av and bv:
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

        self._mutex.release()

    def blank(self, view='default'):
        _view = self._views.get(view)
        if _view:
            _view.lock()
            _view.unlock()

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

    def table(self, columns, data, view='content'):
        _view = self._views.get(view)

        if _view:
            _view.draw_table(columns, data)

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
            if c and c.startswith('KEY_'):
                
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
                    for k, view in self._views.items():
                        # reshape any views
                        view.reshape(*self._stdscr.getmaxyx())

                        # force redraw the active content
                        if self._active_content:
                            view = self._views.get(self._active_content)
                            if view:
                                view.redraw()

                # shift + keys arrows for hard scrolling
                # ch == curses.KEY_SUP
                elif c == 'KEY_SUP':
                    if self._active_content:
                        view = self._views.get(self._active_content)
                        if view:
                            view.scroll(-1)
                            view.redraw()
                elif c == 'KEY_SDOWN':
                    if self._active_content:
                        view = self._views.get(self._active_content)
                        if view:
                            view.scroll(1)
                            view.redraw()

                elif c == 'KEY_SLEFT':
                    if self._active_content:
                        view = self._views.get(self._active_content)
                        if view:
                            view.hor_scroll(-1)
                            view.redraw()
                elif c == 'KEY_SRIGHT':
                    if self._active_content:
                        view = self._views.get(self._active_content)
                        if view:
                            view.hor_scroll(1)
                            view.redraw()

                # keys arrows
                elif c in ('KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT'):
                    self._key = c

                # pageup/pagedown
                elif c in ('KEY_PPAGE', 'KEY_NPAGE'):
                    self._key = c

                # F1 to F24
                elif c.startswith('KEY_F(') and c[-1] == ')':
                    self._key = c

                # mouse handling
                elif c == 'KEY_MOUSE':
                    # @todo
                    # @ref https://www.gnu.org/software/guile-ncurses/manual/html_node/Mouse-handling.html#Mouse-handling
                    pass  

                c = None

        return c

    def key(self):
        return self._key

    def flush(self, view='default'):
        self._mutex.acquire()

        _view = self._views.get(view)
        if _view:
            _view.refresh()

        self._mutex.release()

    def update(self):
        for k, view in self._views.items():
            view.refresh()

    def clear_content(self):
        if self._active_content:
            view = self._views.get(self._active_content)
            if view:
                view.clear()
