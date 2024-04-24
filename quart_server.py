import configparser
import json
import os
from datetime import datetime
from time import time

from quart import Quart, request, redirect

from spotify import get_token, get_current_track
from twitch_utils import retrieve_token_info

# Configuration and Flask App
CONFIG_FILE = 'config/config.json'
COMMANDS_FILE = 'config/commands.json'
QUEUE_FILE = 'queue.json'
config = configparser.ConfigParser()
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'


def update_queue(track_name, artist_name):
    with open('queue.json', 'r', encoding='utf-8') as f:
        queue = json.loads(f.read())
    while queue and queue[0]['title'] != track_name and queue[0]['author"] != artist_name and len(queue) > 0:
        queue.pop(0)
    # print_queue_to_file(queue)


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

    async def index(self):
        return redirect("/currently_playing")

    async def callback(self):
        response = get_token(self.manager.configuration["spotify"]["client_id"],
                             self.manager.configuration["spotify"]["redirect_uri"],
                             request.args['code'],
                             self.manager.verify)
        access_token = response.get('access_token')
        refresh_token = response.get('refresh_token')
        expires_in = response.get('expires_in')
        if access_token and refresh_token and expires_in:
            self.manager.set_config('spotify-token', 'access_token', access_token)
            self.manager.set_config('spotify-token', 'refresh_token', refresh_token)
            self.manager.set_config('spotify-token', 'expires_in', str(expires_in))
            self.manager.set_config('spotify-token', 'timestamp', str(int(time())))
            self.manager.save_config()
            self.manager.authentication_flag.clear()
            return '''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Spotify Token Retrieved</title>
                </head>
                <body>
                    <p>You can close this window.</p>
                </body>
                </html>
            '''
        return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Spotify Token not Retrieved</title>
                </head>
                <body>
                    <p>ERROR: {response.get("error")}</p>
                    <p>{response}</p>
                </body>
                </html>
                '''

    async def callback_twitch(self):
        response = retrieve_token_info(self.manager.configuration["twitch"]["client_id"],
                                       self.manager.configuration["twitch"]["client_secret"],
                                       request.args.get('code'))
        access_token = response.get('access_token')
        refresh_token = response.get('refresh_token')
        expires_in = response.get('expires_in')
        # Save the access token, refresh token, and expiration timestamp
        if access_token and refresh_token and expires_in:
            self.manager.set_config('twitch-token', 'access_token', access_token)
            self.manager.set_config('twitch-token', 'refresh_token', refresh_token)
            self.manager.set_config('twitch-token', 'expires_in', str(expires_in))
            self.manager.set_config('twitch-token', 'timestamp', str(int(time())))
            self.manager.save_config()
            self.manager.authentication_flag.clear()
            return '''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Twitch Token Retrieved</title>
                </head>
                <body>
                    <p>You can close this window.</p>
                </body>
                </html>
            '''
        return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Twitch Token not Retrieved</title>
                </head>
                <body>
                    <p>ERROR: {response.get("error")}</p>
                    <p>{response}</p>
                </body>
                </html>
            '''

    async def currently_playing(self):
        track = get_current_track(self.manager.configuration["spotify-token"]["access_token"])
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
        return "No track is currently playing."
