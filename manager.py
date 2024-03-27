import configparser
import json
import secrets
import sys
import uvicorn
from datetime import datetime
from os import path, remove
from spotipy import SpotifyOAuth

from main import QuartServer
from twitch import TwitchBot
from asyncio import create_task
from aiohttp import ClientSession
from webbrowser import open as wbopen
from time import time
from logger import print_to_logs, PrintColors
from quart import Quart, request, redirect, session


# Files Location
COMMANDS_FILE = "commands.json"
QUEUE_FILE = "queue.json"
CONFIG_FILE = "config.ini"

# Necessary Links for authorization
SPOTIFY_AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
OAUTH_SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"

# Scopes
SCOPE_SPOTIFY = "user-read-playback-state user-modify-playback-state"


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
        self.startup_checks()
        self.quart.app.run()

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
            self.config.set("twitch-token", "expires_at", None)
            self.config.set("twitch-token", "access_token", None)
            self.config.set("twitch-token", "refresh_token", None)
            self.config.set("spotify-token", "access_token", None)
            self.config.set("spotify-token", "refresh_token", None)
            self.config.set("spotify-token", "expires_at", None)
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
        self.config.set("app", "secret_key", self.quart.app.secret_key)
        self.config.set("app", "last_opened", datetime.now().strftime("%d-%m-%Y"))
        self.config.add_section("twitch")
        self.config.set("twitch", "channel", None)
        self.config.set("twitch", "client_id", None)
        self.config.set("twitch", "client_secret", None)
        self.config.add_section("spotify")
        self.config.set("spotify", "client_id", None)
        self.config.set("spotify", "redirect_uri", None)
        self.config.set("spotify", "client_secret", None)
        self.config.add_section("twitch-token")
        self.config.set("spotify-token", "access_token", None)
        self.config.set("spotify-token", "refresh_token", None)
        self.config.set("spotify-token", "expires_at", None)
        self.config.add_section("spotify-token")
        self.config.set("twitch-token", "access_token", None)
        self.config.set("twitch-token", "refresh_token", None)
        self.config.set("twitch-token", "expires_at", None)
        self.setup()
        self.save_config()

    def setup(self):
        if self.config.get("twitch", "channel") is None:
            self.config.set("twitch", "channel", input("Enter the channel you want to join: "))
        if self.config.get("twitch", "client_id") is None:
            self.config.set("twitch", "client_id", input("Enter your Twitch client ID: "))
        if self.config.get("twitch", "client_secret") is None:
            self.config.set("twitch", "client_secret", input("Enter your Twitch client secret: "))
        if self.config.get("spotify", "redirect_uri") is None:
            self.config.set("spotify", "redirect_uri", "https://localhost:5000/callback")
        if self.config.get("spotify", "client_id") is None:
            self.config.set("spotify", "client_id", input("Enter your Spotify client ID: "))
        if self.config.get("spotify", "client_secret") is None:
            self.config.set("spotify", "client_secret", input("Enter your Spotify client secret: "))
        
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
        uvicorn_config = uvicorn.Config(app, host="localhost", port=5000,
                                        ssl_certfile=self.resource_path('localhost.ecc.crt'),
                                        ssl_keyfile=self.resource_path('localhost.ecc.key'),
                                        loop="asyncio", log_level="info")
        server = uvicorn.Server(config=uvicorn_config)

    @property
    def auth_manager(self):
        return SpotifyOAuth(client_id=self.config.get("spotify", "client_id", fallback=None),
                                         client_secret=self.config.get("spotify", "client_secret", fallback=None),
                                         redirect_uri=self.config.get("spotify", "redirect_uri", fallback=None),
                                         scope=SCOPE_SPOTIFY)

    def create_new_bot(self):
        if self.twitch_bot["task"]:
            self.twitch_bot["task"] = None
        self.twitch_bot["instance"] = TwitchBot(self)
        self.twitch_bot["task"] = create_task(self.twitch_bot["instance"].start())

    async def update_twitch_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self.config.get("twitch-token", "refresh_token"),
            "client_id": self.config.get("twitch", "client_id"),
            "client_secret": self.config.get("twitch", "client_secret"),
        }
        async with ClientSession() as session:
            response = await self.fetch(session, TWITCH_TOKEN_URL, data=params)
            if "access_token" in response:
                access_token = response["access_token"]
                refresh_token = response.get("refresh_token")
                expires_in = response.get("expires_in")
                expires_at = int(time()) + expires_in

                self.config.set("twitch-token", "access_token", access_token)
                self.config.set("twitch-token", "refresh_token", refresh_token)
                self.config.set("twitch-token", "expires_at", str(expires_at))
            else:
                raise Exception(f"Failed to refresh Twitch token: {response}")
        self.create_new_bot()

    def start_spotify_oauth_flow(self):
        auth_url = self.auth_manager.get_authorize_url()
        wbopen(auth_url)

    @staticmethod
    async def fetch(session, url, data=None):
        async with session.request("POST", url, data=data) as response:
            return await response.json()

    async def refresh_spotify_token(self):
        response = self.auth_manager.refresh_access_token(self.config.get("spotify-token", "refresh_token"))
        if response is not None:
            access_token = response.get("access_token")
            refresh_token = response.get("refresh_token")
            expires_in = response.get("expires_in")
            expires_at = int(time()) + expires_in
            self.config.set("spotify-token", "access_token", access_token)
            self.config.set("spotify-token", "refresh_token", refresh_token)
            self.config.set("spotify-token", "expires_at", str(expires_at))
            print_to_logs(f"New Token Acquired! {access_token}, {refresh_token}, {expires_at}",
                          PrintColors.BRIGHT_PURPLE)
            self.save_config()
        else:
            print_to_logs(f"Failed to refresh Spotify token: {response.status}", PrintColors.YELLOW)
            print_to_logs(f"Response: {response}", PrintColors.WHITE)
            self.start_spotify_oauth_flow()
