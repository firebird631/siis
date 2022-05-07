# @date 2019-01-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Monitoring client

import sys

import time
import json
import os
import pathlib
import logging
import traceback
import posix

from common.siislog import SiisLog
from terminal.terminal import Terminal
from charting.charting import Charting
from monitor.client.dispatcher import Dispatcher
from common.utils import fix_thread_set_name

sys.path.append('../..')


def display_help():
    pass


def has_exception(_logger, e):
    _logger.error(repr(e))
    _logger.error(traceback.format_exc())


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

    # init terminal display
    Terminal.inst()

    options = {
        'log-path': './user/log',
        'log-name': 'client.log'
    }

    # create initial siis data structure if necessary
    install(options)

    siis_log = SiisLog(options)
    logger = logging.getLogger('siis.client')
    stream = ""
    rpc = ""
    fifo = -1
    fifo_rpc = -1

    if len(sys.argv) > 1:
        stream = sys.argv[1]

    if len(sys.argv) > 2:
        rpc = sys.argv[2]

    if not stream:
        Terminal.inst().error("- Missing stream url !")

    if not rpc:
        Terminal.inst().error("- Missing RPC url !")

    try:
        fifo = os.open(stream, os.O_NONBLOCK | posix.O_RDONLY)
    except Exception as e:
        Terminal.inst().error(repr(e))

    if not fifo:
        Terminal.inst().error("- Cannot open the stream !")

    try:
        fifo_rpc = os.open(rpc, os.O_NONBLOCK | posix.O_WRONLY)
    except Exception as e:
        Terminal.inst().error(repr(e))

    if not fifo_rpc:
        Terminal.inst().error("- Cannot open the RPC fifo !")

    Terminal.inst().info("Starting SIIS simple chart client...")
    Terminal.inst().flush()

    try:
        Charting.inst().start()
    except Exception as e:
        has_exception(logger, e)

    dispatcher = Dispatcher()

    running = True

    Terminal.inst().message("Running main loop...")

    size = 32768
    buf = []
    content = ""
    cur = bytearray()

    if not Charting.inst().visible:
        if not Charting.inst().running:
            # charting service
            try:
                Charting.inst().start()
            except Exception as e:
                has_exception(logger, e)

        if Charting.inst().running:
            Charting.inst().show()
            Terminal.inst().action("Charting is now shown")

    while running:          
        # read from fifo
        try:
            buf = os.read(fifo, size)

            if buf:
                for n in buf:
                    if n == 10:  # new line as message termination
                        try:
                            msg = json.loads(cur.decode('utf8'))
                            dispatcher.on_message(msg)
                        except Exception as e:
                            logger.error(repr(e))

                        cur = bytearray()
                    else:
                        cur.append(n)

        except (BrokenPipeError, IOError):
            pass

        if not Charting.inst().has_charts():
            running = False

        time.sleep(0.01)

    # close message
    messages = dispatcher.close()

    if fifo:
        os.close(fifo)
        fifo = -1

    if fifo_rpc:
        for msg in messages:
            try:
                # write to fifo
                posix.write(fifo_rpc, (json.dumps(msg) + '\n').encode('utf8'))
            except (BrokenPipeError, IOError) as e:
                logger.error(repr(e))
            except (TypeError, ValueError) as e:
                logger.error("Error sending message : %s" % repr(e))

        # fifo_rpc.flush()
        # os.flush(fifo_rpc)

        os.close(fifo_rpc)
        fifo_rpc = -1

    Terminal.inst().info("Terminate...")
    Terminal.inst().flush()

    # terminate charting singleton
    Charting.terminate()

    Terminal.inst().info("Bye!")
    Terminal.inst().flush()

    Terminal.terminate()


if __name__ == "__main__":
    application(sys.argv)
