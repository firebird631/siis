# @date 2019-01-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Utils

from __future__ import annotations

from typing import Union, Set, Tuple, List

import math

from datetime import datetime, timedelta, tzinfo


class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)


# timeframe to str map (double: str)
TIMEFRAME_TO_STR_MAP = {
    0: 't',
    1: '1s',
    3: '3s',
    5: '5s',
    10: '10s',
    15: '15s',
    30: '30s',
    45: '45s',
    60: '1m',
    2*60: '2m',
    3*60: '3m',
    5*60: '5m',
    10*60: '10m',
    15*60: '15m',
    30*60: '30m',
    45*60: '45m',
    60*60: '1h',
    2*60*60: '2h',
    3*60*60: '3h',
    4*60*60: '4h',
    6*60*60: '6h',
    8*60*60: '8h',
    12*60*60: '12h',
    24*60*60: '1d',
    2*24*60*60: '2d',
    3*24*60*60: '3d',
    7*24*60*60: '1w',
    30*24*60*60: '1M'
}

# timeframe reverse map (str: double)
TIMEFRAME_FROM_STR_MAP = {v: k for k, v in TIMEFRAME_TO_STR_MAP.items()}


def timeframe_to_str(timeframe: float) -> str:
    return TIMEFRAME_TO_STR_MAP.get(timeframe, "")


def timeframe_from_str(timeframe: str) -> float:
    return TIMEFRAME_FROM_STR_MAP.get(timeframe, 0.0)


def timestamp_to_str(timestamp: float) -> str:
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def is_solid_timeframe(timeframe: float) -> bool:
    return timeframe in TIMEFRAME_TO_STR_MAP


def direction_to_str(direction: int) -> str:
    if direction > 0:
        return 'long'
    elif direction < 0:
        return 'short'
    else:
        return ''


def direction_from_str(direction: str) -> int:
    if direction == 'long':
        return 1
    elif direction == 'short':
        return -1
    else:
        return 0


def matching_symbols_set(configured_symbols: Union[Tuple[str], List[str], Set[str]],
                         available_symbols: Union[Tuple[str], List[str], Set[str]]) -> Set[str]:
    """
    Special '*' symbol mean every symbol.
    Starting with '!' mean except this symbol.
    Starting with '*' mean every wildcard before the suffix.

    @param configured_symbols
    @param available_symbols List containing any supported markets symbol of the broker.
           Used when a wildcard is defined.
    """
    if not configured_symbols:
        return set()

    if not available_symbols:
        return set()

    if '*' in configured_symbols:
        # all instruments
        watched_symbols = set(available_symbols)

        # except...
        for configured_symbol in configured_symbols:
            if configured_symbol.startswith('!'):
                # ignore, not wildcard, remove it
                watched_symbols.remove(configured_symbol[1:])
    else:
        watched_symbols = set()

        for configured_symbol in configured_symbols:
            if configured_symbol.startswith('*'):
                # all ending symbols name with...
                suffix = configured_symbol[1:]

                for symbol in available_symbols:
                    # except...
                    if symbol.endswith(suffix) and ('!'+symbol) not in configured_symbols:
                        watched_symbols.add(symbol)

            elif not configured_symbol.startswith('!'):
                # not ignored, not wildcard
                watched_symbols.add(configured_symbol)

    return watched_symbols


def fix_thread_set_name():
    try:
        import threading
        import prctl
        def set_thread_name(name): prctl.set_name(name)

        def _thread_name_hack(self):
            set_thread_name(self.name)
            threading.Thread._bootstrap_original(self)

        threading.Thread._bootstrap_original = threading.Thread._bootstrap
        threading.Thread._bootstrap = _thread_name_hack
    except ImportError:
        def set_thread_name(name): pass

        import logging
        error_logger = logging.getLogger('siis.error.utils')
        error_logger.warning('prctl module is not installed. You will not be able to see thread names')


def truncate(number: float, digits: int) -> float:
    stepper = pow(10.0, digits)
    # return math.trunc(stepper * number) / stepper
    # round to avoid some issue in case of some values like 2.43427459 and digits = 8
    return math.trunc(round(stepper * number)) / stepper


def decimal_place(value: float) -> int:
    return -int(math.floor(math.log10(value)))


def format_quantity(quantity: float, precision: int) -> str:
    """
    Return a str version of the float quantity truncated to the precision.
    """
    qty = "{:0.0{}f}".format(truncate(quantity, precision), precision)

    if '.' in qty:
        qty = qty.rstrip('0').rstrip('.')

    return qty


def format_datetime(timestamp: float) -> str:
    """
    Format as human readable in UTC.
    """
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
    # same as utcfromtimestamp but contains the tzinfo
    # return datetime.fromtimestamp(timestamp, tz=UTC()).strftime('%Y-%m-%d %H:%M:%S UTC')


def format_delta(td: float) -> str:
    """
    Format a time delta in a human readable format.
    """
    if abs(td) < 60.0:
        return "%.6f seconds" % td

    if abs(td) < 60*60:
        m, r = divmod(td, 60)
        s = r

        return "%i minutes %i seconds" % (m, s)

    elif abs(td) < 60*60*24:
        h, r = divmod(td, 60*60)
        m, r = divmod(r, 60)
        s = r

        return "%i hours %i minutes %i seconds" % (h, m, s)

    else:
        d, r = divmod(td, 60*60*24)
        h, r = divmod(r, 60*60)
        m, r = divmod(r, 60)
        s = r

        return "%i days %i hours %i minutes %i seconds" % (d, h, m, s)


