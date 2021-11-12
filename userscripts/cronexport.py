import time
import threading

from strategy.strategy import Strategy


class CronExportScript(threading.Thread):
    DELAY = 60.0
    SLEEP_TIME = 5.0

    def __init__(self, strategy_service):
        super().__init__()

        self._strategy_service = strategy_service
        self._last_time = time.time()

        self._process = True

    def run(self):
        while self._process:
            now = time.time()
            if now - self._last_time >= CronExportScript.DELAY:
                self._last_time = now

                results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                    'dataset': "active",
                    'pending': True,
                    'export-format': "json",
                    'filename': "last.json",
                })

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
