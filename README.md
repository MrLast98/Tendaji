# Tendaji

## Description
Tendaji is a simple bot for twitch to address all your bot-sy desired, but locally
It's going to be a full replacement for Streamlabs and Streamelements at some point


## Features
- Full local Application, no third party account
  - Of course, Twitch and Spotify Accounts are necessary
- Everything can be access from https://localhost:5000
- Commands that can be managed from the https://localhost:5000/commands page
  - Simple commands
    - Can add them, modify role, enable/disable them
  - Complex commands
    - Can only modify role and enable/disable them, code required
- Spotify support for query and link song request
- Events logging (ONLY FOLLOW SUPPORTED FOR NOW)
- Local AI Toxicity Analysis (No Chat-GPT)
- Pre-configured text replacements

## Specification
All permission are based on the following hierarchy:
```
'BROADCASTER' > 'MOD' > 'VIP' > 'SUB' > 'ANY' 
```
Setting up a specific level will make the command available to any higher level, so a VIP can bypass SUB and ANY

## Future Implementations
### Legend: 🟥 Not Done 🟨 Working on it 🟩 Implemented
- 🟨 Fully implement localhost-server GUI
  - 🟩 Commands
  - 🟩 First setup (and reconfiguration)
  - 🟨 Chat stream (basic)
  - 🟩 Currently Playing screen
  - 🟨 Navigation bar
  - 🟥 Queue
- 🟨 Fully implement the EventSub API
  - 🟩 Follow
  - 🟥 Subscription
  - 🟥 Sub Gifted
  - 🟥 Cheers
  - 🟥 Points Reward
  - 🟥 Raid
  - 🟥 Host
  - 🟥 Automod
  - 🟥 Ads
  - 🟥 Moderation
    - 🟥 Timeout
    - 🟥 Ban
    - 🟥 Clear Chat
    - 🟥 Deleted Message
  - 🟥 Polls
  - 🟥 Predictions
  - 🟥 Hype Train
  - 🟥 Shield Mode
  - 🟥 Whispers
- 🟥 External Notifications
  - 🟥 Discord
  - 🟥 Telegram
  - 🟥 Instagram
- 🟥 Youtube support
- 🟥 Multi-source queue
- 🟥 Across-channel moderation
- 🟥 RTMPS server for multicasting (?)

## Installation
1. Download the bot for you from the releases pages.
2. Creating a Twitch Developer App
   1. Go to the [Twitch Developer Console](https://dev.twitch.tv/console).
   2. Log in with your Twitch account or sign up if you don't have one.
   3. Click on your avatar at the top right and select "Dashboard".
   4. Click on "Applications" in the left sidebar.
   5. Click on "Register Your Application".
   6. Fill in the required fields such as name, OAuth redirect URLs, and category.
   7. Agree to the Developer Services Agreement and click "Create".
   8. Note down your Client ID and Client Secret. These will be needed for authentication.
3. Creating a Spotify Developer App
   1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications).
   2. Log in with your Spotify account or sign up if you don't have one.
   3. Click on "Create an App".
   4. Fill in the required fields such as App Name, Description, and Redirect URIs.
   5. Agree to the Developer Terms of Service and click "Create".
   6. Note down your Client ID and Client Secret. These will be needed for authentication.
   7. You may need to configure additional settings based on your project requirements.
4. Run the app and configure everything from the Setup page that will open in your browser, the app will take care of the srest


## Download
You can download the latest version of the project from the [releases](https://github.com/MrLast98/Tendaji/releases) page.
