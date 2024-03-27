import configparser
from spotipy import SpotifyOAuth
from twitch import TwitchBot
from asyncio import create_task
from aiohttp import ClientSession
from webbrowser import open as wbopen
from time import time
from logger import print_to_logs, PrintColors

scope_spotify = "user-read-playback-state user-modify-playback-state"
SPOTIFY_AUTHORIZATION_URL = 'https://accounts.spotify.com/authorize'
OAUTH_SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
CONFIG_FILE = 'config.ini'


class Manager:
    def __init__(self):
        self.twitch_bot = {
            "task": None,
            "instance": None
        }
        self.quart = None
        self.updater = None

    @property
    def config(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        return config

    @property
    def auth_manager(self):
        return SpotifyOAuth(client_id=self.config.get('spotify', 'client_id', fallback=None),
                                         client_secret=self.config.get('spotify', 'client_secret', fallback=None),
                                         redirect_uri=self.config.get('spotify', 'redirect_uri', fallback=None),
                                         scope=scope_spotify)

    def create_new_bot(self):
        if self.twitch_bot["task"]:
            self.twitch_bot["task"] = None
        self.twitch_bot["instance"] = TwitchBot(self)
        self.twitch_bot["task"] = create_task(self.twitch_bot["instance"].start())

    def create_new_auth_manager(self):
        self.auth_manager = SpotifyOAuth(client_id=self.config.get('spotify', 'client_id', fallback=None),
                                         client_secret=self.config.get('spotify', 'client_secret', fallback=None),
                                         redirect_uri=self.config.get('spotify', 'redirect_uri', fallback=None),
                                         scope=scope_spotify)

    async def update_twitch_token(self):
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.config.get("twitch-token", "refresh_token"),
            'client_id': self.config.get("twitch", "client_id"),
            'client_secret': self.config.get("twitch", "client_secret"),
        }
        async with ClientSession() as session:
            response = await self.fetch(session, TWITCH_TOKEN_URL, data=params)
            if 'access_token' in response:
                access_token = response['access_token']
                refresh_token = response.get('refresh_token')
                expires_in = response.get('expires_in')
                expires_at = int(time()) + expires_in

                self.config.set("twitch-token", 'access_token', access_token)
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
        async with session.request('POST', url, data=data) as response:
            return await response.json()

    async def refresh_spotify_token(self):
        response = self.auth_manager.refresh_access_token(self.config.get('spotify-token', 'refresh_token'))
        if response is not None:
            access_token = response.get('access_token')
            refresh_token = response.get('refresh_token')
            expires_in = response.get('expires_in')
            expires_at = int(time()) + expires_in
            self.config.set("spotify-token", 'access_token', access_token)
            self.config.set("spotify-token", "refresh_token", refresh_token)
            self.config.set("spotify-token", "expires_at", str(expires_at))
            print_to_logs(f"New Token Acquired! {access_token}, {refresh_token}, {expires_at}",
                          PrintColors.BRIGHT_PURPLE)
        else:
            print_to_logs(f"Failed to refresh Spotify token: {response.status}", PrintColors.YELLOW)
            print_to_logs(f"Response: {response}", PrintColors.WHITE)
            self.start_spotify_oauth_flow()