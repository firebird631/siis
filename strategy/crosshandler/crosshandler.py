# @date 2021-10-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy cross trader handler.

class CrossHandler(object):
    """
    Strategy trader cross handler base class.
    """

    def __init__(self, context_id, timeframe):
        self._context_id = context_id
        self._timeframe = timeframe
