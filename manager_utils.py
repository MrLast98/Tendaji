import json
import os
from datetime import datetime

DEBUG = not os.path.exists("config/.debug")


class PrintColors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    WHITE = '\033[0m'
    BRIGHT_PURPLE = '\033[95m'
    BLUE = '\033[95m'

    def __init__(self):
        self.log_queue = []
        if not os.path.exists("logs"):
            os.mkdir("logs")

    def print_to_logs(self, message, color):
        current_date = datetime.now().strftime("%d-%m-%Y")
        file_name = f"logs/logs-{current_date}.txt"
        # check_log_file()
        if not os.path.exists(file_name):
            if len(self.log_queue) == 0:
                self.log_queue.append((f"LOGS CREATED  - {file_name}", PrintColors.YELLOW))
            self.log_queue.append((message, color))
            return
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
    current_date = datetime.now().strftime("%d-%m-%Y")
    file_name = f"logs/logs-{current_date}.txt"
    # if DEBUG:
    print(message)
    # Open the log file and append the log entry
    with open(file_name, 'a', encoding='utf-8') as file:
        file.write(log_entry)


def get_level_from_color(color):
    match color:
        case PrintColors.RED:
            return "ERROR"
        case PrintColors.YELLOW:
            return "WARNING"
        case PrintColors.GREEN:
            return "SUCCESS"
        case PrintColors.BRIGHT_PURPLE:
            return "INFO"
        case PrintColors.BLUE:
            return "MSG"
        case PrintColors.WHITE:
            return "SYS"


def save_configuration_to_json(self, filename):
    with open(filename, 'w') as f:
        json.dump(self.configuration, f, indent=4)


def load_configuration_from_json(self, filename):
    with open(filename, 'r') as f:
        self.configuration = json.load(f)
    # TODO: Remove this next version
    if "spotify" in self.configuration and "client_secret" in self.configuration["spotify"]:
        del self.configuration["spotify"]["client_secret"]


def check_dict_structure(input_dict, sections):
    required_keys = {(section, item) for section, items in sections.items() for item in items}
    present_keys = {(section, item) for section, items in input_dict.items() for item in items if
                    items[item] is not None and items[item] != ""}
    missing_keys = required_keys - present_keys
    return missing_keys


def is_string_valid(string):
    return string and string is not None and string != ""


def return_date_string():
    return datetime.now().strftime("%d-%m-%Y")
