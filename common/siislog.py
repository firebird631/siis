# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Siis logger

import copy
import logging
# import colorama
# import curses

from logging.handlers import RotatingFileHandler
from terminal.terminal import Terminal


class ColoredFormatter(logging.Formatter):

    def __init__(self, fmt, use_color=True):
        logging.Formatter.__init__(self, fmt, datefmt='%H:%M:%S')
        self.use_color = use_color

    def colors(self, style):
        return {
            'DEFAULT': '\\0',
            'ERROR': '\\1',
            'WARNING': '\\2',
            'ACTION': '\\3',
            'NOTICE': '\\4',
            'HIGH': '\\5',
            'LOW': '\\6',
            'NEUTRAL': '\\7',
            'HIGHLIGHT': '\\8'
        }
        # if style == 'uterm':
        #     return {
        #         'DEFAULT': colorama.Style.RESET_ALL,
        #         'ERROR': colorama.Fore.RED,
        #         'WARNING': colorama.Back.YELLOW + colorama.Fore.WHITE,
        #         'ACTION': colorama.Fore.YELLOW,
        #         'NOTICE': colorama.Fore.CYAN,
        #         'HIGH': colorama.Fore.GREEN,
        #         'LOW': colorama.Fore.MAGENTA,
        #         'NEUTRAL':colorama.Fore.WHITE,
        #         'HIGHLIGHT': colorama.Style.BRIGHT
        #     }

    def format(self, record):
        colors = self.colors(Terminal.inst().style() if Terminal.inst() else "")

        if record.levelno in (logging.ERROR, logging.CRITICAL) and self.use_color:
            record.name = colors['ERROR'] + '- ' + copy.copy(record.name) + colors["DEFAULT"] + ' '
            record.levelname = colors['ERROR'] + copy.copy(record.levelname) + colors["DEFAULT"] + ' '
            record.msg = colors['ERROR'] + copy.copy(str(record.msg)) + colors["DEFAULT"]
            return logging.Formatter.format(self, record)

        elif record.levelno == logging.WARNING and self.use_color:
            record.name = colors["WARNING"] + '- ' + copy.copy(record.name) + colors["DEFAULT"] + ' '
            record.levelname = colors["WARNING"] + '- ' + copy.copy(record.levelname) + colors["DEFAULT"] + ' '
            record.msg = colors["WARNING"] + copy.copy(str(record.msg)) + colors["DEFAULT"]
            return logging.Formatter.format(self, record)

        elif record.levelno == logging.INFO and self.use_color:
            record.name = '- '
            record.levelname = colors["DEFAULT"] + '- ' + copy.copy(record.levelname) + colors["DEFAULT"] + ' '
            record.msg = colors["DEFAULT"] + copy.copy(str(record.msg)) + colors["DEFAULT"]
            return logging.Formatter.format(self, record)

        elif record.levelno == logging.DEBUG and self.use_color:
            record.name = colors["NOTICE"] + '- ' + copy.copy(record.name) + colors["DEFAULT"] + ' '
            record.levelname = colors["NOTICE"] + '- ' + copy.copy(record.levelname) + colors["DEFAULT"] + ' '
            record.msg = colors["NOTICE"] + copy.copy(str(record.msg)) + colors["DEFAULT"]
            return logging.Formatter.format(self, record)

        else:
            return logging.Formatter.format(self, record)


class TerminalHandler(logging.StreamHandler):

    def __init__(self):
        logging.StreamHandler.__init__(self)

    def filter(self, record):
        if (record.pathname.startswith('siis.exec.') or record.pathname.startswith('siis.signal.') or
                record.pathname.startswith('siis.order.') or record.pathname.startswith('siis.traceback.')):
            # this only goes to loggers, not to stdout
            return False

        return True

    def emit(self, record):
        msg = self.format(record)

        if record.levelno == logging.CRITICAL:
            if record.pathname.startswith('siis.error.'):
                Terminal.inst().error(str(msg), view='content') if Terminal.inst() else print(str(msg))
            else:
                Terminal.inst().error(str(msg), view='content') if Terminal.inst() else print(str(msg))

        elif record.levelno == logging.ERROR:
            if record.pathname.startswith('siis.error.'):
                Terminal.inst().error(str(msg), view='debug') if Terminal.inst() else print(str(msg))
            else:
                Terminal.inst().error(str(msg), view='content') if Terminal.inst() else print(str(msg))

        elif record.levelno == logging.WARNING:
            if record.pathname.startswith('siis.error.'):
                Terminal.inst().error(str(msg), view='debug') if Terminal.inst() else print(str(msg))
            else:
                Terminal.inst().warning(str(msg), view='content') if Terminal.inst() else print(str(msg))

        elif record.levelno == logging.INFO:
            if record.pathname.startswith('siis.error.'):
                Terminal.inst().message(str(msg), view='debug') if Terminal.inst() else print(str(msg))
            else:
                Terminal.inst().message(str(msg), view='content') if Terminal.inst() else print(str(msg))

        elif record.levelno == logging.DEBUG:
            Terminal.inst().message(str(msg), view='debug') if Terminal.inst() else print(str(msg))

        else:
            Terminal.inst().message(str(msg), view='default') if Terminal.inst() else print(str(msg))


