import os
import requests
from flask import Flask, redirect, request, render_template, url_for
from urllib.parse import urlencode
import logging
from verified_users import is_historically_verified, add_verified_user, update_verified_user

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Railway deployment support
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Discord OAuth2 Configuration
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
DONUTSMP_ID = "852038293850898442"

# Discord API URLs
DISCORD_API_BASE = "https://discord.com/api"
OAUTH2_AUTHORIZE_URL = f"{DISCORD_API_BASE}/oauth2/authorize"
OAUTH2_TOKEN_URL = f"{DISCORD_API_BASE}/oauth2/token"
USER_GUILDS_URL = f"{DISCORD_API_BASE}/users/@me/guilds"

def get_redirect_uri():
    """Get the redirect URI based on the current request"""
    # For Replit, we need to use the proper domain
    from flask import request
    replit_domain = os.environ.get('REPLIT_DEV_DOMAIN')
    if replit_domain:
        return f"https://{replit_domain}/callback"
    elif request.host.endswith('.replit.app') or request.host.endswith('.repl.co') or request.host.endswith('.replit.dev'):
        return f"https://{request.host}/callback"
    return url_for('callback', _external=True)

@app.route("/")
def index():
    """Main page with Discord OAuth2 verification button"""
    if not CLIENT_ID or not CLIENT_SECRET:
        return render_template('error.html', 
                             error_title="Configuration Error",
                             error_message="Discord OAuth2 credentials not configured. Please set CLIENT_ID and CLIENT_SECRET environment variables.")
    
    # Build OAuth2 authorization URL
    oauth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': get_redirect_uri(),
        'response_type': 'code',
        'scope': 'identify guilds'
    }
    
    oauth_url = f"{OAUTH2_AUTHORIZE_URL}?{urlencode(oauth_params)}"
    
    return render_template('index.html', oauth_url=oauth_url)

@app.route("/callback")
def callback():
    """Handle OAuth2 callback from Discord"""
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error:
        app.logger.error(f"OAuth2 error: {error}")
        return render_template('error.html',
                             error_title="Authorization Error",
                             error_message=f"Discord authorization failed: {error}")
    
    if not code:
        app.logger.error("No authorization code received")
        return render_template('error.html',
                             error_title="Authorization Error",
                             error_message="No authorization code received from Discord.")
    
    try:
        # Exchange authorization code for access token
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': get_redirect_uri(),
            'scope': 'identify guilds'
        }
        
        token_headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        app.logger.debug("Requesting access token from Discord")
        token_response = requests.post(OAUTH2_TOKEN_URL, data=token_data, headers=token_headers)
        
        if token_response.status_code != 200:
            app.logger.error(f"Token request failed: {token_response.status_code} - {token_response.text}")
            return render_template('error.html',
                                 error_title="Token Error",
                                 error_message="Failed to obtain access token from Discord.")
        
        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        if not access_token:
            app.logger.error("No access token in response")
            return render_template('error.html',
                                 error_title="Token Error",
                                 error_message="No access token received from Discord.")
        
        # Get user's guilds
        guild_headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        app.logger.debug("Fetching user guilds from Discord")
        guilds_response = requests.get(USER_GUILDS_URL, headers=guild_headers)
        
        if guilds_response.status_code != 200:
            app.logger.error(f"Guilds request failed: {guilds_response.status_code} - {guilds_response.text}")
            return render_template('error.html',
                                 error_title="API Error",
                                 error_message="Failed to fetch your Discord servers.")
        
        guilds = guilds_response.json()
        
        # Get user info for tracking
        user_headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get(f"{DISCORD_API_BASE}/users/@me", headers=user_headers)
        user_data = user_response.json() if user_response.status_code == 200 else {}
        user_id = user_data.get('id')
        username = user_data.get('username')
        
        # Check if user is currently in DonutSMP
        is_in_donutsmp = any(guild['id'] == DONUTSMP_ID for guild in guilds)
        
        # Check if user has been verified before (historical membership)
        historically_verified = is_historically_verified(user_id) if user_id else False
        
        if is_in_donutsmp:
            # User is currently in DonutSMP - verify and add to history
            if user_id:
                add_verified_user(user_id, username)
            app.logger.info(f"User verified - currently in DonutSMP: {username} ({user_id})")
            return render_template('success.html', current_member=True)
        elif historically_verified:
            # User was previously in DonutSMP but not currently - they were banned/kicked
            if user_id:
                update_verified_user(user_id, username)
            app.logger.info(f"User verified - historical DonutSMP member: {username} ({user_id})")
            return render_template('success.html', current_member=False)
        else:
            # User has never been in DonutSMP server
            app.logger.info(f"User not verified - never been in DonutSMP: {username} ({user_id})")
            
            # For debugging: show what servers they're in
            guild_names = [g.get('name', 'Unknown') for g in guilds]
            app.logger.debug(f"User {username} is in these servers: {guild_names}")
            
            return render_template('error.html',
                                 error_title="Verification Failed",
                                 error_message="You have never been a member of the DonutSMP server. Only current or past DonutSMP members can verify.")
    
    except requests.RequestException as e:
        app.logger.error(f"Request error: {str(e)}")
        return render_template('error.html',
                             error_title="Network Error",
                             error_message="Failed to communicate with Discord API. Please try again later.")
    
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return render_template('error.html',
                             error_title="Unexpected Error",
                             error_message="An unexpected error occurred. Please try again.")

@app.route("/internal/check_ban/<user_id>")
def check_ban_status(user_id):
    """Internal endpoint to check if user is banned from DonutSMP"""
    # Simplified version - returns basic info
    return {"banned": False, "reason": None, "error": "Manual ban checking required"}

@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "DonutSMP Discord Verification"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
