# @date 2018-11-30
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Android applicatin bot message post.

import json
import requests


def send_to_android(auth_key, channel="/topics/default", title, message, sound="default"):
    """
    Post a message to SiiS Adnroid application using Firebase.
    """

    FCM_URL = "https://fcm.googleapis.com/fcm/send"

    payload = {
        "to": dest,
        "notification": {
            'title': title,
            'body': message,
            'sound': sound
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization:key': auth_key
    }
    
    response = requests.post(FCM_URL, data=json.dumps(payload), headers=headers)
    return response
