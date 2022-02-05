# @date 2022-02-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Telegram bot message API support.

import json
import requests

PROTOCOL = "https:/"
API_URL = "api.telegram.org"

# tradeitxsiis_bot / bot chat_id 1026569787 / group chat_id : -710360325


def send_to_telegram(bot_token, chat_id, message):
    """
    Post a message to telegram via API.
    To retrieve a chat_id : curl https://api.telegram.org/bot<TOKEN>/getUpdates
    """
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    headers = {
        'Content-Type': 'application/json',
    }

    api_url = '/'.join((PROTOCOL, API_URL, 'bot'+bot_token, 'sendMessage'))

    response = requests.post(api_url, data=json.dumps(payload), headers=headers)
    return response


def get_telegram_updates(bot_token, update_id=0):
    """
    Retrieve the last bot message updates and return only the commands.
    @param bot_token: Bot token.
    @param update_id: After update_id
    @return:
    """
    commands = []
    last_update_id = 0

    headers = {
        'Content-Type': 'application/json',
    }

    api_url = '/'.join((PROTOCOL, API_URL, 'bot'+bot_token, 'getUpdates'))

    response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        return []

    data = response.json()

    if not data or not data.get('ok', False):
        return []

    results = data.get('result', [])

    for result in results:
        last_update_id = result.get('update_id', 0)
        if last_update_id <= update_id:
            # ignored update id
            continue

        message = result.get('message')
        if not message:
            continue

        chat = message.get('chat')
        if not chat:
            continue

        chat_id = chat.get('id')
        if not chat_id:
            continue

        text = message.get('text')
        is_bot_command = False

        entities = message.get('entities', [])
        if entities and entities[0].get('type', "") == "bot_command":
            is_bot_command = True

        if is_bot_command and text.startswith('/'):
            commands.append((chat_id, text))

    return last_update_id, commands
