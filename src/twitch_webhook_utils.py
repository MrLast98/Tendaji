import json
import os
import re
import string
from time import time
from urllib.parse import urlencode
from webbrowser import open as wbopen

import requests

from defaults import DEFAULT_COMMANDS
from src.ai_helper import analyze_sentiment
from twitch_commands import FUNCTION_LIST, send_message

COMMANDS_FILE = 'config/commands.json'
KEYWORD_PATTERN = r'\[([^\]]+)\]'
SCOPE_TWITCH = 'chat:read chat:edit moderator:read:followers'

# Necessary Links for authorization
TWITCH_AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'


async def authenticate(self, websocket):
    # Send PASS and NICK commands to authenticate
    await websocket.send('CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands')
    await websocket.send(f"PASS oauth:{self.manager.configuration['twitch-token']['access_token']}")
    await websocket.send(f"NICK {self.channel}")


async def join_channel(self, websocket):
    # Join the specified channel
    await websocket.send(f"JOIN #{self.channel}")
    load_commands(self)
    self.manager.print.print_to_logs(f'Logged in to the chat of {self.channel}', self.manager.print.GREEN)


def format_message(message):
    sub = '[SUB]' if message['tags']['subscriber'] else ''
    vip = '[VIP]' if message['tags']['vip'] else ''
    mod = '[MOD]' if message['tags']['mod'] else ''
    broadcaster = '[BROADCASTER]' if message['tags']['broadcaster'] else ''
    tags = f"{broadcaster}{mod}{vip}{sub}"
    author = f"{tags}{message['tags']['display-name']}"
    return f"{author}: {message['parameters'].strip('\r\n')}"


async def handle_irc_message(self, message):
    # Split the message into parts to identify the command
    message = parse_message(message)
    if message:
        match message['command']['command']:
            case 'JOIN':
                # Handle JOIN message
                pass
            case 'NICK':
                # Handle NICK message
                pass
            case 'NOTICE':
                print(message)
            case 'PART':
                # Handle PART message
                pass
            case 'PING':
                await self.chat_websocket.send('PONG')
            case 'PRIVMSG':
                self.manager.print.print_to_logs(
                    f"{message['tags']['display-name']}, {message['parameters'].strip('\r\n')}",
                    self.manager.print.BLUE)
                self.manager.print.print_to_logs(analyze_sentiment(message['parameters'].strip('\r\n')), self.manager.print.BLUE)
                display_message = format_message(message)
                self.manager.queue.put(display_message)
                if message['command'].get('botCommand'):
                    await handle_commands(self, message)
                # print(json.dumps(message, indent=4))
                # Handle PRIVMSG message
            case 'CLEARCHAT':
                # Handle CLEARCHAT message
                pass
            case 'CLEARMSG':
                # Handle CLEARMSG message
                pass
            case 'GLOBALUSERSTATE':
                # Handle GLOBALUSERSTATE message
                pass
            case 'HOSTTARGET':
                # Handle HOSTTARGET message
                pass
            case 'RECONNECT':
                # Handle RECONNECT message
                pass
            case 'ROOMSTATE':
                # Handle ROOMSTATE message
                pass
            case 'USERNOTICE':
                # Handle USERNOTICE message
                pass
            case 'USERSTATE':
                # Handle USERSTATE message
                pass
            case 'WHISPER':
                # Handle WHISPER message
                pass
            case _:
                # Handle unknown commands
                pass
        # print(json.dumps(message, indent=4))


async def handle_commands(self, message):
    command = message['command'].get('botCommand')
    if self.simple_commands.get(command):
        if is_user_allowed(self, message['tags'], self.simple_commands[command]['level']):
            answer = self.simple_commands[command]['message']
            answer = replace_keywords(answer, message)
            await send_message(self, answer)
    elif self.complex_commands.get(command):
        if is_user_allowed(self, message['tags'], self.complex_commands[command]['level']):
            func = getattr(self.twitch_commands, command)
            await func(
                message['command'].get('botCommandParams') if message['command'].get('botCommandParams') else None)


