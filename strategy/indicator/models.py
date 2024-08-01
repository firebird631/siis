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
    @todo should be a 2d volumes array or if keep dict price if not base per buck but mid to be more accurate
    @todo need a bid ask version or only keep the bid ask version because to many cases after that
    """

    timestamp: float     # base timestamp
    timeframe: float     # relate timeframe or 0

    poc: float = 0.0     # Point of Control, in price
    val: float = 0.0     # Low value area, in price
    vah: float = 0.0     # High value area, in price

    volumes: dict = field(default_factory=dict)    # price:volume

    peaks: list = field(default_factory=list)      # prices of peaks
    valleys: list = field(default_factory=list)    # prices of valleys
