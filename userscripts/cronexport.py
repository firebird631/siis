import json
import time
from datetime import datetime
import threading

from strategy.strategy import Strategy
from common.utils import UTC


class CronExportScript(threading.Thread):
    TRADES_DELAY = 60.0
    SLEEP_TIME = 5.0
    BALANCE_DELAY = 60*60*24

    def __init__(self, strategy_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._trades_last_time = 0.0
        self._balances_last_time = 0.0

        self._process = True

    def run(self):
        while self._process:
            now = time.time()
            if now - self._trades_last_time >= CronExportScript.TRADES_DELAY:
                self._trades_last_time = now

                if self._strategy_service.strategy():
                    # export actives and pending trades
                    results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                        'dataset': "active",
                        'pending': True,
                        'export-format': "json",
                        'filename': "last.json",
                    })

            if now - self._balances_last_time >= CronExportScript.BALANCE_DELAY:
                self._balances_last_time = now

                if self._strategy_service.strategy():
                    # export current account balance
                    trader = self._strategy_service.strategy().trader()
                    if trader:
                        balances = {
                            'date': datetime.now().astimezone(UTC()).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            'balance': trader.account.balance,
                            'asset-balance': trader.account.asset_balance
                        }

                        try:
                            with open("/tmp/siis_balances.json", "rb") as f:
                                dataset = json.loads(f.read())
                        except FileNotFoundError:
                            dataset = []

                        dataset.append(balances)

                        with open("/tmp/siis_balances.json", "w") as f:
                            f.write(json.dumps(dataset))

            time.sleep(CronExportScript.SLEEP_TIME)

    def stop(self):
        self._process = False
        super().join(10)


def run_once(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    results['messages'].append("Install cron trade data export")

    monitor_service.install_script('cron-export', CronExportScript(strategy_service))
    return results


def remove(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    results['messages'].append("Stop and remove cron trade data export")

    monitor_service.remove_script('cron-export')
    return results
