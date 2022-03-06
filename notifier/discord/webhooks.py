# @date 2018-11-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Discord bot message post.

import json
import requests


def send_to_discord(webhook_url: str, who: str, message: str, data: dict = None):
    """
    Post a message to discord API via a Webhook.

    @note It use the simple Discord WebHook, only posting limit text message is possible by this way.
    More advanced usage, including image, deletion of previous post require to use the Discord REST API.
    """
    payload = {
        "username": who,
        "content": message
    }
    headers = {
        'Content-Type': 'application/json',
    }

    if data is not None and type(data) is dict:
        payload.update(data)

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
    return response
