import json
import sys
from asyncio import CancelledError
from os import path
from time import time

from quart import Quart, request, Response, redirect, send_from_directory, render_template_string

from manager_utils import is_string_valid, process_form
from spotify import get_token, get_current_track
from templates import DEFAULT_FIRST_TIME_CONFIGURATION_HTML, DEFAULT_COMMANDS_HTML, \
    DEFAULT_BASE_HTML, DEFAULT_DASHBOARD_HTML
from twitch_utils import retrieve_token_info, COMMANDS_FILE

# Configuration and Flask App
CONFIG_FILE = 'config/config.json'
QUEUE_FILE = 'queue.json'
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'


def update_queue(track_name, artist_name):
    with open('queue.json', 'r', encoding='utf-8') as f:
        queue = json.loads(f.read())
    while queue and queue[0]['title'] != track_name and queue[0]['author'] != artist_name and len(queue) > 0:
        queue.pop(0)
    # print_queue_to_file(queue)


class QuartServer:
    def __init__(self, manager):
        self.app = Quart(__name__)
        self.manager = manager
        self.commands = None
        self.setup_routing()

    def setup_routing(self):
        self.app.add_url_rule('/', view_func=self.index)
        self.app.add_url_rule('/callback', view_func=self.callback)
        self.app.add_url_rule('/callback_twitch', view_func=self.callback_twitch)
        self.app.add_url_rule('/page/<page_name>', view_func=self.render_page)
        self.app.add_url_rule('/currently_playing', view_func=self.currently_playing)
        self.app.add_url_rule('/favicon.ico', view_func=self.favicon)
        self.app.add_url_rule('/reset', methods=['POST'], view_func=self.reset_config)
        self.app.add_url_rule('/save', view_func=self.save_commands, methods=['POST'])
        self.app.add_url_rule('/save_config', view_func=self.save_config, methods=['POST'])
        self.app.add_url_rule('/stream', view_func=self.stream)

    @staticmethod
    async def index():
        return await render_template_string(DEFAULT_BASE_HTML)

    async def render_page(self, page_name):
        if page_name == 'commands':
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                self.commands = json.loads(f.read())
            return await render_template_string(DEFAULT_COMMANDS_HTML, commands=self.commands)
        elif page_name == 'dashboard':
            return await render_template_string(DEFAULT_DASHBOARD_HTML)
        elif page_name == 'setup':
            return await render_template_string(DEFAULT_FIRST_TIME_CONFIGURATION_HTML,
                                                needed_values=self.manager.needed_values)
        elif page_name == 'currently_playing':
            return await render_template_string(self.current_song())
        else:
            return "Page not found", 404

    async def favicon(self):
        return await send_from_directory(f'{path.sep.join(sys.argv[0].split(path.sep)[:-1])}/static', 'favicon.ico')

    def event_stream(self):
        try:
            while not self.manager.shutdown_flag.is_set():
                message = self.manager.queue.get(block=True)
                if is_string_valid(message):
                    yield f"data: {message}\n\n"
        except CancelledError:
            pass

    async def stream(self):
        return Response(self.event_stream(), mimetype='text/event-stream')

    # async def commands_config(self):
    #     with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
    #         self.commands = json.loads(f.read())
    #     return await render_template_string(DEFAULT_COMMANDS_HTML, commands=self.commands)

    async def save_commands(self):
        form_data = await request.form
        process_form(form_data)
        await self.manager.create_new_bot()
        return redirect('/commands')

    @staticmethod
    def reset_config():
        return redirect('/commands')

    async def setup(self):
        return await render_template_string(DEFAULT_FIRST_TIME_CONFIGURATION_HTML, needed_values=self.manager.needed_values)

    def current_song(self):
        track = get_current_track(self.manager.configuration['spotify-token']['access_token'])
        if track:
            track_name = track['item']['name']
            artist_name = track['item']['artists'][0]['name']

            album_name = track['item']['album']['name']
            album_image_url = track['item']['album']['images'][0]['url'] if track['item']['album'][
                'images'] else 'No image available'
            track_duration = int(track['item']['duration_ms'])
            progress = int(track['progress_ms'])
            if track_duration - progress >= 30000:
                refresh_rate = 30
            else:
                refresh_rate = ((track_duration - progress) / 1000) + 2  # Convert to seconds and adds 2 seconds
                if path.exists(QUEUE_FILE):
                    update_queue(track_name, artist_name)
            html_content = f'''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Currently Playing</title>
                        <meta http-equiv="refresh" content="{refresh_rate}">
                        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css">
                    </head>
                    <body>
                        <div>
                            <h1>Currently Playing</h1>
                            <p><strong>Track:</strong> {track_name}</p>
                            <p><strong>Artist:</strong> {artist_name}</p>
                            <p><strong>Album:</strong> {album_name}</p>
                            <img src="{album_image_url}" alt="Album art" class="album-art" />
                        </div>
                    </body>
                    </html>
                    '''
            return html_content
        return 'No track is currently playing.'

    async def save_config(self):
        form_data = await request.form
        for key, value in form_data.items():
            section, item = key.split("-")
            self.manager.set_config(section, item, value)
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

    async def currently_playing(self):
        return await render_template_string(self.current_song())

    async def callback(self):
        response = get_token(self.manager.configuration['spotify']['client_id'],
                             self.manager.configuration['spotify']['redirect_uri'],
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
                    <p>ERROR: {response.get('error')}</p>
                    <p>{response}</p>
                </body>
                </html>
                '''

    async def callback_twitch(self):
        response = retrieve_token_info(self.manager.configuration['twitch']['client_id'],
                                       self.manager.configuration['twitch']['client_secret'],
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
                    <p>ERROR: {response.get('error')}</p>
                    <p>{response}</p>
                </body>
                </html>
            '''
