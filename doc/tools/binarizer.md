# Binarizer tool #

From a text version files of ticks/trades, convert them to theirs binary file representation.
Binary files are defaults, but for now the twice are recorded (.dat for binary version, no extension for text).

The binarizer command tool allow to convert a text file to its binary format, at the correct location.
Next the parser (tick streamer) will use by default the binary version if available, because the speed gain is important.

...