# @date 2024-08-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Event type and model


class BaseEvent:

    EVENT_TYPE_UNDEFINED = 0
    EVENT_TYPE_ECONOMIC = 1

    @classmethod
    def event_type(cls):
        return BaseEvent.EVENT_TYPE_UNDEFINED


class EconomicEvent:

    def __init__(self):
        self.code = ""
        self.date = None
        self.title = ""
        self.level = 0
        self.country = ""
        self.currency = ""
        self.previous = 0.0
        self.actual = 0.0
        self.forecast = 0.0
        self.reference = 0
        self.actual_meaning = -2
        self.previous_meaning = -2

    @classmethod
    def event_type(cls):
        return BaseEvent.EVENT_TYPE_ECONOMIC

    @staticmethod
    def meaning_to_str(meaning):
        if meaning == 1:
            return "positive"
        elif meaning == 0:
            return "neutral"
        elif meaning == -1:
            return "negative",
        else:
            return "unknown"

    def __str__(self):
        return "%s at=%s lvl=%i curr=%s (impact=%s)" % (
            self.code,
            self.date.strftime("%Y-%m-%d %H:%M"),
            self.level,
            self.currency,
            self.meaning_to_str(self.actual_meaning))
