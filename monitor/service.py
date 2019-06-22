# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker for web monitoring

import json
import time, datetime
import tempfile, os, posix
import threading
import collections

from common.service import Service
from terminal.terminal import Terminal

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from config import utils

import logging
logger = logging.getLogger('siis.monitor')


class MonitorService(Service):
    """
    Monitoring web service.
    @todo REST HTTP(S) server + WS server.
    @todo receive REST external commands
    @todo streaming throught WS server + streaming API for any sort of data
    @todo streaming of the state and any signals that can be monitored + charting and appliances data
    @todo unix filesocket.
    """

    LEVEL_WATCHER = 0            # can only receive streaming and state
    LEVEL_SIMPLE_MANAGER = 1     # can receive most of the streams + send orders but not the restricted ones
    LEVEL_FULL_MANAGER = 2       # can receive any of the streams + send any of the orders => full access

    def __init__(self, options):
        super().__init__("monitor", options)

        # monitoring config
        self._monitoring_config = utils.monitoring(options.get('config-path')) or {}

        if options.get('monitored', True):
            self._monitoring = True
        else:
            self._monitoring = False

        self._level = MonitorService.LEVEL_WATCHER

        self._content = collections.deque()

        self._fifo = -1
        self._fifo_read = None

        self._thread = None
        self._running = False

        # host, port, allowed host, order, deny... from config

    def start(self):
        if self._monitoring:
            self._tmpdir = tempfile.mkdtemp()
            self._filename = os.path.join(self._tmpdir, 'siis.stream')

            Terminal.inst().info("- Open a monitoring FIFO at %s" % self._filename)

            try:
                os.mkfifo(self._filename, 0o600)
            except OSError as e:
                logger.error("Failed to create monitor FIFO: %s" % repr(e))
                os.rmdir(self._tmpdir)
            else:
                # self._fifo = posix.open(self._filename, posix.O_NONBLOCK + posix.O_WRONLY)
                self._fifo = posix.open(self._filename, posix.O_RDWR + posix.O_NONBLOCK)

        if self._fifo:
            self._running = True
            self._thread = threading.Thread(name="monitor", target=self.update)     
            self._thread.start()

    def terminate(self):
        # remove any streamables
        self._running = False

        if self._fifo > 0:
            try:
                posix.close(self._fifo)
                self._fifo = -1
            except (BrokenPipeError, IOError):
                pass

            os.remove(self._filename)
            os.rmdir(self._tmpdir)

        if self._thread:
            try:
                self._thread.join()
            except:
                pass

            self._thread = None

    def update(self):
        while self._running:
            buf = []*8192

            if self._fifo > 0 and self._monitoring:
                try:
                    buf = posix.read(self._fifo, len(buf))
                except (BrokenPipeError, IOError):
                    pass    

            count = 0

            while self._content:
                c = self._content.popleft()

                # insert category, group and stream name
                c[3]['c'] = c[0]
                c[3]['g'] = c[1]
                c[3]['s'] = c[2]

                try:
                    # write to fifo
                    posix.write(self._fifo, (json.dumps(c[3]) + '\n').encode('utf8'))
                    # msg = json.dumps({'s': None}) + '\n'
                    # posix.write(self._fifo, msg.encode('utf8'))
                except (BrokenPipeError, IOError):
                    pass
                except (TypeError, ValueError) as e:
                    logger.error("Monitor error sending message : %s" % repr(c))

                count += 1
                if count > 10:
                    break

            # don't waste the CPU
            time.sleep(0)  # yield 0.001)

    def command(self, command_type, data):
        pass

    def push(self, stream_category, stream_group, stream_name, content):
        if self._running:
            self._content.append((stream_category, stream_group, stream_name, content))
