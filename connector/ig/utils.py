# -*- coding:utf-8 -*-

import os
import logging
import traceback

logger = logging.getLogger(__name__)


def conv_datetime(dt, version=1):
	"""
	Converts dt to string like
	version 1 = 2014:12:15-00:00:00
	version 2 = 2014/12/15 00:00:00
	"""
	try:
		d_formats = {
			1: "%Y:%m:%d-%H:%M:%S",
			2: "%Y/%m/%d %H:%M:%S",
			3: "%Y/%m/%dT%H:%M:%S"
		}
		fmt = d_formats[version]
		return dt.strftime(fmt)
	except (ValueError, TypeError):
		logger.error(traceback.format_exc())
		logger.warning("conv_datetime returns %s" % dt)
		return dt


def conv_to_ms(td):
	"""
	Converts td to integer number of milliseconds
	"""
	try:
		if isinstance(td, int):
			return td
		else:
			return int(td.total_seconds() * 1000.0)
	except ValueError:
		logger.error(traceback.format_exc())
		logger.warning("conv_to_ms returns '%s'" % td)
		return td
