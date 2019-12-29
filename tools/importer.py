# @date 2019-12-23
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Importer tool.

import sys
import logging
import traceback

from datetime import datetime, timedelta

from instrument.instrument import Instrument
from common.utils import UTC, TIMEFRAME_FROM_STR_MAP, timeframe_to_str, format_datetime, format_delta

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.importer')


def do_exporter(options):
    Terminal.inst().info("Starting SIIS importer...")
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    filename = options.get('filename')

    # @todo

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Importation done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
