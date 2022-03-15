import json
import time
from datetime import datetime
import threading

from trader.trader import Trader
from strategy.strategy import Strategy
from common.utils import UTC


class CronExportScript(threading.Thread):
    TRADES_DELAY = 60.0
    SLEEP_TIME = 5.0
    BALANCE_DELAY = 60.0*60*24
    ALERT_DELAY = 60.0*5
    REGION_DELAY = 60.0*5
    STRATEGY_DELAY = 60.0*5
    TRADER_DELAY = 60.0*5
    HISTORY_DELAY = 60.0 * 5

    def __init__(self, strategy_service, trader_service, unmanaged=False):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._trades_last_time = 0.0
        self._balances_last_time = 0.0
        self._alerts_last_time = 0.0
        self._regions_last_time = 0.0
        self._strategy_last_time = 0.0
        self._trader_last_time = 0.0
        self._history_last_time = 0.0

        self._process = True
        self._unmanaged = unmanaged

        self._report_path = strategy_service.report_path

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
                        'filename': self._report_path + "/siis_trades.json",
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
                            with open(self._report_path + "/siis_balances.json", "rb") as f:
                                dataset = json.loads(f.read())
                        except FileNotFoundError:
                            dataset = []

                        dataset.append(balances)

                        with open(self._report_path + "/siis_balances.json", "w") as f:
                            f.write(json.dumps(dataset))

            if now - self._alerts_last_time >= CronExportScript.ALERT_DELAY:
                self._alerts_last_time = now

                if self._strategy_service.strategy():
                    # export actives alerts
                    results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                        'dataset': "alert",
                        'export-format': "json",
                        'filename': self._report_path + "/siis_alerts.json",
                    })

            if now - self._regions_last_time >= CronExportScript.REGION_DELAY:
                self._regions_last_time = now

                if self._strategy_service.strategy():
                    # export actives regions
                    results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                        'dataset': "region",
                        'export-format': "json",
                        'filename': self._report_path + "/siis_regions.json",
                    })

            if now - self._strategy_last_time >= CronExportScript.STRATEGY_DELAY:
                self._strategy_last_time = now

                if self._strategy_service.strategy():
                    # export strategy traders with trades alerts and regions and states
                    results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                        'dataset': "strategy",
                        'export-format': "json",
                        'filename': self._report_path + "/siis_strategy.json",
                    })

            if now - self._trader_last_time >= CronExportScript.TRADER_DELAY:
                self._trader_last_time = now

                if self._trader_service.trader():
                    # export trader state, orders, assets, positions and account
                    results = self._trader_service.command(Trader.COMMAND_EXPORT, {
                        'dataset': "trader",
                        'export-format': "json",
                        'filename': self._report_path + "/siis_trader.json",
                    })

            if now - self._history_last_time >= CronExportScript.HISTORY_DELAY:
                self._history_last_time = now

                if self._strategy_service.strategy():
                    # export historical trades
                    results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                        'dataset': "history",
                        'pending': True,
                        'export-format': "json",
                        'filename': self._report_path + "/siis_history.json",
                    })

            if self._unmanaged and self._strategy_service.strategy() is None:
                # conditional break for older version
                self._process = False
                break

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

    if hasattr(monitor_service, 'install_script'):
        if not monitor_service.has_script('cron-export'):
            monitor_service.install_script('cron-export', CronExportScript(strategy_service, trader_service))
    else:
        # for older version
        try:
            instance = CronExportScript(strategy_service, trader_service, True)
            instance.start()
        except Exception as e:
            results['error'] = True
            results['messages'].append(repr(e))

    return results


def remove(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    results['messages'].append("Stop and remove cron trade data export")

    if hasattr(monitor_service, 'remove_script'):
        if monitor_service.has_script('cron-export'):
            monitor_service.remove_script('cron-export')

    return results