def parse_utc_datetime(formatted: str) -> Union[datetime, None]:
    if formatted:
        try:
            if formatted.endswith('Z'):
                # always UTC
                formatted = formatted.rstrip('Z')

            if 'T' in formatted:
                if formatted.count(':') == 2:
                    if formatted.count('.') == 1:
                        return datetime.strptime(formatted, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=UTC())
                    else:
                        return datetime.strptime(formatted, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC())
                elif formatted.count(':') == 1:
                    return datetime.strptime(formatted, '%Y-%m-%dT%H:%M').replace(tzinfo=UTC())
                elif formatted.count(':') == 0:
                    return datetime.strptime(formatted, '%Y-%m-%dT%H').replace(tzinfo=UTC())
            else:
                if formatted.count('-') == 2:
                    return datetime.strptime(formatted, '%Y-%m-%d').replace(tzinfo=UTC())
                elif formatted.count('-') == 1:
                    return datetime.strptime(formatted, '%Y-%m').replace(tzinfo=UTC())
                elif formatted.count('-') == 0:
                    return datetime.strptime(formatted, '%Y').replace(tzinfo=UTC())
        except:
            return None

    return None


def parse_datetime(formatted: str) -> Union[datetime, None]:
    if formatted:
        try:
            result = None
            use_utc = False

            if formatted.endswith('Z'):
                formatted = formatted.rstrip('Z')
                use_utc = True

            if 'T' in formatted:
                if formatted.count(':') == 2:
                    if formatted.count('.') == 1:
                        result = datetime.strptime(formatted, '%Y-%m-%dT%H:%M:%S.%f')
                    else:
                        result = datetime.strptime(formatted, '%Y-%m-%dT%H:%M:%S')
                elif formatted.count(':') == 1:
                    result = datetime.strptime(formatted, '%Y-%m-%dT%H:%M')
                elif formatted.count(':') == 0:
                    result = datetime.strptime(formatted, '%Y-%m-%dT%H')
            else:
                if formatted.count('-') == 2:
                    result = datetime.strptime(formatted, '%Y-%m-%d')
                elif formatted.count('-') == 1:
                    result = datetime.strptime(formatted, '%Y-%m')
                elif formatted.count('-') == 0:
                    result = datetime.strptime(formatted, '%Y')

            if result:
                if use_utc:
                    result = result.replace(tzinfo=UTC())

                return result
        except:
            return None

    return None


def period_from_str(period: str) -> float:
    try:
        if period.endswith('s'):
            return float(period[:-1]) * 1.0
        if period.endswith('m'):
            return float(period[:-1]) * 60.0
        if period.endswith('h'):
            return float(period[:-1]) * 3600.0
        elif period.endswith('d'):
            return float(period[:-1]) * 3600.0 * 24
        elif period.endswith('w'):
            return float(period[:-1]) * 3600.0 * 24 * 7
        elif period.endswith('M'):
            return float(period[:-1]) * 3600.0 * 24 * 30
        elif period.endswith('Y'):
            return float(period[:-1]) * 3600.0 * 24 * 365
        return float(period)
    except ValueError:
        return 0.0


def check_yes_no_opt(param: Union[str, int, bool]) -> bool:
    """
    Parse and verify a yes/no option from str, int or direct bool.
    Return True if the option has a valid format and value.
    """
    if type(param) is str:
        return param.lower() in ("yes", "no", "0", "1", "true", "false")

    elif type(param) is int:
        return 0 <= param <= 1

    elif type(param) is bool:
        return True

    return False


def yes_no_opt(param: Union[str, int, bool]) -> Union[bool, None]:
    """
    Parse a yes/no option from str, int or direct bool.
    Return True or False if respectively value means Yes or No else return None if invalid format or value.
    """
    if type(param) is str:
        if param.lower() in ("yes", "true", "1"):
            return True
        elif param.lower() in ("no", "false", "0"):
            return False

    elif type(param) is int:
        if 0 <= param <= 1:
            return bool(param)

    elif type(param) is bool:
        return param

    return None


def check_integer_opt(param: Union[str, int], min_value: int, max_value: int) -> bool:
    """
    Parse and verify an integer option from str or int.
    Return True if the option has a valid format and value from the range min/max.
    """
    if type(param) is str:
        try:
            v = int(param)
            if min_value <= v <= max_value:
                return True
        except ValueError:
            return False

    elif type(param) is int:
        return min_value <= param <= max_value

    return False


def integer_opt(param: Union[str, int], min_value: int, max_value: int) -> Union[int, None]:
    """
    Parse an integer option from str or int.
    Return True the integer value if option has a valid format and value from the range min/max.
    """
    if type(param) is str:
        try:
            v = int(param)
            if min_value <= v <= max_value:
                return v
        except ValueError:
            return None

    elif type(param) is int:
        if min_value <= param <= max_value:
            return param

    return None


def check_float_opt(param: Union[str, float, int], min_value: float, max_value: float) -> bool:
    """
    Parse and verify an float option from str, int or float.
    Return True if the option has a valid format and value from the range min/max.
    """
    if type(param) is str:
        try:
            v = float(param)
            if min_value <= v <= max_value:
                return True
        except ValueError:
            return False

    elif type(param) is float:
        return min_value <= param <= max_value

    elif type(param) is int:
        return min_value <= float(param) <= max_value

    return False


def float_opt(param: Union[str, float, int], min_value: float, max_value: float) -> Union[float, None]:
    """
    Parse a float option from str, int or float.
    Return True if the option has a valid format and value from the range min/max.
    """
    if type(param) is str:
        try:
            v = float(param)
            if min_value <= v <= max_value:
                return v
        except ValueError:
            return None

    elif type(param) is float:
        if min_value <= param <= max_value:
            return param

    elif type(param) is int:
        if min_value <= float(param) <= max_value:
            return param

    return None
