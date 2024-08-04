# @date 2020-10-20
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Indicator data models

from dataclasses import dataclass, field


@dataclass
class VolumeProfile:
    """
    Volume Profile.
    Merged or distinct bid/ask volumes.
    With extra levels of interest : peaks, valleys.
    @note VA, peaks and valleys are not guarantee because they are computed by default.
    """
    timestamp: float     # base timestamp
    timeframe: float     # relate timeframe or 0

    sensibility: float = 0.0    # base price per bin computation sensibility (can be linear or logarithmic)

    poc: float = 0.0     # Point of Control, in price
    val: float = 0.0     # Low value area, in price
    vah: float = 0.0     # High value area, in price

    volumes: dict = field(default_factory=dict)    # price:volume or tuple(bid/ask)

    peaks: list = field(default_factory=list)      # prices of peaks
    valleys: list = field(default_factory=list)    # prices of valleys