def is_user_allowed(self, author, level):
    match level:
        case 'BROADCASTER':
            if author['broadcaster']:
                return True
        case 'MOD':
            if author['mod'] or author['broadcaster']:
                return True
        case 'VIP':
            if author['vip'] or author['mod'] or author['broadcaster']:
                return True
        case 'SUB':
            if author['subscriber'] or author['vip'] or author['mod'] or author['broadcaster']:
                return True
        case _:
            return True

    # If none of the above cases match, it means the user is not allowed
    self.manager.print.print_to_logs(f'User {author.display_name} not allowed to run this command',
                                     self.manager.print.YELLOW)
    return False


def load_commands(self):
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            commands_json = json.load(f)
        load_simple_commands(self, commands_json=commands_json['simple'])
        set_complex_commands(self, commands_json=commands_json['complex'])
    else:
        self.manager.print.print_to_logs('Commands file not found', self.manager.print.RED)
        self.manager.print.print_to_logs('Creating new one with default commands', self.manager.print.WHITE)
        defaults = DEFAULT_COMMANDS
        for command in FUNCTION_LIST:
            defaults['complex'][command] = {}
            defaults['complex'][command]['enabled'] = True
            defaults['complex'][command]['level'] = 'ANY'
        with open('config/commands.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(defaults, indent=4))
        load_commands(self)


def load_simple_commands(self, commands_json):
    for command, context in commands_json.items():
        if context['enabled']:
            del context['enabled']
            # Use the command decorator to register the command
            self.simple_commands[command] = context
            self.manager.print.print_to_logs(f'Registered simple command {command}', self.manager.print.BRIGHT_PURPLE)


def set_complex_commands(self, commands_json):
    for command, context in commands_json.items():
        if context['enabled']:
            del context['enabled']
            self.complex_commands[command] = context
            self.manager.print.print_to_logs(f'Registered complex command {command}', self.manager.print.BRIGHT_PURPLE)


def replace_keywords(message: string, original_message):
    matches = re.findall(KEYWORD_PATTERN, message)
    if len(matches) > 0:
        for m in matches:
            match m:
                case 'sender':
                    return re.sub(KEYWORD_PATTERN, f"@{original_message['tags']['display-name']}", message)
    else:
        return message


def parse_message(message):
    parsed_message = {
        'tags': None,
        'source': None,
        'command': None,
        'parameters': None
    }

    idx = 0
    raw_tags_component = None
    raw_source_component = None
    raw_command_component = None
    raw_parameters_component = None

    if message[idx] == '@':
        end_idx = message.find(' ')
        raw_tags_component = message[1:end_idx]
        idx = end_idx + 1

    if message[idx] == ':':
        idx += 1
        end_idx = message.find(' ', idx)
        raw_source_component = message[idx:end_idx]
        idx = end_idx + 1

    end_idx = message.find(':', idx)
    if end_idx == -1:
        end_idx = len(message)

    raw_command_component = message[idx:end_idx].strip()

    if end_idx != len(message):
        idx = end_idx + 1
        raw_parameters_component = message[idx:]

    parsed_message['command'] = parse_command(raw_command_component)

    if parsed_message['command'] is None:
        return None
    else:
        if raw_tags_component is not None:
            parsed_message['tags'] = parse_tags(raw_tags_component)

        parsed_message['source'] = parse_source(raw_source_component)
        parsed_message['parameters'] = raw_parameters_component

        if raw_parameters_component and raw_parameters_component[0] == '!':
            parsed_message['command'] = parse_parameters(raw_parameters_component, parsed_message['command'])

    return parsed_message


def parse_tags(tags):
    tags_to_ignore = {
        'client-nonce': None,
        'flags': None
    }

    dict_parsed_tags = {}
    parsed_tags = tags.split(';')

    for tag in parsed_tags:
        parsed_tag = tag.split('=')
        tag_value = get_tag_value(parsed_tag)
        if parsed_tag[0] in tags_to_ignore:
            continue
        if parsed_tag[0] == 'badges' and parsed_tag[1]:
            parsed_tag_value = tag_value.split(',') if ',' in tag_value else tag_value
            dict_parsed_tags['broadcaster'] = 'broadcaster/1' in parsed_tag_value
        dict_parsed_tags[parsed_tag[0]] = tag_value
    if not dict_parsed_tags.get('vip'):
        dict_parsed_tags['vip'] = False
    if not dict_parsed_tags.get('broadcaster'):
        dict_parsed_tags['broadcaster'] = False
    return dict_parsed_tags


def get_tag_value(tag_value):
    if tag_value[1] == '':
        return None
    elif tag_value[1] == '0' or tag_value[1] == '1':
        return tag_value[1] == '1'
    return tag_value[1]


def parse_command(raw_command_component):
    command_parts = raw_command_component.split(' ')
    parsed_command = None

    if command_parts[0] in ['JOIN', 'PART', 'NOTICE', 'CLEARCHAT', 'HOSTTARGET', 'PRIVMSG']:
        parsed_command = {
            'command': command_parts[0],
            'channel': command_parts[1]
        }
    elif command_parts[0] == 'PING':
        parsed_command = {
            'command': command_parts[0]
        }
    # Add other command cases as needed

    return parsed_command


def parse_source(raw_source_component):
    if raw_source_component is None:
        return None
    else:
        source_parts = raw_source_component.split('!')
        return {
            'nick': source_parts[0] if len(source_parts) == 2 else None,
            'host': source_parts[1] if len(source_parts) == 2 else source_parts[0]
        }


def parse_parameters(raw_parameters_component, command):
    idx = 0
    command_parts = raw_parameters_component[idx + 1:].strip()
    params_idx = command_parts.find(' ')

    if params_idx == -1:
        command['botCommand'] = command_parts
    else:
        command['botCommand'] = command_parts[:params_idx]
        command['botCommandParams'] = command_parts[params_idx:].strip()

    return command


def retrieve_token_info(client_id, client_secret, code):
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': 'https://localhost:5000/callback_twitch'
    }
    response = requests.post(TWITCH_TOKEN_URL, data=payload, timeout=5)
    return response.json()


