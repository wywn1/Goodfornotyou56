# DonutSMP Discord Verification System

A complete Discord OAuth2 verification system for the DonutSMP server that verifies current members and maintains a historical database for banned/kicked users.

## Features

- **OAuth2 Verification**: Secure Discord login to check DonutSMP membership
- **Historical Database**: Tracks previously verified users (banned/kicked members)
- **Discord Bot**: 5 slash commands for admin management
- **Privacy-Focused**: No persistent data storage beyond historical tracking
- **DonutSMP-Only**: Checks only the specific DonutSMP server

## Quick Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd donutsmp-verification
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export CLIENT_ID="your_discord_client_id"
   export CLIENT_SECRET="your_discord_client_secret"
   export BOT_TOKEN="your_discord_bot_token"
   export SESSION_SECRET="your_session_secret"
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## Discord Bot Commands

- `/verify` - Shows verification button linking to web app
- `/smp @user` - Check if user is in DonutSMP server
- `/rev @user` - Review system with star ratings
- `/add_historical @user` - Manually add banned users to database
- `/set_vouches_channel #channel` - Configure review channel

## Automatic Deployment

### Railway (Recommended - Free)
1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add environment variables in Railway dashboard
5. **Auto-deploys on every push to main branch**

### Render (Free Alternative)
1. Go to [render.com](https://render.com)
2. Connect your GitHub repository
3. Uses `render.yaml` for automatic configuration
4. Add environment variables in Render dashboard

### Fly.io (Free with Credit)
1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Run: `flyctl launch` (uses fly.toml)
3. Set secrets: `flyctl secrets set CLIENT_ID=your_id`
4. Deploy: `flyctl deploy`

### GitHub Actions
- Automatic testing on every push
- Deploy webhook ready for Railway
- See `.github/workflows/deploy.yml`

## Configuration

The system requires these environment variables:
- `CLIENT_ID`: Discord application client ID
- `CLIENT_SECRET`: Discord application client secret
- `BOT_TOKEN`: Discord bot token
- `SESSION_SECRET`: Flask session secret

## File Structure

```
├── main.py                 # Flask web application
├── bot.py                  # Discord bot with slash commands
├── verified_users.py       # Historical database management
├── templates/              # HTML templates
│   ├── index.html         # Main verification page
│   ├── success.html       # Success page
│   └── error.html         # Error page
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## License

MIT License - feel free to use and modify for your Discord server.