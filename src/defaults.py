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
            "enabled": True
        },
        "hotpants": {
            "message": "You're the shit [sender]",
            "level": "SUB",
            "enabled": True
        },
    },
    "complex": {}
}

DEFAULT_FIRST_TIME_CONFIGURATION_HTML = """<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <title>First time Configuration</title>
    <link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css'>
    <script src='https://unpkg.com/htmx.org@1.7.1'></script>
    <style>
        /* Custom styles */
        body {
            margin-top: 40px;
        }
        h2 {
            margin-top: 20px;
        }
        h4 {
            margin-top: 10px;
        }
        select, input[type='text'], input[type='checkbox'], button {
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <form action='{{ url_for('save_config') }}' method='post'>
        <div class='six columns'>
            <h2>Configuration</h2>
            {% for section, item in needed_values %}
                <h4>{{ ' '.join([(section[0].upper() + section[1:]),(item[0].upper() + item[1:])]) }}</h4>
                <input class='u-full-width' type='text' name='{{section}}-{{item}}' value=''>
            {% endfor %}
            <button class='button-primary' type='submit'>Save Config</button>
        </div>
    </form>
</body>
</html>"""

DEFAULT_COMMANDS_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Command Configuration</title>
    <!-- Include Skeleton CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css">
    <script src="https://unpkg.com/htmx.org@1.7.1"></script>
    <style>
        /* Custom styles */
        body {
            margin-top: 40px;
        }
        h2 {
            margin-top: 20px;
        }
        h4 {
            margin-top: 10px;
        }
        select, input[type="text"], input[type="checkbox"], button {
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <form action="{{ url_for('save_commands') }}" method="post">
            <div class="row">
                <div class="six columns">
                    <h2>Simple Commands</h2>
                    <div id="simple-commands">
                        {% for command_name, command_data in commands['simple'].items() %}
                            <div class="command">
                                <h4>{{ command_name[0].upper() + command_name[1:] }}</h4>
                                <input class="u-full-width" type="text" name="simple_{{ command_name }}_message" value="{{ command_data['message'] }}">
                                <select class="u-full-width" name="simple_{{ command_name }}_level">
                                    <option value="ANY" {% if command_data.get('level') == 'ANY' %}selected{% endif %}>ANY</option>
                                    <option value="SUB" {% if command_data.get('level') == 'SUB' %}selected{% endif %}>SUB</option>
                                    <option value="MOD" {% if command_data.get('level') == 'MOD' %}selected{% endif %}>MOD</option>
                                    <option value="VIP" {% if command_data.get('level') == 'VIP' %}selected{% endif %}>VIP</option>
                                    <option value="BROADCASTER" {% if command_data.get('level') == 'BROADCASTER' %}selected{% endif %}>BROADCASTER</option>
                                </select>
                                <div style="display: flex; align-items: center;">
                                    <h6 style="margin-right: 10px; margin-bottom: 0;">Command Status</h6>
                                    <input type="checkbox" name="simple_{{ command_name }}_enabled" {% if command_data.get('enabled') %}checked{% endif %} style="margin-bottom: 0; margin-top: 0; vertical-align: middle;">
                                </div>
                            </div>
                        {% endfor %}
                    </div>
                    <button class="button" id="add-command-btn" type="button">Add New Command</button>
                </div>
                <div class="six columns">
                    <h2>Complex Commands</h2>
                    {% for command_name, command_data in commands['complex'].items() %}
                        <h4>{{ command_name[0].upper() + command_name[1:] }}</h4>
                        <select class="u-full-width" name="complex_{{ command_name }}_level">
                            <option value="ANY" {% if command_data.get('level') == 'ANY' %}selected{% endif %}>ANY</option>
                            <option value="SUB" {% if command_data.get('level') == 'SUB' %}selected{% endif %}>SUB</option>
                            <option value="MOD" {% if command_data.get('level') == 'MOD' %}selected{% endif %}>MOD</option>
                            <option value="VIP" {% if command_data.get('level') == 'VIP' %}selected{% endif %}>VIP</option>
                            <option value="BROADCASTER" {% if command_data.get('level') == 'BROADCASTER' %}selected{% endif %}>BROADCASTER</option>
                        </select>
                        <div style="display: flex; align-items: center;">
                            <h6 style="margin-right: 10px; margin-bottom: 0;">Command Status</h6>
                            <input type="checkbox" name="complex_{{ command_name }}_enabled" {% if command_data.get('enabled') %}checked{% endif %} style="margin-bottom: 0; margin-top: 0; vertical-align: middle;">
                        </div>
                    {% endfor %}
                </div>
            </div>
            <button class="button-primary" type="submit">Save Config</button>
        </form>
    </div>
    <script>
        document.getElementById('add-command-btn').addEventListener('click', function() {
            var commandCount = document.querySelectorAll('.command').length + 1;
            var newCommandName = 'New Command ' + commandCount;
            var newCommand = `
                <div class="command">
                    <input class="command-name u-full-width" type="text" name="simple_${newCommandName.toLowerCase()}_name" value="${newCommandName}">
                    <input class="u-full-width" type="text" name="simple_${newCommandName.toLowerCase()}_message" value="">
                    <select class="u-full-width" name="simple_${newCommandName.toLowerCase()}_level">
                        <option value="ANY">ANY</option>
                        <option value="SUB">SUB</option>
                        <option value="MOD">MOD</option>
                        <option value="VIP">VIP</option>
                        <option value="BROADCASTER">BROADCASTER</option>
                    </select>
                    <input type="checkbox" name="simple_${newCommandName.toLowerCase()}_enabled">
                </div>
            `;
            document.getElementById('simple-commands').insertAdjacentHTML('beforeend', newCommand);
        });

        // Add event listener to the form submission
        document.getElementById('command-form').addEventListener('submit', function(event) {
            // Loop through each command section
            document.querySelectorAll('.command').forEach(function(command, index) {
                command.querySelector('input[type="text"]').setAttribute('name', 'simple_' + newCommandName + '_message');
                command.querySelector('select').setAttribute('name', 'simple_' + newCommandName + '_level');
                command.querySelector('input[type="checkbox"]').setAttribute('name', 'simple_' + newCommandName + '_enabled');
            });
        });
    </script>
</body>
</html>
"""

DEFAULT_INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css">
    <script src="https://unpkg.com/htmx.org@1.6.1"></script>
</head>
<body>
    <ul id="messages">
        <!-- Messages will be appended here -->
    </ul>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var source = new EventSource('/stream');
            source.onmessage = function(event) {
                var list = document.getElementById('messages');
                var listItem = document.createElement('li');
                listItem.textContent = event.data;
                list.appendChild(listItem);
            };
        });
    </script>
</body>
</html>
"""

# default_templates = [('first_time_configuration.html', DEFAULT_FIRST_TIME_CONFIGURATION_HTML),
#                      ('index.html', DEFAULT_INDEX_HTML),
#                      ('commands.html', DEFAULT_COMMANDS_HTML)]
