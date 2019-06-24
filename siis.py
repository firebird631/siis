# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Siis standard implementation of the application (application main)

from __init__ import APP_VERSION, APP_SHORT_NAME, APP_LONG_NAME

import signal
import threading
import sys
import os
import time
import datetime
import logging
import pathlib
import traceback

from common.utils import UTC, fix_thread_set_name, TIMEFRAME_FROM_STR_MAP

from watcher.watcher import Watcher
from watcher.service import WatcherService

from trader.trader import Trader
from strategy.strategy import Strategy
from trader.service import TraderService
from strategy.service import StrategyService
from monitor.service import MonitorService
from monitor.desktopnotifier import DesktopNotifier

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from terminal.terminal import Terminal
from terminal.command import CommandsHandler

from database.database import Database

from common.runnable import Runnable
from common.siislog import SiisLog

from app.help import display_cli_help, display_welcome
from app.setup import install
from app.generalcommands import register_general_commands
from app.tradingcommands import register_trading_commands


def signal_handler(sig, frame):
    # Terminal.inst().action('Exit signal Ctrl+C pressed !', view='status')
    Terminal.inst().action('Tip command :q<ENTER> to exit !', view='status')
    # sys.exit(0)


def has_exception(siis_logger, e):
    siis_logger.error(repr(e))
    siis_logger.error(traceback.format_exc())


