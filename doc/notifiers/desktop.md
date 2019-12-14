# Desktop Notifier #

This notifier is always loaded and defined.

It offers in a Linux desktop environment the ability to display a desktop popup using D-Bus,
and to emit audio alerts using aplay (Alsa Player).

Audible alerts can be customized.

There is currently no support for Windows desktop similar behaviors.

On a server installation there is no such D-Bus or audio support, then they can be disabled.

By default the poups and audio notifications are disabled.

To toggle the desktop notification press the 'n' key.
To toggle the audible notification press the 'a' key.

## Configuration ##

* "play-alerts" boolean, default to false, play audio alerts
* "display-popups" boolean, default to false, display desktop popups
* "audio" dict ...
	* "device" string, default to "pulse", audio device
	* "alerts" dict ...

...
