import os
from datetime import datetime


debug = not os.path.exists(".debug")
log_queue = []


class PrintColors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    WHITE = '\033[0m'
    BRIGHT_PURPLE = '\033[95m'
    BLUE = '\033[95m'


def print_to_logs(message, color):
    global log_queue
    current_date = datetime.now().strftime("%d-%m-%Y")
    file_name = f"logs-{current_date}.txt"
    # check_log_file()
    if not os.path.exists(file_name):
        if len(log_queue) == 0:
            log_queue.append((f"LOGS CREATED  - {file_name}", PrintColors.YELLOW))
        log_queue.append((message, color))
        return
    elif os.path.exists(file_name) and len(log_queue) > 0:
        for msg, msg_color in log_queue:
            new_print(msg, msg_color)
        log_queue = []
    new_print(message, color)


def new_print(message, color):
    # Get current timestamp in the specified format
    timestamp = datetime.now().strftime('%d/%m/%y - %H:%M')
    level = get_level_from_color(color)
    log_entry = f"{timestamp} | {level}: {message}\n"
    # Format the log entry
    message = f"{timestamp} | {color}{level}{PrintColors.WHITE}: {color}{message}{PrintColors.WHITE}"
    current_date = datetime.now().strftime("%d-%m-%Y")
    file_name = f"logs-{current_date}.txt"
    if debug:
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
