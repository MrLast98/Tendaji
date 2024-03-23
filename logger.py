import os
from datetime import datetime


debug = not os.path.exists(".debug")


class PrintColors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    WHITE = '\033[0m'
    BRIGHT_PURPLE = '\033[95m'


def print_to_logs(message, color):
    current_date = datetime.now().strftime("%d-%m-%Y")
    file_name = f"logs-{current_date}.txt"
    if not os.path.exists(file_name):
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(f"LOGS CREATION - {file_name}")
        print_to_logs(f"LOGS CREATED  - {file_name}", PrintColors.YELLOW)

    # Get current timestamp in the specified format
    timestamp = datetime.now().strftime('%d/%m/%y - %H:%M')
    # Format the log entry
    log_entry = f"{timestamp}: {color}{message}{PrintColors.WHITE}\n"
    if debug:
        print(log_entry.strip("\n"))
    # Open the log file and append the log entry
    with open("logs.txt", 'a', encoding='utf-8') as file:
        file.write(log_entry)
