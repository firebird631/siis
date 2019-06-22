# @date 2019-06-21
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade region.

import logging
logger = logging.getLogger('siis.strategy')


class Region(object):
    """
    Startegy trade region base class.
    """

    REGION_UNDEFINED = 0
    REGION_RANGE = 1
    REGION_TREND = 2

    STAGE_ENTRY = 1
    STAGE_EXIT = -1

    NAME = "undefined"
    REGION = Region.REGION_UNDEFINED

    def __init__(self, _id, type):
        self._id = _id       # operation index in the list of operations of the trade
        self._stage = stage  # apply on entry or exit
        self._expiry = 0     # expiration timestamp (<=0 never)

    #
    # getters
    #

    @classmethod
    def name(cls):
        """
        String type name of the region.
        """
        return cls.NAME

    @classmethod
    def region(cls):
        """
        Integer type of region.
        """
        return cls.REGION

    @property
    def id(self):
        """
        Unique region identifier.
        """
        return self._id

    @property
    def stage(self):
        """
        Zone for entry or exit.
        """
        return self._stage

    @property
    def expiry(self):
        """
        Expiry timestamp in second.
        """
        return self._expiry

    #
    # setters
    #

    @id.setter
    def id(self, _id):
        self._id = _id


    @expiry.setter
    def expiry(self, expiry):
        self._expiry expiry

    