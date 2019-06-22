# @date 2019-01-01
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Monitoring client

from __init__ import APP_VERSION, APP_SHORT_NAME, APP_LONG_NAME

import sys
sys.path.append('../..')

import time
import json
import termios, fcntl, os
import signal
import pathlib
import logging
import traceback

from common.siislog import SiisLog
from terminal.terminal import Terminal
from charting.charting import Charting
from monitor.client.dispatcher import Dispatcher
from common.utils import fix_thread_set_name


def display_help():
    pass

def signal_handler(sig, frame):
    Terminal.inst().action('> Press q to exit !')

def has_exception(e):
    siis_logger.error(repr(e))
    siis_logger.error(traceback.format_exc())

def install(options):
    config_path = "./"
    data_path = "./"

    home = pathlib.Path.home()
    if home.exists():
        if sys.platform == "linux":
            config_path = pathlib.Path(home, '.siis', 'config')
            log_path = pathlib.Path(home, '.siis', 'log')
        elif sys.platform == "windows":
            app_data = os.getenv('APPDATA')

            config_path = pathlib.Path(home, app_data, 'siis', 'config')
            log_path = pathlib.Path(home, app_data, 'siis', 'log')
        else:
            config_path = pathlib.Path(home, '.siis', 'config')
            log_path = pathlib.Path(home, '.siis', 'log')
    else:
        # uses cwd
        home = pathlib.Path(os.getcwd())

        config_path = pathlib.Path(home, 'user', 'config')
        log_path = pathlib.Path(home, 'user', 'log')

    # config/
    if not config_path.exists():
        config_path.mkdir(parents=True)

    options['config-path'] = str(config_path)

    # log/
    if not log_path.exists():
        log_path.mkdir(parents=True)

    options['log-path'] = str(log_path)


def application(argv):
    fix_thread_set_name()

    # init terminal displayer
    Terminal()

    options = {
        'log-path': './user/log',
        'log-name': 'client.log'
    }

    # create initial siis data structure if necessary
    install(options)

    siis_log = SiisLog(options)
    siis_logger = logging.getLogger('client')
    stream = ""
    fifo = -1

    if len(sys.argv) > 1:
        stream = sys.argv[1]

    if not stream:
        Terminal.inst().error("- Missing stream url !")

    try:
        fifo = os.open(stream, os.O_NONBLOCK + os.O_RDONLY)
    except Exception as e:
        Terminal.inst().error(repr(e))

    if not fifo:
        Terminal.inst().error("- Cannot open the stream !")

    Terminal.inst().info("Starting SIIS monitor...")
    Terminal.inst().action("- (Press 'q' twice to terminate)")
    Terminal.inst().action("- (Press 'h' for help)")
    Terminal.inst().flush()

    signal.signal(signal.SIGINT, signal_handler)
    # signal.pause()
    # install key grabber
    fd = sys.stdin.fileno()

    oldterm = termios.tcgetattr(fd)
    newattr = termios.tcgetattr(fd)
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, newattr)

    oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

    try:
        Charting.inst().start()
    except Exception as e:
        has_exception(e)

    dispatcher = Dispatcher()

    running = True

    Terminal.inst().message("Running main loop...")

    TIMER_TICK_FREQ_SEC = 0.005
    value = None
    key_counter = 0

    size = 32768
    buf = []*size
    content = ""
    cur = bytearray()

    if not Charting.inst().visible:
        if not Charting.inst().running:
            # charting service
            try:
                Charting.inst().start()
            except Exception as e:
                has_exception(e)

        if Charting.inst().running:
            Charting.inst().show()
            Terminal.inst().action("Charting is now shown")

    try:
        while running:
            # keyboard input commands
            try:
                c = sys.stdin.read(1)

                if c:
                    if c == '\b':
                        value = None

                    elif c == '\n' and value:
                        # validated commands
                        if c.startswith('s'):
                            key = c[1:]
                            # @todo subscribe
                        elif c.startswith('u'):
                            key = c[1:]
                            # @todo unsubscribe

                        value = None

                    elif value and len(value) > 0:
                        value += c

                    else:
                        value = "" + c

                    # direct commands

                    if value == '+':
                        value = None
                        # @todo next strategy chart

                    elif value == '-':
                        value = None
                        # @todo previous strategy chart

                    if value == 'r':
                        value = None
                        # @todo list strategies

                    elif value == 'm':
                        value = None
                        # @todo list strategies markets

                    elif value == 'd':
                        value = None

                        if not Charting.inst().visible:
                            if not Charting.inst().running:
                                # charting service
                                try:
                                    Charting.inst().start()
                                except Exception as e:
                                    has_exception(e)

                            if Charting.inst().running:
                                Charting.inst().show()
                                Terminal.inst().action("Charting is now shown")
                        else:
                            Charting.inst().hide()
                            Terminal.inst().action("Charting is now hidden")

                    if value == 'h':
                        value = None
                        display_help()

                    if value == 'q':
                        Terminal.inst().notice("Press another time 'q' to confirm exit")

                    if value == 'qq':
                        running = False

                    key_counter = 0

            except IOError:
                pass
            
            # read from fifo
            try:
                buf = os.read(fifo, size)

                if buf:
                    for n in buf:
                        if n == 10:
                            try:
                                msg = json.loads(cur.decode('utf8'))
                                dispatcher.on_message(msg)
                            except Exception as e:
                                siis_logger.error(repr(e))

                            cur = bytearray()
                        else:
                            cur.append(n)

            except (BrokenPipeError, IOError):
                pass

            key_counter += 1

            time.sleep(TIMER_TICK_FREQ_SEC)

            # 15 sec clear input
            if key_counter >= 1 * 200: # / TIMER_TICK_FREQ_SEC:
                key_counter = 0

                if value is not None:
                    value = None
                    Terminal.inst().info("Current typing canceled")

    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

    if fifo:
        os.close(fifo)
        fifo = -1

    Terminal.inst().info("Terminate...")
    Terminal.inst().flush()

    # terminate charting singleton
    Charting.terminate()

    Terminal.inst().info("Bye!")
    Terminal.inst().flush()

    Terminal.terminate()

if __name__ == "__main__":
    application(sys.argv)
