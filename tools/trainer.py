# @date 2023-04-114
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Machine Learning / Trainer tools
import base64
import subprocess
import uuid
from datetime import datetime

from config import utils
from tools.tool import Tool

from terminal.terminal import Terminal
from database.database import Database

from watcher.service import WatcherService

import logging
logger = logging.getLogger('siis.tools.trainer')
error_logger = logging.getLogger('siis.tools.error.trainer')


class Trainer(Tool):
    """
    Intercept training/machine learning demands and manage sub-process for backtesting, optimizing and finally
    output results for the caller.
    """

    @classmethod
    def alias(cls):
        return "train"

    @classmethod
    def help(cls):
        return ("Process a training for a specific strategy.",
                "Specify --profile, --learning, --from, --to, --timeframe",
                "Optional --initial-fetch to fetch data before training")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("trainer", options)

        self._watcher_service = None

        self._profile = None
        self._learning = None

        self._profile_config = None
        self._learning_config = None

    def check_options(self, options):
        if not options.get('profile'):
            Terminal.inst().error("Missing strategy profile")
            return False

        if not options.get('learning'):
            Terminal.inst().error("Missing strategy learning proxy file")
            return False

        if not options.get('from'):
            Terminal.inst().error("Missing from datetime parameters")
            return False

        if not options.get('to'):
            Terminal.inst().error("Missing to datetime parameters")
            return False

        if not options.get('timeframe'):
            Terminal.inst().error("Missing backtest timeframe parameters")
            return False

        Terminal.inst().message("Import profile...")

        self._profile_config = utils.load_config(options, "profiles/%s" % options['profile'])
        if not self._profile_config:
            Terminal.inst().error("Miss-configured strategy profile file")
            return False

        Terminal.inst().message("Import learning...")

        self._learning_config = utils.load_learning(options, options['learning'])
        if not self._profile_config:
            Terminal.inst().error("Miss-configured learning proxy file")
            return False

        self._profile = options['profile']
        self._learning = options['learning']

        return True

    def init(self, options):
        # database manager
        Database.create(options)
        Database.inst().setup(options)

        # want speedup the database inserts
        Database.inst().enable_fetch_mode()

        return True

    def run(self, options):
        if 'initial-fetch' in options:
            Terminal.inst().info("Starting watcher's service...")
            self._watcher_service = WatcherService(None, options)

            watchers_config = self._profile_config.get('watchers', {})

            for watcher_name, watcher_config in watchers_config.items():
                markets = watcher_config.get('symbols', [])

                Terminal.inst().info("Create watcher %s to fetch initial markets data..." % watcher_name)
                watcher = self._watcher_service.create_watcher(options, watcher_name, markets)
                if watcher:
                    watcher.initial_fetch = True

                    watcher.connect()

                    markets = watcher.matching_symbols_set(markets, watcher.available_instruments())

                    for market_id in markets:
                        Terminal.inst().info("Fetch data for market %s..." % market_id)
                        watcher._watched_instruments.add(market_id)

                        try:
                            watcher.update_markets_info()
                            # @todo prefetch
                        except Exception as e:
                            error_logger.error(str(e))

                    watcher.disconnect()

        #
        # options for trainer
        #

        from_dt = options.get('from')
        to_dt = options.get('to')
        timeframe = options.get('timeframe')

        def gen_trainer_filename() -> str:
            return "trainer_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace(
                '/', '_').replace('+', '0')

        def write_trainer_file(filename: str, _trainer_params: dict, _strategy_params: dict):
            data = {
                'created': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                'trainer': _trainer_params,
                'strategy': _strategy_params
            }

            utils.write_learning(options['learning-path'], filename, data)

        n = 5  # debug only

        while 1:
            sub_name = "Sub-%s" % n
            learning_filename = gen_trainer_filename()

            trainer_params = self._learning_config.get('trainer', {})
            strategy_params = self._learning_config.get('strategy', {})

            write_trainer_file(learning_filename, trainer_params, strategy_params)

            cmd_opts = [
                'python',
                'siis.py',
                options['identity'],
                '--profile=%s' % self._profile,
                '--backtest',
                '--from=%s' % from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                '--to=%s' % to_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                '--timeframe=%s' % timeframe,
                '--learning=%s' % learning_filename,
                '--exit'
            ]

            print("Run sub-process %s" % sub_name)
            with subprocess.Popen(cmd_opts) as p:
                p.wait()
                print("-- %s Done" % sub_name)

            n += 1

            if n >= 5:
                break

        return True

    def terminate(self, options):
        if self._watcher_service:
            self._watcher_service.terminate()

        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = Trainer
