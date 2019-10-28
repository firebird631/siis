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
import logging
import pathlib
import traceback

from datetime import datetime

from common.utils import UTC, fix_thread_set_name, TIMEFRAME_FROM_STR_MAP

from watcher.watcher import Watcher
from watcher.service import WatcherService

from trader.trader import Trader
from strategy.strategy import Strategy
from trader.service import TraderService
from strategy.service import StrategyService
from monitor.service import MonitorService
from monitor.desktopnotifier import DesktopNotifier
from common.watchdog import WatchdogService

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from terminal.terminal import Terminal
from terminal.command import CommandsHandler

from database.database import Database

from common.runnable import Runnable
from common.siislog import SiisLog

from view.service import ViewService

from app.help import display_cli_help, display_welcome
from app.setup import install
from app.generalcommands import register_general_commands
from app.tradingcommands import register_trading_commands
from app.regioncommands import register_region_commands


def signal_handler(sig, frame):
    if Terminal.inst():
        Terminal.inst().action('Tip command :q<ENTER> to exit !', view='status')


def setup_views(siis_logger, view_service, watcher_service, trader_service, strategy_service):
    pass
    # @todo
    # 'strategy'
    # 'stat'
    # 'perf'
    # 'trader'
    # 'account'
    # 'market'
    # 'ticker'


def terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service):
    if watcher_service:
        watcher_service.terminate()
    if trader_service:
        trader_service.terminate()
    if strategy_service:
        strategy_service.terminate()
    if monitor_service:
        monitor_service.terminate()
    if desktop_service:
        desktop_service.terminate()
    if view_service:
        view_service.terminate()
    if notifier_service:
        pass  # notifier_service.terminate()

    Database.terminate()

    if watchdog_service:
        watchdog_service.terminate()

