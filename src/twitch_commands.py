import re

import spotify

FUNCTION_LIST = ['song', 'play', 'pause', 'skip', 'sbagliato', 'sr']
URL_PATTERN = r'\b(?:https?|ftp):\/\/[\w\-]+(\.[\w\-]+)+[/\w\-?=&#%]*\b'


class TwitchCommands:
    def __init__(self, twitch_manager):
        self.twitch_manager = twitch_manager
        self.command_timeout = {}

    async def song(self, _):
        response = spotify.get_queue(self.twitch_manager.manager.configuration['spotify-token']['access_token'])
        currently_playing = spotify.parse_song(response['currently_playing'])
        await send_message(self.twitch_manager, currently_playing['name'])

    async def play(self, _):
        spotify.play(self.twitch_manager.manager.configuration['spotify-token']['access_token'])
        self.twitch_manager.manager.print.print_to_logs('Resumed!', self.twitch_manager.manager.print.YELLOW)
        await send_message(self.twitch_manager, 'Resumed!')

    async def pause(self, _):
        spotify.pause(self.twitch_manager.manager.configuration['spotify-token']['access_token'])
        self.twitch_manager.manager.print.print_to_logs('Paused!', self.twitch_manager.manager.print.YELLOW)
        await send_message(self.twitch_manager, 'Paused!')

    async def skip(self, _):
        spotify.skip(self.twitch_manager.manager.configuration['spotify-token']['access_token'])
        self.twitch_manager.manager.print.print_to_logs('Skipped!', self.twitch_manager.manager.print.YELLOW)
        await send_message(self.twitch_manager, 'Skipped!')

    async def sbagliato(self, _):
        await send_message(self.twitch_manager, 'Oh No')

    async def sr(self, requested_song):
        if re.search(URL_PATTERN, requested_song):
            requested_song = requested_song.split('/')[-1]
            if '?' in requested_song:
                requested_song = requested_song.split('?')[0]
            query = spotify.get_track_by_id(self.twitch_manager.manager.configuration['spotify-token']['access_token'],
                                            requested_song)
            spotify.add_song_id(self.twitch_manager.manager.configuration['spotify-token']['access_token'],
                                requested_song)
        else:
            query = spotify.query_for_song(self.twitch_manager.manager.configuration['spotify-token']['access_token'],
                                           requested_song)
            spotify.add_song_id(self.twitch_manager.manager.configuration['spotify-token']['access_token'], query['id'])
            # self.queue.append({
            #     'title': f'{query["name"]}',
            #     'author': f"{query['artists'][0]['name']}",
            #     'requested_by': f"{ctx.author.display_name}",
            #     'duration': query['duration_ms']
            # })
            # print_queue_to_file(self.queue)
        self.twitch_manager.manager.print.print_to_logs(
            f"Aggiunto {query['name']} - {query['artists'][0]['name']} alla coda!",
                                         self.twitch_manager.manager.print.BRIGHT_PURPLE)
        await send_message(self.twitch_manager, f"Aggiunto {query['name']} - {query['artists'][0]['name']}!")


async def send_message(self, message, target=None):
    # Send a message to the channel or a specific user
    if target:
        await self.chat_websocket.send(f"PRIVMSG #{self.channel} :/w {target} {message}")
    else:
        await self.chat_websocket.send(f"PRIVMSG #{self.channel} :{message}")
