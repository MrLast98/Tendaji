DEFAULT_BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Tendaji{% endblock %}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
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
    <nav>
        <ul>
            <li><a href="#home" class="navButton">Home</a></li>
            <li><a href="#commands" class="navButton">Commands</a></li>
            <li><a href="#currently_playing" class="navButton">Currently Playing</a></li>
            <li><a href="#dashboard" class="navButton">Dashboard</a></li>
        </ul>
    </nav>
    <div id="dynamicContent">
        <!-- Content will be loaded here -->
    </div>
    <script>
        $(document).ready(function() {
            // Function to load content based on hash
            function loadContent() {
                var hash = window.location.hash.substring(1); // Remove the '#'
                if (hash) {
                    $("#dynamicContent").load('/page/' + hash, function() {
                        // Optional: Do something after content has been loaded
                    });
                }
            }

            // Load content initially based on the current hash
            loadContent();

            // Listen for hash changes
            $(window).on('hashchange', function() {
                loadContent();
            });

            $(".navButton").click(function(e) {
                e.preventDefault(); // Prevent the default action
                var targetHash = $(this).attr("href"); // Get the hash of the clicked button
                window.location.hash = targetHash; // Update the hash
            });
        });
    </script>
</body>
</html>

"""


DEFAULT_FIRST_TIME_CONFIGURATION_HTML = """
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
"""


DEFAULT_COMMANDS_HTML = """
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
"""


DEFAULT_DASHBOARD_HTML = """
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
"""