# register the color formatter
logging.ColoredFormatter = ColoredFormatter


class SiisLog(object):
    """
    Siis logger initialized based on python logger.
    """

    def __init__(self, options, style=''):
        # if init before terminal
        # colorama.init()

        # stderr to terminal in info level
        self.console = TerminalHandler()  #  logging.StreamHandler()
        self.console.setLevel(logging.DEBUG)

        # self.term_formatter = logging.Formatter('- %(name)-12s: %(levelname)-8s %(message)s')
        self.term_formatter = ColoredFormatter('%(asctime)s %(name)-s%(message)s', True)
        self.console.setFormatter(self.term_formatter)

        # add the handler to the root logger
        logging.getLogger('').addHandler(self.console)

        # default log file formatter
        self.file_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        # a siis logger with siis.log
        self.file_logger = RotatingFileHandler(options['log-path'] + '/' + options['log-name'],
                                               maxBytes=1024*1024, backupCount=5)
        # self.file_logger = logging.FileHandler(options['log-path'] + '/' + options['log-name'])
        self.file_logger.setFormatter(self.file_formatter)
        self.file_logger.setLevel(logging.DEBUG)

        self.add_file_logger('siis', self.file_logger)

        # a siis logger with exec.siis.log
        # self.exec_file_logger = logging.FileHandler(options['log-path'] + '/' + "exec." + options['log-name'])
        self.exec_file_logger = RotatingFileHandler(options['log-path'] + '/' + "exec." + options['log-name'],
                                                    maxBytes=1024*1024, backupCount=5)
        self.exec_file_logger.setFormatter(self.file_formatter)
        self.exec_file_logger.setLevel(logging.INFO)

        # don't propagate execution to siis logger
        self.add_file_logger('siis.exec', self.exec_file_logger, False)

        # a siis logger with error.siis.log
        # self.error_file_logger = logging.FileHandler(options['log-path'] + '/' + "error." + options['log-name'])
        self.error_file_logger = RotatingFileHandler(options['log-path'] + '/' + "error." + options['log-name'],
                                                     maxBytes=1024*1024, backupCount=5)
        self.error_file_logger.setFormatter(self.file_formatter)
        self.error_file_logger.setLevel(logging.INFO)

        # don't propagate error trade to siis logger
        self.add_file_logger('siis.error', self.error_file_logger, False)

        # a siis logger with signal.siis.log
        # self.signal_file_logger = logging.FileHandler(options['log-path'] + '/' + "signal." + options['log-name'])
        self.signal_file_logger = RotatingFileHandler(options['log-path'] + '/' + "signal." + options['log-name'],
                                                      maxBytes=1024*1024, backupCount=5)
        self.signal_file_logger.setFormatter(self.file_formatter)
        self.signal_file_logger.setLevel(logging.INFO)

        # don't propagate signal trade to siis logger
        self.add_file_logger('siis.signal', self.signal_file_logger, False)

        # a siis logger with order.siis.log
        # self.order_file_logger = logging.FileHandler(options['log-path'] + '/' + "order." + options['log-name'])
        self.order_file_logger = RotatingFileHandler(options['log-path'] + '/' + "order." + options['log-name'],
                                                     maxBytes=1024*1024, backupCount=5)
        self.order_file_logger.setFormatter(self.file_formatter)
        self.order_file_logger.setLevel(logging.INFO)

        # don't propagate signal trade to siis logger
        self.add_file_logger('siis.order', self.order_file_logger, False)

        # a siis logger with traceback.siis.log
        # self.traceback_file_logger = logging.FileHandler(options['log-path'] + '/' + "traceback." + options['log-name'])
        self.traceback_file_logger = RotatingFileHandler(options['log-path'] + '/' + "traceback." + options['log-name'],
                                                         maxBytes=1024*1024, backupCount=5)
        self.traceback_file_logger.setFormatter(self.file_formatter)
        self.traceback_file_logger.setLevel(logging.INFO)

        # don't propagate traceback to siis logger
        self.add_file_logger('siis.traceback', self.traceback_file_logger, False)

    def add_file_logger(self, name, handler, level=logging.DEBUG, propagate=True):
        my_logger = logging.getLogger(name)

        my_logger.addHandler(handler)
        my_logger.setLevel(level)
        my_logger.propagate = propagate

        return my_logger
