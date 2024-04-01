import configparser
import json
import os
import manager_utils
from time import time
from datetime import datetime

from quart import Quart, request, redirect, session
from requests import post
from twitch import print_queue_to_file

# Configuration and Flask App
CONFIG_FILE = 'config/config.json'
COMMANDS_FILE = 'config/commands.json'
QUEUE_FILE = 'queue.json'
config = configparser.ConfigParser()
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


def update_queue(track_name, artist_name):
    with open("queue.json", "r", encoding="utf-8") as f:
        queue = json.loads(f.read())
    while queue and queue[0]["title"] != track_name and queue[0]["author"] != artist_name and len(queue) > 0:
        queue.pop(0)
    print_queue_to_file(queue)


#
#
# def signal_handler(loop):
#     """Initiates the shutdown process."""
#     print_to_logs("Signal received, shutting down.")
#     for task in asyncio.all_tasks(loop):
#         task.cancel()
#     asyncio.ensure_future(shutdown())


class QuartServer:
    def __init__(self, manager):
        self.app = Quart(__name__)
        self.app.add_url_rule("/", view_func=self.index)
        self.app.add_url_rule("/callback", view_func=self.callback)
        self.app.add_url_rule("/callback_twitch", view_func=self.callback_twitch)
        self.app.add_url_rule("/currently_playing", view_func=self.currently_playing)
        self.manager = manager

    def retrieve_token_info(self, code):
        payload = {
            'client_id': self.manager.configuration['twitch']['client_id'],
            'client_secret': self.manager.configuration['twitch']['client_secret'],
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://localhost:5000/callback_twitch'
        }
        response = post(TWITCH_TOKEN_URL, data=payload)
        response_json = response.json()
        access_token = response_json.get('access_token')
        refresh_token = response_json.get('refresh_token')
        expires_in = response_json.get('expires_in')
        # Calculate the expiration timestamp and save it
        expires_at = int(time()) + expires_in
        return access_token, refresh_token, expires_at

    async def index(self):
        return redirect("/currently_playing")

    async def callback(self):
        token = self.manager.auth_manager.get_access_token(request.args['code'])
        if token:
            session['token_info'] = token
            self.manager.set_config('spotify-token', 'access_token', token['access_token'])
            self.manager.set_config('spotify-token', 'refresh_token', token.get('refresh_token'))
            self.manager.set_config('spotify-token', 'expires_at', str(token['expires_at']))
            self.manager.save_config()
            return redirect("/currently_playing")
        else:
            error = "Error retrieving tokens"
            f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Error Occurred</title>
                </head>
                <body>
                    <p>Error: {error}</p>
                </body>
                </html>
                '''

    async def callback_twitch(self):
        access_token, refresh_token, expires_at = self.retrieve_token_info(request.args.get('code'))

        # Save the access token, refresh token, and expiration timestamp
        if access_token and refresh_token and expires_at:
            self.manager.set_config('twitch-token', 'access_token', access_token)
            self.manager.set_config('twitch-token', 'refresh_token', refresh_token)
            self.manager.set_config('twitch-token', 'expires_at', str(expires_at))
            self.manager.save_config()
            return '''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Process Complete</title>
                </head>
                <body>
                    <p>You can close this window.</p>
                </body>
                </html>
            '''
        else:
            return '''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Error Occurred</title>
                </head>
                <body>
                    <p>Error: "Error retrieving tokens"</p>
                </body>
                </html>
            '''

    async def currently_playing(self):
        sp, _ = await self.manager.bot.get_player()
        if sp is not None:
            track = sp.current_playback()
            if track is not None:
                track_name = track['item']['name']
                artist_name = track['item']['artists'][0]['name']

                album_name = track['item']['album']['name']
                album_image_url = track['item']['album']['images'][0]['url'] if track['item']['album'][
                    'images'] else "No image available"
                track_duration = int(track['item']["duration_ms"])
                progress = int(track["progress_ms"])
                if track_duration - progress >= 30000:
                    refresh_rate = 30
                else:
                    refresh_rate = (track_duration - progress) / 1000 + 1  # Convert to seconds and add 1
                    if os.path.exists(QUEUE_FILE):
                        update_queue(track_name, artist_name)
                next_refresh = int(time()) + refresh_rate
                html_content = f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Currently Playing</title>
                    <meta http-equiv="refresh" content="{refresh_rate}">
                    <style>
                        body {{ font-family: Arial, sans-serif; }}
                        .album-art {{ width: 300px; }}
                    </style>
                </head>
                <body>
                    <div>
                    <div>
                        <h1>Currently Playing</h1>
                        <p><strong>Track:</strong> {track_name}</p>
                        <p><strong>Artist:</strong> {artist_name}</p>
                        <p><strong>Album:</strong> {album_name}</p>
                        <p><strong>Next Refresh:</strong> {datetime.fromtimestamp(next_refresh).strftime('%H:%M:%S')}</p>
                        <img src="{album_image_url}" alt="Album art" class="album-art" />
                    </div>
                </body>
                </html>
                '''
                return html_content
        else:
            return "No track is currently playing."
