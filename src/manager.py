import json
import platform
import secrets
import sys
from asyncio import create_task, run, CancelledError, sleep, gather, Event
from datetime import timedelta
from os import path, mkdir, chdir
from queue import Queue
from webbrowser import open as wbopen

import uvicorn
from websockets import ConnectionClosedOK

from manager_utils import PrintColors, load_configuration_from_json, save_configuration_to_json, return_date_string, \
    check_dict_structure, is_string_valid, check_token_expiry, is_token_config_invalid, reset_token_config
from quart_server import QuartServer
from spotify import start_spotify_oauth_flow, refresh_spotify_token
from translations import TranslationManager
from twitch import TwitchWebSocketManager
from twitch_utils import start_twitch_oauth_flow, refresh_twitch_token

# Files Location
CONFIG_FILE = 'config/config.json'


class Manager:
    def __init__(self):
        self.quart = None
        self.bot = None
        self.verify = None
        self.delay = None
        self.server = None
        self.queue = Queue()
        self.needed_values = []
        self.configuration = {
            'app': {
                'last_opened': None,
                'selected_language': None
            },
            'twitch': {
                'channel': None,
                'client_id': None,
                'client_secret': None
            },
            'spotify': {
                'client_id': None,
                'redirect_uri': None
            },
            'twitch-token': {
                'access_token': None,
                'refresh_token': None,
                'expires_in': None
            },
            'spotify-token': {
                'access_token': None,
                'refresh_token': None,
                'expires_in': None
            }
        }
        self.tasks = {
            'bot': None,
            'quart': None,
            'updater': None
        }
        self.translation_manager = TranslationManager(self)
        self.authentication_flag = Event()
        self.shutdown_flag = Event()
        self.quart = QuartServer(self)
        self.print = PrintColors()
        self.startup_checks()

    def startup_checks(self):
        if not path.exists('config'):
            self.print.print_to_logs('Creating new config folder', self.print.YELLOW)
            mkdir('config')

        self.print.print_to_logs('Checking config file existence', self.print.BRIGHT_PURPLE)
        if path.exists(f"{CONFIG_FILE}"):
            self.print.print_to_logs('Config found! Loading configuration...', self.print.GREEN)
            load_configuration_from_json(self, CONFIG_FILE)
        else:
            self.print.print_to_logs('Config file not found!', self.print.RED)
            self.print.print_to_logs('Creating new one and generating Quart app secret..', self.print.YELLOW)
            self.save_config()

        self.setup()
        # self.save_config()
        self.print.print_to_logs('Configuration Loaded', self.print.GREEN)
        self.print.print_to_logs('Do you want to reset the tokens? [Y/]', self.print.WHITE)
        # print('Do you want to reset the tokens? [Y/]')
        i = input('> ')
        if 'y' in i.lower():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reset tokens to empty strings
            reset_token_config(self)
            self.print.print_to_logs('Token for Spotify and Twitch correctly reset!', self.print.GREEN)
            # Write the updated data back to the file
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

        filename = f"logs/logs-{return_date_string()}.txt"
        if not path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"LOGS CREATION - {filename}\n")
            if 'y' not in i.lower():
                self.print.print_to_logs('New Logs generated!', self.print.YELLOW)
                reset_token_config(self)
                self.save_config()

        # if not path.exists('templates'):
        #     self.print.print_to_logs('No templates found, writing down default templates', self.print.YELLOW)
        #     mkdir('templates')
        #     write_default_templates()
        #     self.print.print_to_logs('Default templates written!', self.print.GREEN)

    def setup(self):
        sections = {
            'app': ['last_opened', 'selected_language'],
            'twitch': ['channel', 'client_id', 'client_secret'],
            'spotify': ['client_id', 'redirect_uri'],
            'twitch-token': ['access_token', 'refresh_token', 'expires_in', 'timestamp'],
            'spotify-token': ['access_token', 'refresh_token', 'expires_in', 'timestamp']
        }

        missing_keys = check_dict_structure(self.configuration, sections)
        if len(missing_keys) > 0:
            for section, item in missing_keys:
                match item:
                    case 'last_opened':
                        self.configuration[section][item] = return_date_string()
                    case 'redirect_uri':
                        self.configuration[section][item] = 'https://localhost:5000/callback'
                    case 'selected_language':
                        self.configuration[section][item] = 'en'
                    case _:
                        if section in ('twitch', 'spotify'):
                            self.needed_values.append((section, item))
                            # question = self.translation_manager.get_translation('insert_missing_configuration')
                            # section_name = self.translation_manager.get_dictionary(section)
                            # item_name = self.translation_manager.get_dictionary(item)
                            # value = input(f"{question}{section_name} {item_name}: ")
                            # self.configuration[section][item] = value
                        else:
                            self.configuration[section][item] = ''

    def set_config(self, section, key, value):
        self.configuration[section][key] = value
        self.print.print_to_logs(f"Set {section}/{key} in configuration", self.print.GREEN)

    def save_config(self):
        save_configuration_to_json(self, CONFIG_FILE)
        self.print.print_to_logs('Configuration saved', self.print.BRIGHT_PURPLE)

    def read_config(self):
        load_configuration_from_json(self, CONFIG_FILE)
        self.print.print_to_logs('Configuration loaded', self.print.BRIGHT_PURPLE)

    async def await_authentication(self):
        try:
            while self.authentication_flag.is_set():
                await sleep(1)
            self.print.print_to_logs('Authentication completed!', self.print.GREEN)
        except CancelledError:
            pass

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            # base_path = path.sep.join(sys.argv[0].split(path.sep)[:-1])
            base_path = path.abspath('.')
        return str(path.join(base_path, relative_path))

    async def create_server(self):
        self.quart.app.secret_key = secrets.token_hex(64)
        uvicorn_config = uvicorn.Config(self.quart.app, host='localhost', port=5000,
                                        ssl_certfile=self.resource_path('localhost.ecc.crt'),
                                        ssl_keyfile=self.resource_path('localhost.ecc.key'),
                                        loop='asyncio', log_level='info')
        self.server = uvicorn.Server(config=uvicorn_config)
        await self.server.serve()

    async def create_new_bot(self):
        if self.bot is not None and self.tasks['bot'] is not None:
            self.print.print_to_logs('Shutting down task', self.print.YELLOW)
            try:
                await self.bot.close()
                await self.tasks['bot']
            except CancelledError:
                pass
            except ConnectionClosedOK:
                pass
        self.bot = TwitchWebSocketManager(self)
        self.tasks['bot'] = create_task(self.bot.run())

    async def check_spotify(self):
        self.print.print_to_logs('Spotify sanity check!', self.print.BRIGHT_PURPLE)
        if is_token_config_invalid(self.configuration['spotify-token']):
            self.print.print_to_logs('No Token', self.print.RED)
            await start_spotify_oauth_flow(self)
            self.save_config()
        elif check_token_expiry(self.configuration['spotify-token']['expires_in'],
                                self.configuration['spotify-token']['timestamp']):
            self.print.print_to_logs('Expired Spotify Token', self.print.YELLOW)
            await refresh_spotify_token(self)
            self.save_config()
        else:
            self.print.print_to_logs('Spotify is OK!', self.print.GREEN)
        if is_string_valid(self.configuration['spotify-token']['expires_in']):
            expires_in = int(self.configuration['spotify-token']['expires_in'])
            spotify_delay = expires_in - 120  # Subtract 300 seconds for a buffer
            if spotify_delay <= 0:
                spotify_delay = None  # If the token is already expired or about to expire, don't set a delay
            self.set_delay(spotify_delay)

    async def check_twitch(self):
        self.print.print_to_logs('Twitch sanity check!', self.print.BRIGHT_PURPLE)
        if is_token_config_invalid(self.configuration['twitch-token']):
            self.print.print_to_logs('Twitch token missing. Retrieving...', self.print.RED)
            await start_twitch_oauth_flow(self)
            self.save_config()
            await self.create_new_bot()
        elif check_token_expiry(self.configuration['twitch-token']['expires_in'],
                                self.configuration['twitch-token']['timestamp']):
            self.print.print_to_logs('Expired Twitch Token', self.print.YELLOW)
            await refresh_twitch_token(self)
            self.save_config()
            await self.create_new_bot()
        else:
            self.print.print_to_logs('Twitch is OK!', self.print.GREEN)
        if is_string_valid(self.configuration['twitch-token']['expires_in']):
            expires_in = int(self.configuration['twitch-token']['expires_in'])
            twitch_delay = expires_in - 120  # Subtract 300 seconds for a buffer
            if twitch_delay <= 0:
                twitch_delay = None
            self.set_delay(twitch_delay)

    def set_delay(self, delay):
        if self.delay is None or (delay is not None and (self.delay > delay or self.delay < 0)):
            self.delay = delay
            self.print.print_to_logs(f"New delay: {str(timedelta(seconds=self.delay))}", PrintColors.GREEN)

    async def check_tokens(self):
        self.delay = None
        # Spotify check
        await self.check_spotify()
        # Twitch check
        await self.check_twitch()

    async def shutdown(self):
        if self.shutdown_flag.is_set():
            return
        self.shutdown_flag.set()
        self.print.print_to_logs('Initiating shutdown...', self.print.BRIGHT_PURPLE)
        await self.bot.close()
        self.tasks['updater'].cancel()
        self.save_config()
        self.print.print_to_logs('Cleanup complete. Exiting...', self.print.BRIGHT_PURPLE)

    async def core_loop(self):
        try:
            while not self.shutdown_flag.is_set():
                await sleep(self.delay if self.delay is not None else 300)
                await self.check_tokens()
        except CancelledError:
            pass

    async def main(self):
        self.tasks['quart'] = create_task(self.create_server())
        if len(self.needed_values) > 0:
            self.authentication_flag.set()
            wbopen('https://localhost:5000/setup')
            await self.await_authentication()
        await self.check_tokens()
        if self.bot is None and self.tasks['bot'] is None:
            await self.create_new_bot()
        self.tasks['updater'] = create_task(self.core_loop())
        tasks = [self.tasks['quart'], self.tasks['updater'], self.tasks['bot']]
        try:
            await gather(*tasks)
        except CancelledError:
            await self.shutdown()


if __name__ == '__main__':
    if platform.system() == 'Darwin':
        chdir(path.sep.join(sys.argv[0].split(path.sep)[:-1]))
    manager = Manager()
    try:
        run(manager.main())
    except KeyboardInterrupt:
        pass
