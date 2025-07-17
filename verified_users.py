"""
Simple file-based storage for verified users
This tracks users who have been verified at least once
"""
import json
import os
from datetime import datetime

VERIFIED_USERS_FILE = "verified_users.json"

def load_verified_users():
    """Load verified users from file"""
    try:
        if os.path.exists(VERIFIED_USERS_FILE):
            with open(VERIFIED_USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

def save_verified_users(users_data):
    """Save verified users to file"""
    try:
        with open(VERIFIED_USERS_FILE, 'w') as f:
            json.dump(users_data, f, indent=2)
    except Exception:
        pass

def add_verified_user(user_id, username=None):
    """Add a user to the verified list"""
    users_data = load_verified_users()
    users_data[str(user_id)] = {
        "username": username,
        "first_verified": datetime.now().isoformat(),
        "last_verified": datetime.now().isoformat()
    }
    save_verified_users(users_data)

def update_verified_user(user_id, username=None):
    """Update last verification time for existing user"""
    users_data = load_verified_users()
    user_key = str(user_id)
    if user_key in users_data:
        users_data[user_key]["last_verified"] = datetime.now().isoformat()
        if username:
            users_data[user_key]["username"] = username
    else:
        add_verified_user(user_id, username)
    save_verified_users(users_data)

def is_historically_verified(user_id):
    """Check if user has been verified before"""
    users_data = load_verified_users()
    return str(user_id) in users_data

def get_verified_user_info(user_id):
    """Get verification info for a user"""
    users_data = load_verified_users()
    return users_data.get(str(user_id))