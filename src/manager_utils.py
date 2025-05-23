import json
import os
from datetime import datetime
from time import time

from werkzeug.datastructures import MultiDict

from twitch_ircchat_utils import COMMANDS_FILE

DEBUG = not os.path.exists('config/.debug')


class PrintColors:
    RED = '\033[38;5;203m'
    YELLOW = '\033[38;5;227m'
    GREEN = '\033[38;5;120m'
    WHITE = '\033[0m'
    BRIGHT_PURPLE = '\033[95m'
    BLUE = '\033[38;5;111m'
    ORANGE = '\033[38;5;214m'

    def __init__(self):
        self.log_queue = []
        if not os.path.exists('logs'):
            os.mkdir('logs')

    def print_to_logs(self, message, color):
        current_date = datetime.now().strftime('%d-%m-%Y')
        file_name = f"logs/logs-{current_date}.txt"
        if not os.path.exists(file_name):
            with open(file_name, 'w', encoding='utf-8'):
                pass
        if os.path.exists(file_name) and len(self.log_queue) > 0:
            for msg, msg_color in self.log_queue:
                new_print(msg, msg_color)
            self.log_queue = []
        new_print(message, color)


def new_print(message, color):
    # Get current timestamp in the specified format
    timestamp = datetime.now().strftime('%d/%m/%y - %H:%M')
    level = get_level_from_color(color)
    log_entry = f"{timestamp} | {level}: {message}\n"
    # Format the log entry
    message = f"{timestamp} | {color}{level}{PrintColors.WHITE}: {color}{message}{PrintColors.WHITE}"
    current_date = datetime.now().strftime('%d-%m-%Y')
    file_name = f"logs/logs-{current_date}.txt"
    print(message)
    # Open the log file and append the log entry
    with open(file_name, 'a', encoding='utf-8') as file:
        file.write(log_entry)


def get_level_from_color(color):
    match color:
        case PrintColors.RED:
            return 'ERROR'
        case PrintColors.YELLOW:
            return 'WARNING'
        case PrintColors.GREEN:
            return 'SUCCESS'
        case PrintColors.BRIGHT_PURPLE:
            return 'INFO'
        case PrintColors.BLUE:
            return 'MSG'
        case PrintColors.WHITE:
            return 'SYS'
        case PrintColors.ORANGE:
            return 'EVENT'


def save_configuration_to_json(self, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(self.configuration, f, indent=4)


def load_configuration_from_json(self, filename):
    with open(filename, 'r', encoding='utf-8') as f:
        self.configuration = json.load(f)
    # TODO: Remove this next version
    if 'spotify' in self.configuration and 'client_secret' in self.configuration['spotify']:
        del self.configuration['spotify']['client_secret']
    if 'spotify-token' in self.configuration and 'expires_at' in self.configuration['spotify-token']:
        del self.configuration['spotify-token']['expires_at']
    if 'twitch-token' in self.configuration and 'expires_at' in self.configuration['twitch-token']:
        del self.configuration['twitch-token']['expires_at']


def check_dict_structure(input_dict, sections):
    required_keys = {(section, item) for section, items in sections.items() for item in items}
    present_keys = {(section, item) for section, items in input_dict.items() for item in items if
                    items[item] is not None and items[item] != ''}
    missing_keys = required_keys - present_keys
    return missing_keys


def is_string_valid(string):
    return string and string is not None and string != ''


def return_date_string():
    return datetime.now().strftime('%d-%m-%Y')


def check_token_expiry(expires_in, timestamp):
    if is_string_valid(expires_in):
        expires_at = int(expires_in) + int(timestamp)
        return (expires_at < int(time())) or abs(int(time()) - expires_at) <= 120
    return True


def is_token_config_invalid(token):
    return (not is_string_valid(token['access_token'])
            or not is_string_valid(token['refresh_token'])
            or not is_string_valid(token['expires_in'])
            or not is_string_valid(token['timestamp']))


def reset_token_config(self):
    self.set_config('twitch-token', 'expires_in', '')
    self.set_config('twitch-token', 'access_token', '')
    self.set_config('twitch-token', 'refresh_token', '')
    self.set_config('twitch-token', 'timestamp', '')
    self.set_config('spotify-token', 'access_token', '')
    self.set_config('spotify-token', 'refresh_token', '')
    self.set_config('spotify-token', 'expires_in', '')
    self.set_config('spotify-token', 'timestamp', '')


def process_new_commands(form_data):
    replacement_names = [(key.split("_")[1], form_data[key].lower()) for key in form_data.keys() if key.startswith('simple_new command') and key.endswith("_name")]
    for old_name, new_name in replacement_names:
        new_command_keys = [(key, key.replace(key.split('_')[1], new_name.lower())) for key in form_data.keys() if
                            key.startswith(f'simple_{old_name}') and not key.endswith("_name")]
        # Update the keys in form_data
        for old_key, new_key in new_command_keys:
            form_data[new_key] = form_data.pop(old_key)
        form_data.pop(f'simple_{old_name}_name')
    return form_data


def process_form(form_data):
    commands = {}
    processed_data = MultiDict(form_data)
    processed_data = process_new_commands(processed_data)
    # Parse form data and update commands dictionary
    for key, value in processed_data.items():
        section, command_name, attribute = key.split('_')
        if section not in commands:
            commands[section] = {}

        # Initialize the second level of nesting
        if command_name not in commands[section]:
            commands[section][command_name] = {}
        if attribute in ['timeout', 'min-messages']:
            commands[section][command_name][attribute] = int(value)
        else:
            commands[section][command_name][attribute] = value
    for command_name, command_data in commands["simple"].items():
        # Check if the "enabled" key exists
        if "enabled" not in command_data:
            # If it doesn't exist, add it with the value "False"
            commands["simple"][command_name]["enabled"] = False
        else:
            commands["simple"][command_name]["enabled"] = True
    # Iterate over the "complex" section
    for command_name, command_data in commands["complex"].items():
        # Check if the "enabled" key exists
        if "enabled" not in command_data:
            # If it doesn't exist, add it with the value "False"
            commands["complex"][command_name]["enabled"] = False
        else:
            commands["complex"][command_name]["enabled"] = True
    print(json.dumps(commands, indent=4))
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        f.write(json.dumps(commands, indent=4))
