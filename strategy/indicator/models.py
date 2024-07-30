# @date 2020-10-20
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Indicator data models

from dataclasses import dataclass, field


@dataclass
class VolumeProfile:
    """
    Volume Profile.
    Merged bid/ask volumes.
    With extra levels of interest : peaks, valleys.
    """

    timestamp: float
    timeframe: float

    poc: float = 0.0
    low_area: float = 0.0
    high_area: float = 0.0

    volumes: dict = field(default_factory=dict)

    peaks: list = field(default_factory=list)
    valleys: list = field(default_factory=list)
