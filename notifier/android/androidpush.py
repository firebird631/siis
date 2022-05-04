# @date 2018-11-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Android Firebase push.

import json
import requests

FCM_URL = "https://fcm.googleapis.com/fcm/send"


def send_to_android(auth_key, channel, title, message, sound="default"):
    """
    Post a message to SiiS Android application using Firebase.
    """
    payload = {
        "to": channel or "/topics/default",
        "notification": {
            'title': title,
            'body': message,
            'sound': sound,
            # 'icon' : 'app logo',
            # 'badge' : 'icon in task android bar / iOS monochrome)',
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': "key=" + auth_key
    }

    response = requests.post(FCM_URL, data=json.dumps(payload), headers=headers)
    return response
