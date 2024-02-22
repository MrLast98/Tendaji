import configparser
import os
import webbrowser
from flask import Flask, request
import requests
from threading import Thread
from urllib.parse import urlencode
from irc.bot import SingleServerIRCBot

CONFIG_FILE = 'config.ini'
APP = Flask(__name__)

# Twitch OAuth URLs
AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'

# Twitch requires a scope for the bot. Adjust the scope based on your needs.
SCOPE = 'chat:read chat:edit'


class TwitchBot(SingleServerIRCBot):
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE)
        self.ensure_config_section_exists('twitch')

        if not self.validate_config():
            self.setup()
            self.config.read(CONFIG_FILE)  # Reload the config after setup

        self.username = self.config.get('twitch', 'username')
        self.token = self.config.get('twitch', 'token')
        self.channel = '#' + self.config.get('twitch', 'channel')

        server = 'irc.chat.twitch.tv'
        port = 6667
        print(f"Connecting to {self.channel}")

        SingleServerIRCBot.__init__(self, [(server, port, f"oauth:{self.token}")], self.username, self.username)

    def ensure_config_section_exists(self, section):
        if not self.config.has_section(section):
            self.config.add_section(section)

    def validate_config(self):
        required_keys = ['username', 'token', 'channel', 'client_id', 'client_secret']
        return all(self.config.get('twitch', key) for key in required_keys)

    def setup(self):
        # Prompt for missing details
        if not self.config['twitch'].get('username'):
            self.config.set("twitch", "username", input("Enter your Twitch username: "))
        if not self.config['twitch'].get('channel'):
            self.config.set("twitch", "channel", input("Enter the channel you want to join: "))
        if not self.config['twitch'].get('client_id'):
            self.config.set("twitch", "client_id", input("Enter your Twitch client ID: "))
        if not self.config['twitch'].get('client_secret'):
            self.config.set("twitch", "client_secret", input("Enter your Twitch client secret: "))

        # Check if the token exists and is valid; if not, start the OAuth flow
        if not self.config['twitch'].get('token'):
            print("Initiating OAuth flow to obtain token...")
            Thread(target=lambda: APP.run(port=5000, debug=False, ssl_context=("localhost.ecc.crt", "localhost.ecc.key"))).start()
            self.start_oauth_flow()
            print("Please complete the OAuth flow in the browser.")
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def start_oauth_flow(self):
        params = {
            'client_id': self.config.get('twitch', 'client_id'),
            'redirect_uri': 'https://localhost:5000/callback',
            'response_type': 'code',
            'scope': SCOPE
        }
        url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
        webbrowser.open(url)

    @APP.route('/callback')
    def callback(self):
        code = request.args.get('code')
        payload = {
            'client_id': self.config.get('twitch', 'client_id'),
            'client_secret': self.config.get('twitch', 'client_secret'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://localhost:5000/callback'
        }
        response = requests.post(TOKEN_URL, data=payload)
        response_json = response.json()
        access_token = response_json.get('access_token')

        # Save the access token and other details to config.ini
        self.config.set('twitch', 'token', access_token)
        with open(CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

        os._exit(0)
        print(f"Joined {self.channel}")

    def on_pubmsg(self, connection, event):
        if event.arguments[0].startswith("!sr"):
            print(f"Received !sr command from {event.source.nick}")


if __name__ == "__main__":
    bot = TwitchBot()
    bot.start()
