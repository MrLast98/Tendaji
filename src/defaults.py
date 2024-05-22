EN_DEFAULTS = {
    "dictionary": {
        "app": "App",
        "twitch": "Twitch",
        "spotify": "Spotify",
        "selected_language": "Language",
        "channel": "Channel you want to join in",
        "client_id": "Client ID",
        "client_secret": "Client Secret"
    },
    "errors": {
        "twitch_bot": {
            "missing_player": "No player found - Please start playing a song before requesting!"
        }
    },
    "insert_missing_configuration": "Please, enter the ",
    "section_missing": ""
}

DEFAULT_COMMANDS = {
    "simple": {
        "hello": {
            "message": "hello [sender]",
            "level": "ANY",
            "enabled": True,
            "timeout": 0,
            "min_messages": 0
        },
        "hotpants": {
            "message": "You're the shit [sender]",
            "level": "MOD",
            "enabled": True,
            "timeout": 0,
            "min_messages": 0
        }
    },
    "complex": {}
}


# default_templates = [('first_time_configuration.html', DEFAULT_FIRST_TIME_CONFIGURATION_HTML),
#                      ('index.html', DEFAULT_INDEX_HTML),
#                      ('commands.html', DEFAULT_COMMANDS_HTML)]
