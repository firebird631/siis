# Notifying of signals, trades, accounts and system reports #

Notifier offers the possibility to send notification to external services and the system desktop.


### Configuration ###

Each notifier can be configured per profile, in the "notifiers": {} map section.
In addition each notifier has a specific configuration file in config/notifiers/ directory,
with a possible overriding in the user config directory.


## Desktop ##

By default the desktop notifier is always initiated, but on VPS dBus will not be available, neither audio support.
It is possible to disable it from a profile.

* Display system desktop popup notification using dBus on Linux
* Play audio alerts using aplay (alsa player) on Linux
* Not support for Windows desktop for now
* Customizable audio alerts at user level and at profile level

### Configuration ###

* "play-alerts" boolean, default to false, play audio alerts
* "display-popups" boolean, default to false, display desktop popups
* "audio" dict ...
	* "device" string, default to "pulse", audio device
	* "alerts" dict ...


## Android ##

An Android application is in development, and allow to receive notifications using the Firebase API.
This application could be used to receive public signals, or to receive your own private notification using your private auth-key.


### Configuration ###

...

## Discord ##

Only webhooks supported. Help is welcome to uses Discord API for more advanced features.

### Configuration ###

...


## Xmpp ##

Planned support, help is welcome.

### Configuration ###

...


## Telegram ##

Planned support, help is welcome.

### Configuration ###

...


## Hangout ##

Planned support, help is welcome.

### Configuration ###

...
