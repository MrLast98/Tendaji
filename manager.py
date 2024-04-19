import json
import secrets
import sys
from asyncio import create_task, run, CancelledError, sleep, gather, all_tasks, Event
from os import path, remove, mkdir
from time import time
from urllib.parse import urlencode
from webbrowser import open as wbopen

import uvicorn
from aiohttp import ClientSession

from manager_utils import PrintColors, load_configuration_from_json, save_configuration_to_json, return_date_string, \
    check_dict_structure, is_string_valid
from quart_server import QuartServer
from spotify import get_authorization_code, generate_code_verifier_and_challenge, refresh_access_token
from translations import TranslationManager
from twitch import TwitchBot

# pyinstaller --onefile --add-data "localhost.ecc.crt;." --add-data "localhost.ecc.key;." manager.py


# Files Location
COMMANDS_FILE = "config/commands.json"
QUEUE_FILE = "queue.json"
CONFIG_FILE = "config/config.json"

# Necessary Links for authorization
TWITCH_AUTHORIZATION_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"

# Scopes
SCOPE_SPOTIFY = "user-read-playback-state user-modify-playback-state"
SCOPE_TWITCH = "chat:read chat:edit"


class Manager:
    def __init__(self):
        self.quart = None
        self.updater = None
        self.bot = None
        self.verify = None
        self.configuration = {
            "app": {
                "last_opened": None,
                "selected_language": None
            },
            "twitch": {
                "channel": None,
                "client_id": None,
                "client_secret": None
            },
            "spotify": {
                "client_id": None,
                "redirect_uri": None
            },
            "twitch-token": {
                "access_token": None,
                "refresh_token": None,
                "expires_at": None
            },
            "spotify-token": {
                "access_token": None,
                "refresh_token": None,
                "expires_at": None
            }
        }
        self.tasks = {
            "bot": None,
            "quart": None,
            "updater": None
        }
        self.translation_manager = TranslationManager(self)
        self.authentication_flag = Event()
        self.shutdown_flag = Event()
        self.quart = QuartServer(self)
        self.print = PrintColors()
        self.startup_checks()

    def startup_checks(self):
        if not path.exists("config"):
            self.print.print_to_logs("Creating new config folder", self.print.YELLOW)
            mkdir("config")

        self.print.print_to_logs("Checking config file existence", self.print.BRIGHT_PURPLE)
        if path.exists(f"{CONFIG_FILE}"):
            self.print.print_to_logs("Config found! Loading configuration...", self.print.GREEN)
            load_configuration_from_json(self, CONFIG_FILE)
        else:
            self.print.print_to_logs("Config file not found!", self.print.RED)
            self.print.print_to_logs("Creating new one and generating Quart app secret..", self.print.YELLOW)
            self.save_config()

        self.setup()
        # self.save_config()
        self.print.print_to_logs("Configuration Loaded", self.print.GREEN)
        self.print.print_to_logs("Wanna reset the tokens?[Y/]", self.print.WHITE)
        i = input("> ")
        if "y" in i.lower():
            with open(CONFIG_FILE, 'r', encoding="utf-8") as f:
                data = json.load(f)

            # Reset tokens to empty strings
            self.set_config("twitch-token", "expires_at", "")
            self.set_config("twitch-token", "access_token", "")
            self.set_config("twitch-token", "refresh_token", "")
            self.set_config("spotify-token", "access_token", "")
            self.set_config("spotify-token", "refresh_token", "")
            self.set_config("spotify-token", "expires_at", "")
            self.print.print_to_logs("Token for Spotify and Twitch correctly reset!", self.print.GREEN)
            # Write the updated data back to the file
            with open(CONFIG_FILE, 'w', encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        filename = f"logs/logs-{return_date_string()}.txt"
        if not path.exists(filename) and "y" not in i.lower():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"LOGS CREATION - {filename}\n")
            self.print.print_to_logs("New Logs generated!", self.print.YELLOW)
            self.set_config("twitch-token", "expires_at", "")
            self.set_config("twitch-token", "access_token", "")
            self.set_config("twitch-token", "refresh_token", "")
            self.set_config("spotify-token", "access_token", "")
            self.set_config("spotify-token", "refresh_token", "")
            self.set_config("spotify-token", "expires_at", "")
            self.save_config()

        self.print.print_to_logs("Checking for queue existence...", self.print.BRIGHT_PURPLE)
        if path.exists(QUEUE_FILE):
            remove(QUEUE_FILE)
            self.print.print_to_logs("Cleared queue", self.print.BRIGHT_PURPLE)


    def setup(self):
        sections = {
            "app": ["last_opened", "selected_language"],
            "twitch": ["channel", "client_id", "client_secret"],
            "spotify": ["client_id", "redirect_uri"],
            "twitch-token": ["access_token", "refresh_token", "expires_at"],
            "spotify-token": ["access_token", "refresh_token", "expires_at"]
        }

        missing_keys = check_dict_structure(self.configuration, sections)
        if len(missing_keys) > 0:
            for section, item in missing_keys:
                match item:
                    case "last_opened":
                        self.configuration[section][item] = return_date_string()
                    case "redirect_uri":
                        self.configuration[section][item] = "https://localhost:5000/callback"
                    case "selected_language":
                        self.configuration[section][item] = "en"
                    case _:
                        if section in ('twitch', 'spotify'):
                            question = self.translation_manager.get_translation("insert_missing_configuration")
                            section_name = self.translation_manager.get_dictionary(section)
                            item_name = self.translation_manager.get_dictionary(item)
                            value = input(f"{question}{section_name} {item_name}: ")
                            self.configuration[section][item] = value
                        else:
                            self.configuration[section][item] = ""

    def set_config(self, section, key, value):
        self.configuration[section][key] = value
        self.print.print_to_logs(f"Set {section}/{key} in configuration", self.print.GREEN)

    def save_config(self):
        save_configuration_to_json(self, CONFIG_FILE)
        self.print.print_to_logs("Configuration saved", self.print.BRIGHT_PURPLE)

    def read_config(self):
        load_configuration_from_json(self, CONFIG_FILE)
        self.print.print_to_logs("Configuration loaded", self.print.BRIGHT_PURPLE)

    async def await_authentication(self):
        while self.authentication_flag.is_set():
            await sleep(1)
        self.print.print_to_logs("Authentication completed!", self.print.GREEN)

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = path.abspath(".")

        return str(path.join(base_path, relative_path))

    def create_server(self):
        self.quart.app.secret_key = secrets.token_hex(64)
        uvicorn_config = uvicorn.Config(self.quart.app, host="localhost", port=5000,
                                        ssl_certfile=self.resource_path("localhost.ecc.crt"),
                                        ssl_keyfile=self.resource_path("localhost.ecc.key"),
                                        loop="asyncio", log_level="info")
        server = uvicorn.Server(config=uvicorn_config)
        self.tasks["quart"] = create_task(server.serve())

    async def create_new_bot(self):
        if self.bot is not None and self.tasks["bot"] is not None:
            self.print.print_to_logs("Shutting down task", self.print.YELLOW)
            try:
                await self.bot.close()
                await self.tasks["bot"]
            except CancelledError:
                pass
        self.bot = TwitchBot(self)
        self.tasks["bot"] = create_task(self.bot.start())

    async def update_twitch_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self.configuration["twitch-token"]["refresh_token"],
            "client_id": self.configuration["twitch"]["client_id"],
            "client_secret": self.configuration["twitch"]["client_secret"],
        }
        async with ClientSession() as session:
            async with session.request("POST", TWITCH_TOKEN_URL, data=params) as response:
                response = await response.json()
            if "access_token" in response:
                access_token = response["access_token"]
                refresh_token = response.get("refresh_token")
                expires_in = response.get("expires_in")
                expires_at = int(time()) + expires_in

                self.set_config("twitch-token", "access_token", access_token)
                self.set_config("twitch-token", "refresh_token", refresh_token)
                self.set_config("twitch-token", "expires_at", str(expires_at))
            else:
                raise Exception(f"Failed to refresh Twitch token: {response}")

    async def start_spotify_oauth_flow(self):
        self.verify, challenge = generate_code_verifier_and_challenge()
        auth_url = get_authorization_code(self.configuration["spotify"]["client_id"], self.configuration["spotify"]["redirect_uri"], challenge, self.quart.app.secret_key)
        wbopen(auth_url)
        self.authentication_flag.set()
        await self.await_authentication()

    async def refresh_spotify_token(self):
        response = refresh_access_token(self.configuration["spotify"]["client_id"], self.configuration["spotify-token"]["refresh_token"])
        if response:
            access_token = response.get("access_token")
            refresh_token = response.get("refresh_token")
            expires_in = response.get("expires_in")
            expires_at = int(time()) + expires_in
            self.set_config("spotify-token", "access_token", access_token)
            self.set_config("spotify-token", "refresh_token", refresh_token)
            self.set_config("spotify-token", "expires_at", str(expires_at))
            self.save_config()
        else:
            self.print.print_to_logs(f"Failed to refresh Spotify token: {response.status}", self.print.YELLOW)
            self.print.print_to_logs(f"Response: {response}", self.print.WHITE)
            await self.start_spotify_oauth_flow()

    async def start_twitch_oauth_flow(self):
        self.print.print_to_logs("Re-Authorizing Twitch Bot...", self.print.YELLOW)
        params = {
            "client_id": self.configuration["twitch"]["client_id"],
            "redirect_uri": "https://localhost:5000/callback_twitch",
            "response_type": "code",
            "scope": SCOPE_TWITCH
        }
        url = f"{TWITCH_AUTHORIZATION_URL}?{urlencode(params)}"
        wbopen(url)
        self.authentication_flag.set()
        await self.await_authentication()

    async def check_spotify(self):
        if (not is_string_valid(self.configuration["spotify-token"]["expires_at"]) or
                not is_string_valid(self.configuration["spotify-token"]["refresh_token"]) or
                not is_string_valid(self.configuration["spotify-token"]["access_token"])):
            self.print.print_to_logs("No Token", self.print.RED)
            await self.start_spotify_oauth_flow()
            self.save_config()
        elif (is_string_valid(self.configuration["spotify-token"]["expires_at"]) and (
                int(self.configuration["spotify-token"]["expires_at"]) < int(time())) or
              abs(int(time()) - int(self.configuration["spotify-token"]["expires_at"])) <= 300):
            self.print.print_to_logs("Expired Spotify Token", self.print.YELLOW)
            await self.refresh_spotify_token()
            self.save_config()
        else:
            self.print.print_to_logs("Spotify is OK!", self.print.GREEN)

    async def check_twitch(self):
        if (not is_string_valid(self.configuration["twitch-token"]["access_token"]) or
                not is_string_valid(self.configuration["twitch-token"]["refresh_token"]) or
                not is_string_valid(self.configuration["twitch-token"]["expires_at"])):
            self.print.print_to_logs("Twitch token missing. Retrieving...", self.print.RED)
            await self.start_twitch_oauth_flow()
            self.save_config()
            await self.create_new_bot()
        elif (is_string_valid(self.configuration["twitch-token"]["expires_at"]) and (
                int(self.configuration["twitch-token"]["expires_at"]) < int(time())) or
              abs(int(time()) - int(self.configuration["twitch-token"]["expires_at"])) <= 300):
            self.print.print_to_logs("Expired Twitch Token", self.print.YELLOW)
            await self.update_twitch_token()
            self.save_config()
            await self.create_new_bot()
        else:
            self.print.print_to_logs("Twitch is OK!", self.print.GREEN)

    async def check_tokens(self):
        # Twitch check
        self.print.print_to_logs("Twitch sanity check!", self.print.BRIGHT_PURPLE)
        await self.check_twitch()
        # Spotify check
        self.print.print_to_logs("Spotify sanity check!", self.print.BRIGHT_PURPLE)
        await self.check_spotify()

    async def shutdown(self):
        if self.shutdown_flag.is_set():
            return  # Shutdown already initiated, do nothing
        self.shutdown_flag.set()  # Set the flag to indicate shutdown has started
        self.print.print_to_logs("Initiating shutdown...", self.print.BRIGHT_PURPLE)
        # Cancel all tasks
        for task in all_tasks():
            task.cancel()
        # Await all tasks to ensure they complete their cleanup
        await gather(*all_tasks(), return_exceptions=True)
        # Perform any additional cleanup here
        self.save_config()
        self.print.print_to_logs("Cleanup complete. Exiting...", self.print.BRIGHT_PURPLE)

    async def core_loop(self):
        while not self.shutdown_flag.is_set():
            await sleep(300)
            await self.check_tokens()

    async def main(self):
        self.create_server()
        await self.check_tokens()
        await self.create_new_bot()
        self.tasks["updater"] = create_task(self.core_loop())
        tasks = [self.tasks["quart"], self.tasks["updater"], self.tasks["bot"]]
        await gather(*tasks)

        # except Exception as e:
        #     self.print.print_to_logs(e, PrintColors.RED)
        #     await self.shutdown()


if __name__ == "__main__":
    manager = Manager()
    try:
        run(manager.main())
    except KeyboardInterrupt:
        manager.shutdown()
    finally:
        manager.shutdown()