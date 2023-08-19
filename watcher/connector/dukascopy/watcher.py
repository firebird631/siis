# @date 2023-08-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# ig.com watcher implementation

import copy
import json
import time
import pytz
import traceback

from datetime import datetime, timedelta

from watcher.watcher import Watcher
from common.signal import Signal

from connector.ig.connector import IGConnector
from connector.ig.lightstreamer import LSClient, Subscription

from instrument.instrument import Instrument
from database.database import Database

from trader.order import Order
from trader.market import Market

from common.utils import decimal_place, UTC

import logging
logger = logging.getLogger('siis.watcher.dukascopy')
exec_logger = logging.getLogger('siis.exec.dukascopy.ig')
error_logger = logging.getLogger('siis.error.watcher.dukascopy')
traceback_logger = logging.getLogger('siis.traceback.watcher.dukascopy')


class DukascopyWatcher(Watcher):
    """
    Dukascopy watcher get price and volumes of instruments in live mode through websocket API.

    @note Not implemented (only data fetcher)
    """

    def __init__(self, service):
        super().__init__("dukascopy.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)