def application(argv):
    fix_thread_set_name()

    # init terminal displayer
    Terminal()

    options = {
        'working-path': os.getcwd(),
        'identity': 'real',
        'config-path': './user/config',
        'log-path': './user/log',
        'reports-path': './user/reports',
        'markets-path': './user/markets',
        'log-name': 'siis.log',
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
                elif arg == '--optimize':
                    # use the optimizer
                    options['optimize'] = True
                elif arg == '--sync':
                    # use the syncer
                    options['sync'] = True
                elif arg == '--rebuild':
                    # use the rebuilder
                    options['rebuild'] = True

                elif arg == '--install-market':
                    options['install-market'] = True
                elif arg == '--initial-fetch':
                    # do the initial OHLC fetch for watchers
                    options['initial-fetch'] = True
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
                    # if backtest from date (if ommited use whoole data) date format is "yyyy-mm-dd-hh:mm:ss", fetch, binarize, optimize to date
                    options['from'] = datetime.strptime(arg.split('=')[1], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC())
                elif arg.startswith('--to='):
                    # if backtest to date (can be ommited), fetch, binarize, optimize to date
                    options['to'] = datetime.strptime(arg.split('=')[1], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC())
                elif arg.startswith('--last='):
                    # fetch the last n data history
                    options['last'] = int(arg.split('=')[1])

                elif arg.startswith('--market='):
                    # fetch, binarize, optimize the data history for this market
                    options['market'] = arg.split('=')[1]
                elif arg.startswith('--spec='):
                    # fetcher data history option
                    options['option'] = arg.split('=')[1]
                elif arg.startswith('--broker='):
                    # broker name for fetcher, watcher, optimize, binarize
                    options['broker'] = arg.split('=')[1]
                elif arg.startswith('--timeframe='):
                    # fetch, binarize, optimize base timeframe
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
            from tools.binarizer import do_binarizer
            do_binarizer(options)
        else:
            display_cli_help()

        sys.exit(0)

    #
    # fetcher mode
    #

    if options.get('fetch'):
        if options.get('market') and options.get('broker'):
            from tools.fetcher import do_fetcher
            do_fetcher(options)
        else:
            display_cli_help()

        sys.exit(0)

    #
    # optimizer mode
    #

    if options.get('optimize'):
        if options.get('market') and options.get('from') and options.get('to') and options.get('broker'):
            from tools.optimizer import do_optimizer
            do_optimizer(options)
        else:
            display_cli_help()

        sys.exit(0)

    #
    # syncer mode
    #

    if options.get('sync'):
        if options.get('market') and options.get('broker'):
            from tools.syncer import do_syncer
            do_syncer(options)
        else:
            display_cli_help()

        sys.exit(0)

    #
    # rebuilder mode
    #

    if options.get('rebuild'):
        if options.get('market') and options.get('from') and options.get('to') and options.get('broker') and options.get('timeframe'):
            from tools.rebuilder import do_rebuilder
            do_rebuilder(options)
        else:
            display_cli_help()

        sys.exit(0)

    #
    # normal mode
    #

    Terminal.inst().info("Starting SIIS using %s identity..." % options['identity'])
    Terminal.inst().action("- type ':q<Enter> or :quit<Enter>' to terminate")
    Terminal.inst().action("- type ':h<Enter> or :help<Enter>' to display help")
    Terminal.inst().flush()

    if options.get('backtesting'):  
        Terminal.inst().notice("Process a backtesting.")

    if options.get('paper-mode'):
        Terminal.inst().notice("- Using paper-mode trader.")
    else:
        Terminal.inst().notice("- Using live-mode trader.")

    signal.signal(signal.SIGINT, signal_handler)

    #
    # application
    #

    watchdog_service = WatchdogService(options)
    watchdog_service.start(options)

    # application services
    view_service = None
    notifier_service = None
    desktop_service = None
    watcher_service = None
    trader_service = None
    strategy_service = None

    # monitoring service
    Terminal.inst().info("Starting monitor service...")
    monitor_service = MonitorService(options)

    # desktop notifier (to be splitted in ViewService and in a DesktopNotifier managed by a NotifierService)
    try:    
        desktop_service = DesktopNotifier()
        # desktop_service.start(options)
        watchdog_service.add_service(desktop_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    # notifier service
    # notifier_service = NotifierService()
    # notifier_service.start() .. discord notifier... @todo
    try:
        view_service = ViewService()
        # view_service.start(options)
        watchdog_service.add_service(view_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    # database manager
    try:
        Database.create(options)
        Database.inst().setup(options)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    # watcher service
    Terminal.inst().info("Starting watcher's service...")
    try:
        watcher_service = WatcherService(options)
        watcher_service.start(options)
        watchdog_service.add_service(watcher_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    # trader service
    Terminal.inst().info("Starting trader's service...")
    try:
        trader_service = TraderService(watcher_service, monitor_service, options)
        trader_service.start(options)
        watchdog_service.add_service(trader_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    # want to display desktop notification and update views
    watcher_service.add_listener(desktop_service)
    watcher_service.add_listener(view_service)

    # want to display desktop notification and update views
    trader_service.add_listener(desktop_service)
    trader_service.add_listener(view_service)

    # trader service listen to watcher service and update views
    watcher_service.add_listener(trader_service)

    # strategy service
    Terminal.inst().info("Starting strategy's service...")
    try:
        strategy_service = StrategyService(watcher_service, trader_service, monitor_service, options)
        strategy_service.start(options)
        watchdog_service.add_service(strategy_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    # strategy service listen to watcher service
    watcher_service.add_listener(strategy_service)

    # strategy service listen to trader service
    trader_service.add_listener(strategy_service)

    # want to display desktop notification, update view and notify on discord
    # strategy_service.add_listener(notifier_service)
    # @todo add notifier service and replace desktop service as desktop notifier into this service same for discord...
    strategy_service.add_listener(desktop_service)
    strategy_service.add_listener(view_service)

    # for display stats (@todo move to views)
    desktop_service.strategy_service = strategy_service
    desktop_service.trader_service = trader_service

    # register terminal commands
    commands_handler = CommandsHandler()
    commands_handler.init(options)

    # cli commands registration
    register_general_commands(commands_handler)
    register_trading_commands(commands_handler, trader_service, strategy_service, monitor_service)
    register_region_commands(commands_handler, strategy_service)

    setup_views(siis_logger, view_service, watcher_service, trader_service, strategy_service)

    # setup and start the monitor service
    monitor_service.setup(watcher_service, trader_service, strategy_service)
    try:
        monitor_service.start()
        watchdog_service.add_service(monitor_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service, desktop_service, view_service, notifier_service)
        sys.exit(-1)

    Terminal.inst().message("Running main loop...")

    Terminal.inst().upgrade()
    Terminal.inst().message("Steady...", view='notice')

    display_welcome()

    LOOP_SLEEP = 0.016  # in second
    MAX_CMD_ALIVE = 15  # in second

    running = True

    value = None
    value_changed = False
    command_timeout = 0
    prev_timestamp = 0

    try:
        while running:
            # keyboard input commands
            try:
                c = Terminal.inst().read()
                key = Terminal.inst().key()

                if c:
                    # split the commande line
                    args = [arg for arg in (value[1:].split(' ') if value and value.startswith(':') else []) if arg]
                    if value and value[-1] == ' ':
                        args.append('')

                    # update the current type command
                    commands_handler.process_char(c, args)

                if key:
                    if key == 'KEY_ESCAPE':
                        # cancel command
                        value = None
                        value_changed = True
                        command_timeout = 0

                        # use command mode
                        Terminal.inst().set_mode(Terminal.MODE_DEFAULT)

                    # split the commande line
                    args = [arg for arg in (value[1:].split(' ') if value and value.startswith(':') else []) if arg]
                    if value and value[-1] == ' ':
                        args.append('')

                    # process on the arguments
                    args = commands_handler.process_key(key, args, Terminal.inst().mode == Terminal.MODE_COMMAND)

                    if args:
                        # regen the updated commande ligne
                        value = ":" + ' '.join(args)
                        value_changed = True
                        command_timeout = 0

                    desktop_service.on_key_pressed(key)

                # @todo move the rest to command_handler
                if c:
                    if value and value[0] == ':':
                        if c == '\b':
                            # backspace, erase last command char
                            value = value[:-1] if value else None
                            value_changed = True
                            command_timeout = time.time()

                        elif c != '\n':
                            # append to the advanced command value
                            value += c
                            value_changed = True
                            command_timeout = time.time()

                        elif c == '\n':
                            result = commands_handler.process_cli(value)
                            command_timeout = 0

                            if not result:
                                # maybe an application level command
                                if value == ':q' or value == ':quit':
                                    running = False

                                elif value.startswith(':x '):
                                    # manually exit position at market 
                                    # @todo move as command
                                    target = value[3:]

                                    if target == "all" or target == "ALL":
                                        Terminal.inst().action("Send close to market command for any positions", view='status')
                                        trader_service.command(Trader.COMMAND_CLOSE_ALL_MARKET, {})
                                    else:
                                        Terminal.inst().action("Send close to market command for position %s" % (target,), view='status')
                                        trader_service.command(Trader.COMMAND_CLOSE_MARKET, {'key': target})

                                elif value.startswith(':d '):
                                    # @deprecated manually duplicate a position entry or exit must be associated to social strategy
                                    # @todo move as command
                                    target = value[3:]

                                    Terminal.inst().action("Send replicate to market command for position %s" % (target,), view='status')
                                    trader_service.command(Trader.COMMAND_TRIGGER, {'key': target})

                            # clear command value
                            value_changed = True
                            value = None

                            # use default mode
                            Terminal.inst().set_mode(Terminal.MODE_DEFAULT)

                    elif c != '\n':
                        # initial command value
                        value = "" + c
                        value_changed = True
                        command_timeout = time.time()

                        if value and value[0] == ':':
                            # use command mode
                            Terminal.inst().set_mode(Terminal.MODE_COMMAND)

                    if value and value[0] != ':':
                        # direct key

                        # use default mode
                        Terminal.inst().set_mode(Terminal.MODE_DEFAULT)

                        try:
                            result = commands_handler.process_accelerator(key)

                            # @todo convert to Command object accelerator
                            if not result:
                                result = True

                                # @todo might be replaced by views                                
                                if value == 'p':
                                    trader_service.command(Trader.COMMAND_LIST_POSITIONS, {})
                                elif value == 'o':
                                    trader_service.command(Trader.COMMAND_LIST_ORDERS, {})
                                elif value == 'g':
                                    trader_service.command(Trader.COMMAND_SHOW_PERFORMANCE, {})

                                # display views

                                elif value == 'C':
                                    Terminal.inst().clear_content()
                                elif value == 'D':
                                    Terminal.inst().switch_view('debug')
                                elif value == 'I':
                                    Terminal.inst().switch_view('content')
                                elif value == 'F':
                                    Terminal.inst().switch_view('strategy')
                                elif value == 'S':
                                    Terminal.inst().switch_view('stats')
                                elif value == 'P':
                                    Terminal.inst().switch_view('perf')
                                elif value == 'T':
                                    Terminal.inst().switch_view('ticker')
                                elif value == 'A':
                                    Terminal.inst().switch_view('account')
                                elif value == 'M':
                                    Terminal.inst().switch_view('market')
                                elif value == 'Q':
                                    Terminal.inst().switch_view('asset')
                                elif value == 'N':
                                    Terminal.inst().switch_view('signal')

                                elif value == '?':
                                    # ping services and workers
                                    watchdog_service.ping(1.0)

                                elif value == ' ':
                                    # a simple mark on the terminal
                                    Terminal.inst().notice("Trading time %s" % (datetime.fromtimestamp(strategy_service.timestamp).strftime('%Y-%m-%d %H:%M:%S')), view='status')

                                elif value == 'a' and desktop_service:
                                    desktop_service.audible = not desktop_service.audible
                                    Terminal.inst().action("Audible notification are now %s" % ("actives" if desktop_service.audible else "disabled",), view='status')
                                elif value == 'n' and desktop_service:
                                    desktop_service.popups = not desktop_service.popups
                                    Terminal.inst().action("Desktop notification are now %s" % ("actives" if desktop_service.popups else "disabled",), view='status')
                                elif value == 'e' and desktop_service:
                                    desktop_service.discord = not desktop_service.discord
                                    Terminal.inst().action("Discord notification are now %s" % ("actives" if desktop_service.discord else "disabled",), view='status')

                                else:
                                    result = False

                            if result:
                                value = None
                                value_changed = True
                                command_timeout = 0

                        except Exception as e:
                            siis_logger.error(repr(e))
                            siis_logger.error(traceback.format_exc())

            except IOError:
                pass
            except Exception as e:
                siis_logger.error(repr(e))
                siis_logger.error(traceback.format_exc())

            # display advanced command only
            if value_changed:
                if value and value.startswith(':'):        
                    Terminal.inst().action("Command: %s" % value[1:], view='command')
                else:
                    Terminal.inst().message("", view='command')

            # clear input if no char hit during the last MAX_CMD_ALIVE
            if value and not value.startswith(':'):
                if (command_timeout > 0) and (time.time() - command_timeout >= MAX_CMD_ALIVE):
                    value = None
                    value_changed = True
                    Terminal.inst().info("Current typing canceled", view='status')

            try:
                # display strategy tarding time (update max once per second)
                if strategy_service.timestamp - prev_timestamp >= 1.0:
                    mode = "live"
                    if trader_service.backtesting:
                        mode = "backtesting"
                    elif trader_service.paper_mode:
                        mode = "paper-mode"

                    Terminal.inst().message("%s - %s" % (mode, datetime.fromtimestamp(strategy_service.timestamp).strftime('%Y-%m-%d %H:%M:%S')), view='notice')
                    prev_timestamp = strategy_service.timestamp

                # synchronous operations here
                watcher_service.sync()
                trader_service.sync()
                strategy_service.sync()

                if monitor_service:
                    monitor_service.sync()

                if desktop_service:
                    desktop_service.sync()

                if view_service:
                    view_service.sync()

                Terminal.inst().update()

            except BaseException as e:
                siis_logger.error(repr(e))
                siis_logger.error(traceback.format_exc())

            # don't waste CPU time on main thread
            time.sleep(LOOP_SLEEP)

    finally:
        Terminal.inst().restore_term()

    Terminal.inst().info("Terminate...")
    Terminal.inst().flush() 

    commands_handler.terminate(options) if commands_handler else None
    commands_handler = None

    # service terminate
    monitor_service.terminate() if monitor_service else None
    strategy_service.terminate() if strategy_service else None
    trader_service.terminate() if trader_service else None
    watcher_service.terminate() if watcher_service else None
    desktop_service.terminate() if desktop_service else None
    view_service.terminate() if view_service else None
    notifier_service.terminate() if notifier_service else None

    Terminal.inst().info("Saving database...")
    Terminal.inst().flush() 

    Database.terminate()

    watchdog_service.terminate() if watchdog_service else None

    Terminal.inst().info("Bye!")
    Terminal.inst().flush()

    Terminal.terminate()


if __name__ == "__main__":
    application(sys.argv)
