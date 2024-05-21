import requests

from src.twitch_ircchat_utils import replace_keywords

TWITCH_EVENTSUB_URL = 'https://api.twitch.tv/helix/eventsub/subscriptions'


def subscribe_to_follow(self, session_id):
    data = {
        'type': 'channel.follow',
        'version': '2',
        'condition': {
            "broadcaster_user_id": self.user['data'][0]['id'],
            "moderator_user_id": self.user['data'][0]['id']
        },
        'transport': {
            'method': 'websocket',
            'session_id': session_id
        }
    }

    response = requests.post(TWITCH_EVENTSUB_URL, headers=self.headers, json=data, timeout=5)
    return response.json()


def subscribe_to_sub(self, session_id):
    data = {
        'type': 'channel.follow',
        'version': '2',
        'condition': {
            "broadcaster_user_id": self.user['data'][0]['id'],
            "moderator_user_id": self.user['data'][0]['id']
        },
        'transport': {
            'method': 'websocket',
            'session_id': session_id
        }
    }

    response = requests.post(TWITCH_EVENTSUB_URL, headers=self.headers, json=data, timeout=5)
    return response.json()


def get_user_info(self):
    response = requests.get('https://api.twitch.tv/helix/users', headers=self.headers, timeout=5)
    if response.status_code in range(200, 299):
        return response.json()
    return None


def handle_eventsub_messages(self, message):
    match message['metadata']['subscription_type']:
        case 'channel.follow':
            message = replace_keywords("[user_name] ti sta seguendo!", message)
            self.manager.print.print_to_logs(message, self.manager.print.ORANGE)