def do_binarizer(options, siis_logger):
    from database.tickstorage import TextToBinary

    Terminal.inst().info("Starting SIIS binarizer...")
    Terminal.inst().flush()

    timeframe = -1

    if not options.get('timeframe'):
        timeframe = 60  # default to 1min
    else:
        if options['timeframe'] in TIMEFRAME_FROM_STR_MAP:
            timeframe = TIMEFRAME_FROM_STR_MAP[options['timeframe']]
        else:
            try:
                timeframe = int(options['timeframe'])
            except:
                pass

    if timeframe < 0:
        siis_logger.error("Invalid timeframe !")
        sys.exit(-1)

    converter = TextToBinary(options['markets-path'], options['broker'], options['market'], options.get('from'), options.get('to'))
    converter.process()

    Terminal.inst().info("Binarization done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)


def do_fetcher(options, siis_logger):
    Terminal.inst().info("Starting SIIS fetcher using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    watcher_service = WatcherService(options)
    fetcher = watcher_service.create_fetcher(options['broker'])

    timeframe = -1
    cascaded = None

    if not options.get('timeframe'):
        timeframe = 60  # default to 1min
    else:
        if options['timeframe'] in TIMEFRAME_FROM_STR_MAP:
            timeframe = TIMEFRAME_FROM_STR_MAP[options['timeframe']]
        else:
            try:
                timeframe = int(options['timeframe'])
            except:
                pass

    if not options.get('cascaded'):
        cascaded = None
    else:
        if options['cascaded'] in TIMEFRAME_FROM_STR_MAP:
            cascaded = TIMEFRAME_FROM_STR_MAP[options['cascaded']]
        else:
            try:
                cascaded = int(options['cascaded'])
            except:
                pass

    if timeframe < 0:
        siis_logger.error("Invalid timeframe")
        sys.exit(-1)

    try:
        fetcher.connect()
    except:
        sys.exit(-1)

    if fetcher.connected:
        siis_logger.info("Fetcher authentified to %s, trying to collect data..." % fetcher.name)

        markets = fetcher.matching_symbols_set(options['market'].split(','), fetcher.available_instruments())

        try:
            for market_id in markets:
                if not fetcher.has_instrument(market_id, options.get('spec')):
                    siis_logger.error("Market %s not found !" % (market_id,))
                else:
                    fetcher.fetch_and_generate(market_id, timeframe,
                        options.get('from'), options.get('to'), options.get('last'),
                        options.get('spec'), cascaded)
        except KeyboardInterrupt:
            pass
        finally:
            fetcher.disconnect()

    fetcher = None

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Fetch done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)

def application(argv):
    fix_thread_set_name()

    # init terminal displayer
    Terminal()

    options = {
        'identity': 'real',
        'config-path': './user/config',
        'log-path': './user/log',
        'reports-path': './user/reports',
        'markets-path': './user/markets',
        'log-name': 'siis.log'
    }

    # create initial siis data structure if necessary
    install(options)

    siis_log = SiisLog(options, Terminal().inst().style())
    siis_logger = logging.getLogger('siis')

    # parse process command line
    if len(argv) > 1:
        options['livemode'] = True

        # utc or local datetime ?
        for arg in argv:
            if arg.startswith('--'):
                if arg == '--paper-mode':
                    # livemode but in paper-mode
                    options['paper-mode'] = True            
                elif arg == '--fetch':
                    # use the fetcher
                    options['fetch'] = True
                elif arg == '--binarize':
                    # use the binarizer
                    options['binarize'] = True

                elif arg == '--backtest':
                    # backtest mean always paper-mode
                    options['paper-mode'] = True
                    options['backtesting'] = True
                elif arg.startswith('--timestep='):
                    # backesting timestep, default is 60 second
                    options['timestep'] = float(arg.split('=')[1])
                elif arg.startswith('--time-factor='):
                    # backtesting time-factor
                    options['time-factor'] = float(arg.split('=')[1])

                elif arg.startswith('--from='):
                    # if backtest from date (if ommited use whoole data) date format is "yyyy-mm-dd-hh:mm:ss", fetch, binarize to date
                    options['from'] = datetime.datetime.strptime(arg.split('=')[1], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC())
                elif arg.startswith('--to='):
                    # if backtest to date (can be ommited), fetch, binarize to date
                    options['to'] = datetime.datetime.strptime(arg.split('=')[1], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC())
                elif arg.startswith('--last='):
                    # fetch the last n data history
                    options['last'] = int(arg.split('=')[1])

                elif arg.startswith('--market='):
                    # fetch, binarize the data history for this market
                    options['market'] = arg.split('=')[1]
                elif arg.startswith('--spec='):
                    # fetcher data history option
                    options['option'] = arg.split('=')[1]
                elif arg.startswith('--broker='):
                    # fetch the data history from this broker name (fetcher, watcher)
                    options['broker'] = arg.split('=')[1]
                elif arg.startswith('--timeframe='):
                    # fetch, binarize base timeframe
                    options['timeframe'] = arg.split('=')[1]
                elif arg.startswith('--cascaded='):
                    # fetch cascaded ohlc generation
                    options['cascaded'] = arg.split('=')[1]

                elif arg == '--watcher-only':
                    # feed only with live data (not compatible with --read-only)
                    options['watcher-only'] = True
                
                elif arg == '--read-only':
                    # does not write to the database (not compatible with --watcher-only)
                    options['read-only'] = True
                elif arg == '--check-data':
                    # check DB ohlc data (@todo)
                    options['check-data'] = True

                elif arg.startswith('--profile='):
                    # appliances profile name
                    options['profile'] = arg.split('=')[1]

                elif arg == '--version':
                    Terminal.inst().info('%s %s' % (APP_SHORT_NAME, '.'.join([str(x) for x in APP_VERSION])))
                    sys.exit(0)

                elif arg == '--help' or '-h':
                    display_cli_help()
                    sys.exit(0)
            else:
                options['identity'] = argv[1]

        # watcher-only read-only mutual exclusion
        if options.get('watcher-only') and options.get('read-only'):
            Terminal.inst().error("Options --watcher-only and --read-only are mutually exclusive !")
            sys.exit(-1)

        # backtesting
        if options.get('backtesting', False):
            if options.get('from') is None or options.get('to') is None:
                del options['backtesting']
                Terminal.inst().error("Backtesting need from= and to= date time")
                sys.exit(-1)

    if options['identity'].startswith('-'):
        Terminal.inst().error("First option must be the identity name")

    #
    # binarizer mode
    #

    if options.get('binarize'):
        if options.get('market') and options.get('from') and options.get('to') and options.get('broker'):
            do_binarizer(options, siis_logger)
        else:
            display_cmd_line_help()

        sys.exit(0)

    #
    # fetcher mode
    #

    if options.get('fetch'):
        if options.get('market') and options.get('broker') and options.get('timeframe'):
            do_fetcher(options, siis_logger)
        else:
            display_cmd_line_help()

        sys.exit(0)

    #
    # normal mode
    #

    Terminal.inst().info("Starting SIIS using %s identity..." % options['identity'])
    Terminal.inst().action("- (Press 'q' twice to terminate)")
    Terminal.inst().action("- (Press 'h' for help)")
    Terminal.inst().flush()

    if options.get('backtesting'):  
        Terminal.inst().notice("Process a backtesting.")

    if options.get('paper-mode'):
        Terminal.inst().notice("- Using paper-mode trader.")
    else:
        Terminal.inst().notice("- Using live-mode trader.")

    signal.signal(signal.SIGINT, signal_handler)

    # monitoring service
    Terminal.inst().info("Starting monitor service...")
    monitor_service = MonitorService(options)
    monitor_service.start()

    # desktop notifier (@todo move as handler of the monitor service)
    desktop_service = DesktopNotifier()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # watcher service
    Terminal.inst().info("Starting watcher's service...")
    watcher_service = WatcherService(options)
    watcher_service.start()

    # trader service
    Terminal.inst().info("Starting trader's service...")
    trader_service = TraderService(watcher_service, monitor_service, options)
    trader_service.start()

    # want to display desktop notification
    watcher_service.add_listener(desktop_service)

    # want to display desktop notification
    trader_service.add_listener(desktop_service)

    # trader service listen to watcher service
    watcher_service.add_listener(trader_service)

    # strategy service
    Terminal.inst().info("Starting strategy's service...")
    strategy_service = StrategyService(watcher_service, trader_service, monitor_service, options)
    strategy_service.start()

    # strategy service listen to watcher service
    watcher_service.add_listener(strategy_service)

    # strategy service listen to trader service
    trader_service.add_listener(strategy_service)

    # want to display desktop notification
    strategy_service.add_listener(desktop_service)

    # for display stats
    desktop_service.strategy_service = strategy_service

    # register terminal commands
    commands_handler = CommandsHandler()
    commands_handler.init(options)

    register_general_commands(commands_handler)
    register_trading_commands(commands_handler, watcher_service, trader_service, strategy_service)

    Terminal.inst().message("Running main loop...")

    Terminal.inst().upgrade()
    Terminal.inst().message("Steady...", view='notice')

    display_welcome()

    LOOP_SLEEP = 0.016  # in second
    MAX_CMD_ALIVE = 15  # in second

    running = True

    value = None
    command_timeout = 0

    try:
        while running:
            # keyboard input commands
            try:
                c = Terminal.inst().read()
                key = Terminal.inst().key()

                if key:
                    if key == 'KEY_ESCAPE':
                        # cancel command
                        value = None
                        command_timeout = 0

                    # split the commande line
                    args = value[1:].split(' ') if value and value.startswith(':') else []

                    # process on the arguments
                    args = commands_handler.process_key(key, args)

                    if args:
                        # regen the updated commande ligne
                        value = ":" + ' '.join(args)

                # @todo move the rest to command_handler
                if c:
                    if value and value[0] == ':':                       
                        if c == '\b':
                            # backspace, erase last command char
                            value = value[:-1] if value else None
                            command_timeout = time.time()

                        elif c != '\n':
                            # append to the advanced command value
                            value += c
                            command_timeout = time.time()

                        elif c == '\n':
                            result = commands_handler.process_cli(value)
                            command_timeout = 0

                            if not result:
                                # maybe an application level command
                                if value == ':q' or value == ':quit':
                                    running = False

                                elif value.startswith(':x '):
                                    # @todo move as command
                                    # manually exit position at market
                                    value = value[2:]

                                    if value == "all" or value == "ALL":
                                        Terminal.inst().action("Send close to market command for any positions", view='status')
                                        trader_service.command(Trader.COMMAND_CLOSE_ALL_MARKET, {})
                                    else:
                                        Terminal.inst().action("Send close to market command for position %s" % (value,), view='status')
                                        trader_service.command(Trader.COMMAND_CLOSE_MARKET, {'key': value})

                                elif value.startswith(':d '):
                                    # @deprecated manually duplicate a position entry or exit must be associated to social strategy
                                    # @todo move as command
                                    value = value[2:]

                                    Terminal.inst().action("Send replicate to market command for position %s" % (value,), view='status')
                                    trader_service.command(Trader.COMMAND_TRIGGER, {'key': value})

                                else:
                                    # unsupported command
                                    value = value[1:]
                                    Terminal.inst().action("Unsupported command %s" % (value,), view='status')

                            # clear command value
                            value = None

                    elif c != '\n':
                        # initial command value
                        value = "" + c
                        command_timeout = time.time()

                    if value and value[0] != ':':
                        # direct key
                        try:
                            commands_handler.process_accelerator(key)
                            command_timeout = 0

                            # @todo convert to Command object accelerator
                            if value == 'p':
                                value = None
                                trader_service.command(Trader.COMMAND_LIST_POSITIONS, {})
                            elif value == 'b':
                                value = None
                                trader_service.command(Trader.COMMAND_LIST_ASSETS, {})
                            elif value == 'm':
                                value = None
                                trader_service.command(Trader.COMMAND_LIST_MARKETS, {})
                            elif value == 't':
                                value = None
                                trader_service.command(Trader.COMMAND_LIST_TICKERS, {})                            
                            elif value == 'c':
                                value = None
                                trader_service.command(Trader.COMMAND_DISPLAY_ACCOUNT, {})
                            elif value == 'o':
                                value = None
                                trader_service.command(Trader.COMMAND_LIST_ORDERS, {})
                            elif value == 'g':
                                value = None
                                trader_service.command(Trader.COMMAND_SHOW_PERFORMANCE, {})
                            elif value == 'f':
                                value = None
                                strategy_service.command(Strategy.COMMAND_SHOW_STATS, {})
                            elif value == 's':
                                value = None
                                strategy_service.command(Strategy.COMMAND_SHOW_HISTORY, {})
                            elif value == 'w':
                                value = None
                                # trader_service.command(Trader.COMMAND_LIST_WATCHED, {})

                            #
                            # display view
                            #

                            if value == 'C':
                                value = None
                                Terminal.inst().clear_content()
                            elif value == 'F':
                                value = None
                                Terminal.inst().switch_view('strategy')
                            elif value == 'S':
                                value = None
                                Terminal.inst().switch_view('stats')
                            elif value == 'P':
                                value = None
                                Terminal.inst().switch_view('perf')
                            elif value == 'T':
                                value = None
                                Terminal.inst().switch_view('trader')
                            elif value == 'D':
                                value = None
                                Terminal.inst().switch_view('debug')
                            elif value == 'I':
                                value = None
                                Terminal.inst().switch_view('content')
                            elif value == 'A':
                                value = None
                                Terminal.inst().switch_view('account')
                            elif value == 'M':
                                value = None
                                Terminal.inst().switch_view('market')
                            elif value == 'X':
                                value = None
                                Terminal.inst().switch_view('ticker')

                            elif value == '?':
                                # ping services and workers
                                value = None
                                watcher_service.ping()
                                trader_service.ping()
                                strategy_service.ping()
                                monitor_service.ping()

                            elif value == ' ':
                                # a simple mark on the terminal
                                value = None
                                Terminal.inst().notice("Trading time %s" % (datetime.datetime.fromtimestamp(strategy_service.timestamp).strftime('%Y-%m-%d %H:%M:%S')), view='status')

                            #
                            # notifier opts
                            #

                            elif value == 'a':
                                value = None
                                desktop_service.audible = not desktop_service.audible

                                if desktop_service.audible:
                                    Terminal.inst().action("Audible notification are now actives", view='status')
                                else:
                                    Terminal.inst().action("Audible notification are now disabled", view='status')

                            elif value == 'n':
                                value = None
                                desktop_service.popups = not desktop_service.popups

                                if desktop_service.popups:
                                    Terminal.inst().action("Desktop notification are now actives", view='status')
                                else:
                                    Terminal.inst().action("Desktop notification are now disabled", view='status')

                            elif value == 'e':
                                value = None
                                desktop_service.discord = not desktop_service.discord

                                if desktop_service.discord:
                                    Terminal.inst().action("Discord notification are now actives", view='status')
                                else:
                                    Terminal.inst().action("Discord notification are now disabled", view='status')

                        except Exception as e:
                            has_exception(siis_logger, e)

                key = Terminal.inst().key()
                if key:
                    try:
                        # todo improve could have event, or just a wrapper on the further desktop service
                        if key == 'KEY_PPAGE':
                            desktop_service.prev_item()
                        elif key == 'KEY_NPAGE':
                            desktop_service.next_item()
                    except Exception as e:
                        has_exception(siis_logger, e)

            except IOError:
                pass
            except Exception as e:
                has_exception(siis_logger, e)

            try:
                Terminal.inst().message(datetime.datetime.fromtimestamp(strategy_service.timestamp).strftime('%Y-%m-%d %H:%M:%S'), view='notice')

                # synchronous operations here
                watcher_service.sync()
                trader_service.sync()
                strategy_service.sync()
                monitor_service.sync()
                desktop_service.sync()
                Terminal.inst().update()

            except BaseException as e:
                siis_logger.error(traceback.format_exc())
                Terminal.inst().error(repr(e))

            # don't waste CPU time on main thread
            # but seems not necessary, and could only wait the rest or a quantil
            # time.sleep(LOOP_SLEEP)

            if value and value.startswith(':'):
                # display advanced command only
                Terminal.inst().action("Command: %s" % value[1:], view='command')
            else:
                # nothing else to display
                Terminal.inst().message("", view='command')

            # clear input if no char presseding during the last MAX_CMD_ALIVE seconds
            if (command_timeout > 0) and (time.time() - command_timeout >= MAX_CMD_ALIVE):
                if value is not None:
                    value = None
                    Terminal.inst().info("Current typing canceled", view='status')

    finally:
        Terminal.inst().restore_term()

    Terminal.inst().info("Terminate...")
    Terminal.inst().flush() 

    commands_handler.terminate(options)
    commands_handler = None

    # service terminate
    monitor_service.terminate()
    strategy_service.terminate()
    trader_service.terminate()
    watcher_service.terminate()
    desktop_service.terminate()

    Terminal.inst().info("Saving database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Bye!")
    Terminal.inst().flush()

    Terminal.terminate()


if __name__ == "__main__":
    application(sys.argv)
