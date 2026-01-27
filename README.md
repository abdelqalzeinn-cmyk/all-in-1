# Discord Bot with Search, Generate, and Say Commands

A Discord bot with three main commands:
- `/search` - Search for images using Playwright
- `/generate` - Generate images using Pollinations API
- `/say` - Make the bot say something (ephemeral command)

## Features

- **Search Command**: Uses Playwright to search for images and filters inappropriate content
- **Generate Command**: Creates AI-generated images using the free Pollinations API
- **Say Command**: Allows users to make the bot say messages (command is only visible to the user)
- **Profanity Filter**: Built-in profanity filtering for all commands

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

3. **Create Discord Bot**:
   - Go to Discord Developer Portal
   - Create a new application
   - Add a bot to the application
   - Enable Message Content Intent
   - Copy the bot token

4. **Configure Environment**:
   - Copy `.env.example` to `.env`
   - Add your Discord bot token to the `.env` file:
     ```
     DISCORD_TOKEN=your_discord_bot_token_here
     ```

5. **Invite Bot to Server**:
   - In Discord Developer Portal, go to OAuth2 -> URL Generator
   - Select scopes: `bot` and `applications.commands`
   - Select bot permissions: `Send Messages`, `Embed Links`, `Read Message History`
   - Copy the generated URL and invite the bot to your server

## Usage

### `/search`
Search for images using a text prompt.
```
/search prompt:cute cats
```

### `/generate`
Generate an AI image using Pollinations API.
```
/generate prompt:a beautiful sunset over mountains
```

### `/say`
Make the bot say something (only you can see the command response).
```
/say message:Hello everyone!
```

## Security Features

- **Profanity Filter**: All commands check for inappropriate words using the `better-profanity` library
- **Ephemeral Commands**: The `/say` command response is only visible to the user who ran it
- **Input Validation**: All user inputs are validated before processing

## Running the Bot

```bash
python bot.py
```

The bot will automatically sync slash commands when it starts.

## Dependencies

- `discord.py` - Discord API wrapper
- `playwright` - Web automation for image search
- `aiohttp` - HTTP client for API requests
- `python-dotenv` - Environment variable management
- `better-profanity` - Profanity filtering

## Notes

- The search command uses DuckDuckGo for image searching
- The generate command uses Pollinations API (free tier)
- All commands include error handling and user feedback
- The bot requires the Message Content Intent to be enabled in Discord Developer Portal
