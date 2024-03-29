import configparser
import json
import secrets
import sys
from asyncio import create_task, run, CancelledError, sleep, current_task, gather, all_tasks
from contextlib import suppress
from datetime import datetime
from os import path, remove
from time import time
from urllib.parse import urlencode
from webbrowser import open as wbopen

import uvicorn
from aiohttp import ClientSession
from spotipy import SpotifyOAuth

from logger import print_to_logs, PrintColors
from main import QuartServer
from twitch import TwitchBot

# Files Location
COMMANDS_FILE = "commands.json"
QUEUE_FILE = "queue.json"
CONFIG_FILE = "config.ini"

# Necessary Links for authorization
SPOTIFY_AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
OAUTH_SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
TWITCH_AUTHORIZATION_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"

# Scopes
SCOPE_SPOTIFY = "user-read-playback-state user-modify-playback-state"
SCOPE_TWITCH = "chat:read chat:edit"


class Manager:
    def __init__(self):
        self.twitch_bot = {
            "task": None,
            "instance": None
        }
        self.quart = None
        self.updater = None
        self.quart = QuartServer(self)
        self.config = configparser.ConfigParser()
        self.configuration = {
            "app": {
                "secret_key": "",
                "last_opened": ""
            },
            "twitch": {
                "channel": "",
                "client_id": "",
                "client_secret": ""
            },
            "spotify": {
                "client_id": "",
                "client_sectet": "",
                "redirect_uri": ""
            },
            "twitch-token": {
                "access_token": "",
                "refresh_token": "",
                "expires_at": ""
            },
            "spotify-token": {
                "access_token": "",
                "refresh_token": "",
                "expires_at": ""
            }
        }
        self.tasks = {
            "bot": None,
            "quart": None,
            "updater": None
        }
        self.startup_checks()

    def startup_checks(self):
        print_to_logs("Checking config file existence", PrintColors.BRIGHT_PURPLE)
        if path.exists(CONFIG_FILE):
            print_to_logs("Config found! Loading configuration...", PrintColors.GREEN)
            self.config.read(CONFIG_FILE)
            self.import_configuration()
            print_to_logs("Configuration Loaded", PrintColors.GREEN)
        else:
            print_to_logs("Config file not found!", PrintColors.RED)
            print_to_logs("Creating new one and generating Quart app secret..", PrintColors.YELLOW)
            self.generate_config_file()
            print_to_logs("Quart app secret and configuration file created", PrintColors.GREEN)

        filename = f"logs-{datetime.now().strftime('%d-%m-%Y')}.txt"
        if not path.exists(filename):
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"LOGS CREATION - {filename}\n")
            print_to_logs("New Logs generated!", PrintColors.YELLOW)
            self.set_config("twitch-token", "expires_at", None)
            self.set_config("twitch-token", "access_token", None)
            self.set_config("twitch-token", "refresh_token", None)
            self.set_config("spotify-token", "access_token", None)
            self.set_config("spotify-token", "refresh_token", None)
            self.set_config("spotify-token", "expires_at", None)
            self.save_config()

        print_to_logs("Checking for queue existence...", PrintColors.BRIGHT_PURPLE)
        if path.exists(QUEUE_FILE):
            remove(QUEUE_FILE)
            print_to_logs("Cleared queue", PrintColors.BRIGHT_PURPLE)

        print_to_logs("Checking commands file existence", PrintColors.BRIGHT_PURPLE)
        if path.exists(COMMANDS_FILE):
            print_to_logs("Commands found! Loading...", PrintColors.GREEN)
        else:
            print_to_logs("Commands file not found", PrintColors.RED)
            print_to_logs("Creating new one with no commands", PrintColors.WHITE)
            with open("commands.json", "w", encoding="utf-8") as f:
                f.write(json.dumps({"example": "[sender] this is an example command"}))

    def generate_config_file(self):
        self.quart.app.secret_key = secrets.token_hex(16)
        self.config.add_section("app")
        self.set_config("app", "secret_key", self.quart.app.secret_key)
        self.set_config("app", "last_opened", datetime.now().strftime("%d-%m-%Y"))
        self.config.add_section("twitch")
        self.set_config("twitch", "channel", None)
        self.set_config("twitch", "client_id", None)
        self.set_config("twitch", "client_secret", None)
        self.config.add_section("spotify")
        self.set_config("spotify", "client_id", None)
        self.set_config("spotify", "redirect_uri", None)
        self.set_config("spotify", "client_secret", None)
        self.config.add_section("twitch-token")
        self.set_config("spotify-token", "access_token", None)
        self.set_config("spotify-token", "refresh_token", None)
        self.set_config("spotify-token", "expires_at", None)
        self.config.add_section("spotify-token")
        self.set_config("twitch-token", "access_token", None)
        self.set_config("twitch-token", "refresh_token", None)
        self.set_config("twitch-token", "expires_at", None)
        self.setup()
        self.save_config()

    def setup(self):
        if self.configuration["twitch"]["channel"] is None:
            self.set_config("twitch", "channel", input("Enter the channel you want to join: "))
        if self.configuration["twitch"]["client_id"] is None:
            self.set_config("twitch", "client_id", input("Enter your Twitch client ID: "))
        if self.configuration["twitch"]["client_secret"] is None:
            self.set_config("twitch", "client_secret", input("Enter your Twitch client secret: "))
        if self.configuration["spotify"]["redirect_uri"] is None:
            self.set_config("spotify", "redirect_uri", "https://localhost:5000/callback")
        if self.configuration["spotify"]["client_id"] is None:
            self.set_config("spotify", "client_id", input("Enter your Spotify client ID: "))
        if self.configuration["spotify"]["client_secret"] is None:
            self.set_config("spotify", "client_secret", input("Enter your Spotify client secret: "))

    def import_configuration(self):
        self.configuration = {
            "app": {
                "secret_key": self.config.get("app", "secret_key", fallback=None),
                "last_opened": self.config.get("app", "last_opened", fallback=None)
            },
            "twitch": {
                "channel": self.config.get("twitch", "channel", fallback=None),
                "client_id": self.config.get("twitch", "client_id", fallback=None),
                "client_secret": self.config.get("twitch", "client_secret", fallback=None),
            },
            "spotify": {
                "client_id": self.config.get("spotify", "client_id", fallback=None),
                "client_secret": self.config.get("spotify", "client_secret", fallback=None),
                "redirect_uri": self.config.get("spotify", "redirect_uri", fallback="https://localhost:5000/callback"),
            },
            "twitch-token": {
                "access_token": self.config.get("twitch-token", "access_token", fallback=None),
                "refresh_token": self.config.get("twitch-token", "refresh_token", fallback=None),
                "expires_at": self.config.get("twitch-token", "expires_at", fallback=None),
            },
            "spotify-token": {
                "access_token": self.config.get("spotify-token", "access_token", fallback=None),
                "refresh_token": self.config.get("spotify-token", "refresh_token", fallback=None),
                "expires_at": self.config.get("spotify-token", "expires_at", fallback=None),
            }
        }

    def set_config(self, section, key, value):
        self.config.set(section, key, value)
        self.configuration[section][key] = value
        print_to_logs(f"Set {section}/{key} in configuration", PrintColors.GREEN)

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            self.config.write(configfile)
        print_to_logs("Configuration saved", PrintColors.BRIGHT_PURPLE)

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = path.abspath(".")

        return str(path.join(base_path, relative_path))

    def start_server(self):
        uvicorn_config = uvicorn.Config(self.quart.app, host="localhost", port=5000,
                                        ssl_certfile=self.resource_path("localhost.ecc.crt"),
                                        ssl_keyfile=self.resource_path("localhost.ecc.key"),
                                        loop="asyncio", log_level="info")
        return uvicorn.Server(config=uvicorn_config).serve()

    @property
    def auth_manager(self):
        return SpotifyOAuth(client_id=self.configuration["spotify"]["client_id"],
                            client_secret=self.configuration["spotify"]["client_secret"],
                            redirect_uri=self.configuration["spotify"]["redirect_uri"],
                            scope=SCOPE_SPOTIFY)

    async def create_new_bot(self):
        if self.tasks["bot"] is not None:
            self.tasks["bot"].cancel()
            try:
                await self.tasks["bot"]
            except CancelledError:
                pass
        return TwitchBot(self).start()

    async def update_twitch_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self.config.get("twitch-token", "refresh_token"),
            "client_id": self.config.get("twitch", "client_id"),
            "client_secret": self.config.get("twitch", "client_secret"),
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

    def start_spotify_oauth_flow(self):
        auth_url = self.auth_manager.get_authorize_url()
        wbopen(auth_url)

    async def refresh_spotify_token(self):
        response = self.auth_manager.refresh_access_token(self.config.get("spotify-token", "refresh_token"))
        if response is not None:
            access_token = response.get("access_token")
            refresh_token = response.get("refresh_token")
            expires_in = response.get("expires_in")
            expires_at = int(time()) + expires_in
            self.set_config("spotify-token", "access_token", access_token)
            self.set_config("spotify-token", "refresh_token", refresh_token)
            self.set_config("spotify-token", "expires_at", str(expires_at))
            print_to_logs(f"New Token Acquired! {access_token}, {refresh_token}, {expires_at}",
                          PrintColors.BRIGHT_PURPLE)
            self.save_config()
        else:
            print_to_logs(f"Failed to refresh Spotify token: {response.status}", PrintColors.YELLOW)
            print_to_logs(f"Response: {response}", PrintColors.WHITE)
            self.start_spotify_oauth_flow()

    async def check_spotify(self):
        if (self.configuration["spotify-token"]["expires_at"] is None or
                self.configuration["spotify-token"]["refresh_token"] is None or
                self.configuration["spotify-token"]["access_token"] is None):
            print_to_logs("No Token", PrintColors.RED)
            self.start_spotify_oauth_flow()
        elif (self.configuration["spotify-token"]["expires_at"] and
              int(time()) - int(self.configuration["spotify-token"]["expires_at"]) < 300):
            print_to_logs("Expired Spotify Token", PrintColors.YELLOW)
            await self.refresh_spotify_token()
            self.save_config()
        else:
            print_to_logs("Spotify is OK!", PrintColors.GREEN)

    async def check_twitch(self):
        if self.tasks["bot"] is None:
            print_to_logs("No bot istance", PrintColors.RED)
            await self.create_new_bot()
        else:
            access_token = self.configuration["twitch-token"]["access_token"]
            refresh_token = self.configuration["twitch-token"]["refresh_token"]
            expires_at = self.configuration["twitch-token"]["expires_at"]
            if expires_at and expires_at != "" and expires_at != "None" and int(time()) - int(expires_at) < 300:
                print_to_logs("Expired Twitch Token", PrintColors.YELLOW)
                await self.update_twitch_token()
                self.save_config()
                await self.create_new_bot()
            elif ((not access_token or access_token == "" or access_token == "None") or
                  (not refresh_token or refresh_token == "" or refresh_token == "None") or
                  (not expires_at or expires_at == "" or expires_at == "None")):
                print_to_logs("Twitch token configuration missing. Retrieving...", PrintColors.RED)
                self.start_twitch_oauth_flow()
                print_to_logs("Re-Authorizing Twitch Bot...", PrintColors.YELLOW)
            else:
                print_to_logs("Twitch is OK!", PrintColors.GREEN)

    def start_twitch_oauth_flow(self):
        params = {
            "client_id": self.configuration["twitch"]["client_id"],
            "redirect_uri": "https://localhost:5000/callback_twitch",
            "response_type": "code",
            "scope": SCOPE_TWITCH
        }
        url = f"{TWITCH_AUTHORIZATION_URL}?{urlencode(params)}"
        wbopen(url)

    async def core_loop(self):
        while not current_task().cancelled():
            # Twitch check
            print_to_logs("Twitch sanity check!", PrintColors.BRIGHT_PURPLE)
            await self.check_twitch()
            await sleep(1)
            # Spotify check
            print_to_logs("Spotify sanity check!", PrintColors.BRIGHT_PURPLE)
            await self.check_spotify()

            await sleep(300)

    async def shutdown(self):
        """Gracefully shut down all tasks and save configurations."""
        print_to_logs("Initiating shutdown...", PrintColors.BRIGHT_PURPLE)
        self.save_config()
        for task in all_tasks():
            task.cancel()
            with suppress(CancelledError):
                await task
        print_to_logs("Cleanup complete. Exiting...", PrintColors.BRIGHT_PURPLE)

    async def main(self):
        try:
            self.tasks["quart"] = create_task(self.start_server())
            self.tasks["bot"] = create_task(self.create_new_bot())
            self.tasks["updater"] = create_task(self.core_loop())
            tasks = [self.tasks["quart"], self.tasks["bot"], self.tasks["updater"]]
            await gather(*tasks)
        except KeyboardInterrupt:
            await self.shutdown()


if __name__ == "__main__":
    manager = Manager()
    run(manager.main())