def refresh_access_token(refresh_token, client_id, client_secret):
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    }
    response = requests.post(TWITCH_TOKEN_URL, data=payload, timeout=5)
    return response.json()


async def refresh_twitch_token(self):
    response = refresh_access_token(self.configuration['twitch-token']['refresh_token'],
                                    self.configuration['twitch']['client_id'],
                                    self.configuration['twitch']['client_secret'])
    if 'access_token' in response:
        access_token = response.get('access_token')
        refresh_token = response.get('refresh_token')
        expires_in = response.get('expires_in')

        self.set_config('twitch-token', 'access_token', access_token)
        self.set_config('twitch-token', 'refresh_token', refresh_token)
        self.set_config('twitch-token', 'expires_in', str(expires_in))
        self.set_config('twitch-token', 'timestamp', str(int(time())))
    else:
        self.print.print_to_logs(f"Failed to refresh Twitch token: {response.status}", self.print.YELLOW)
        self.print.print_to_logs(f"Response: {response}", self.print.WHITE)
        await start_twitch_oauth_flow(self)


async def start_twitch_oauth_flow(self):
    self.print.print_to_logs('Re-Authorizing Twitch Bot...', self.print.YELLOW)
    params = {
        'client_id': self.configuration['twitch']['client_id'],
        'redirect_uri': 'https://localhost:5000/callback_twitch',
        'response_type': 'code',
        'scope': SCOPE_TWITCH
    }
    url = f"{TWITCH_AUTHORIZATION_URL}?{urlencode(params)}"
    wbopen(url)
    self.authentication_flag.set()
    await self.await_authentication()
