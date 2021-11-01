# List of implemented strategy indicators #

A strategy can operate ony many markets and many timeframes, for each timeframe there is sub, and each sub can compute multiples indicators.

Indicators take input data, compute at every update (tick, trade, candle) or only at candle close, or any other circumstances implemented by the strategy.

Some indicators generate an array of the same size of the input, or multiples array, some others are more exotics, and compute non temporals results,
or temporal results buy with a different structure than the inputs.

...


## List ##

### Price ###

...

### Volume ###

...

### Momentum ###

...

### SMA ###

Most common and simple indicator, the smoothed moving average.

...

### EMA ###

...

### HEMA ###

...

### WMA ###

...

### VWMA ###

...

### RSI ###

...

### Stochastic ###

...

### Stochastic RSI ###

...

### Parabolic SAR ###

...

### Average True Range (ATR) ###

...

### SineWave (Simplified Hilbert) ###

...

### MESA MAMA (SineWave based adaptive moving average) ###

...

### MACD ###

...

### Donchian Channel ###

...

### Bollinger Bands ###

...

### Ichimoku ###

...

### Tomdemark TD9 ###

...

### Buy/sell signal detection based on Awesome (BSAwe) ###

...


### ATR based Support/resistance detection ###

...

### Triangle based detection ###

...

### ZigZag based detection ###

...


## Creating an indicator ##

...

### Base class ###

...

### Registration ###

...
