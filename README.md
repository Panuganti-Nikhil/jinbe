# Jinbe Discord Bot

A powerful Discord bot with server templates, moderation, and management features.

## Features

- 🎨 Server Templates (Gaming, Music, Friends, Blox Fruits, YouTube)
- 🛡️ Advanced Auto-Moderation System
- 🔒 Channel Lock/Unlock Commands
- 📢 Announcement System
- 👋 Welcome System
- 📜 Auto Rules Generation
- 💬 Quote System

## Commands

### Slash Commands (Owner Only)
- `/templates` - View available templates
- `/apply <template>` - Apply a template (WARNING: Deletes all channels)
- `/announce <message>` - Make announcements
- `/welcome <message>` - Set welcome message
- `/editrules <rules>` - Edit server rules
- `/sync` - Sync commands
- `/help` - Show help menu

### Prefix Commands (Owner Only)
- `!lock <#channel>` - Lock a channel
- `!unlock <#channel>` - Unlock a channel

### Public Commands
- `/quote <message_link>` - Create a quote from any message
- Right-click message → Apps → Create Quote

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```
DISCORD_TOKEN=your_bot_token_here
```

3. Run the bot:
```bash
python jinbe.py
```

## Deployment

This bot is ready for deployment on:
- Render.com (recommended)
- Railway.app
- Heroku
- VPS

## Environment Variables

- `DISCORD_TOKEN` - Your Discord bot token (required)

## License

MIT License - See [LICENSE](LICENSE) file for details

## Contributing

Feel free to fork this project and submit pull requests!

## Hosting

This bot is hosted 24/7 on [Render.com](https://render.com/)

## Support

For issues or questions, please open an issue on GitHub.
