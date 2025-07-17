import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp
import asyncio
from typing import Optional
import logging
from verified_users import is_historically_verified, get_verified_user_info

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # Configuration
        self.DONUTSMP_ID = 852038293850898442
        self.VOUCHES_CHANNEL_ID = None  # Will be set automatically
        self.VERIFICATION_URL = os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000')
        if not self.VERIFICATION_URL.startswith('http'):
            self.VERIFICATION_URL = f"https://{self.VERIFICATION_URL}"
        
        # Discord API credentials for verification checks
        self.CLIENT_ID = os.environ.get('CLIENT_ID')
        self.CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info(f"Bot is starting up as {self.user}")
        
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    def is_admin(self, member: discord.Member) -> bool:
        """Check if member is admin, mod, or owner"""
        if member.guild_permissions.administrator:
            return True
        if member.id == member.guild.owner_id:
            return True
        # Check for common mod/admin roles
        admin_roles = ['admin', 'administrator', 'mod', 'moderator', 'owner']
        for role in member.roles:
            if role.name.lower() in admin_roles:
                return True
        return False

    async def check_donutsmp_membership(self, user_id: int) -> dict:
        """Check if user is in DonutSMP server or was banned/kicked"""
        try:
            guild = self.get_guild(self.DONUTSMP_ID)
            current_member = False
            was_banned = False
            ban_reason = None
            
            if guild:
                # Check if user is currently in the server
                member = guild.get_member(user_id)
                current_member = member is not None
                
                # Check if user is banned
                try:
                    ban_entry = await guild.fetch_ban(discord.Object(id=user_id))
                    was_banned = True
                    ban_reason = ban_entry.reason or "No reason provided"
                except discord.NotFound:
                    # User is not banned
                    pass
                except discord.Forbidden:
                    logger.warning("Bot doesn't have permission to check bans")
            else:
                logger.warning(f"Bot is not in DonutSMP server (ID: {self.DONUTSMP_ID})")
            
            # Check historical verification (fallback for old system)
            historically_verified = is_historically_verified(user_id)
            user_info = get_verified_user_info(user_id)
            
            # User is verified if they're current member, banned, or historically verified
            verified = current_member or was_banned or historically_verified
            
            # Status message
            if current_member:
                status = "Currently in DonutSMP"
            elif was_banned:
                status = f"Banned from DonutSMP: {ban_reason}"
            elif historically_verified:
                status = "Previously verified (historical)"
            else:
                status = "Never been in DonutSMP"
            
            return {
                'current_member': current_member,
                'was_banned': was_banned,
                'ban_reason': ban_reason,
                'historically_verified': historically_verified,
                'user_info': user_info,
                'verified': verified,
                'status': status
            }
        except Exception as e:
            logger.error(f"Error checking DonutSMP membership: {e}")
            return {
                'current_member': False,
                'was_banned': False,
                'ban_reason': None,
                'historically_verified': False,
                'user_info': None,
                'verified': False,
                'status': f'Error: {str(e)}'
            }

bot = DiscordBot()

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle verification button click"""
        verification_url = f"{bot.VERIFICATION_URL}/"
        
        embed = discord.Embed(
            title="🔐 Discord Verification",
            description="Click the link below to verify your DonutSMP membership:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Verification Link",
            value=f"[Click here to verify]({verification_url})",
            inline=False
        )
        embed.add_field(
            name="📋 Instructions",
            value="1. Click the verification link\n2. Login with Discord\n3. We'll check if you're in DonutSMP\n4. Return here once verified!",
            inline=False
        )
        embed.set_footer(text="Your data is not stored - we only check server membership")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ReviewModal(discord.ui.Modal):
    def __init__(self, target_user: discord.Member, admin_user: discord.Member):
        super().__init__(title="Submit Review")
        self.target_user = target_user
        self.admin_user = admin_user
        
        # Rating input (1-5 stars)
        self.rating = discord.ui.TextInput(
            label="Rating (1-5 stars)",
            placeholder="Enter a number from 1 to 5",
            min_length=1,
            max_length=1,
            required=True
        )
        self.add_item(self.rating)
        
        # Review message
        self.review_message = discord.ui.TextInput(
            label="Review Message (Optional)",
            placeholder="Enter your review message...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.review_message)
        
    async def on_submit(self, interaction: discord.Interaction):
        # Validate rating
        try:
            rating_value = int(self.rating.value)
            if rating_value < 1 or rating_value > 5:
                await interaction.response.send_message("❌ Rating must be between 1 and 5 stars!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Rating must be a number between 1 and 5!", ephemeral=True)
            return
        
        # Create star display
        stars = "⭐" * rating_value
        
        # Get vouches channel - look for #✅│vouches
        vouches_channel = None
        if bot.VOUCHES_CHANNEL_ID:
            vouches_channel = bot.get_channel(bot.VOUCHES_CHANNEL_ID)
        else:
            # Auto-find the vouches channel
            for channel in interaction.guild.channels:
                if isinstance(channel, discord.TextChannel) and "vouches" in channel.name.lower():
                    vouches_channel = channel
                    bot.VOUCHES_CHANNEL_ID = channel.id
                    break
        
        if not vouches_channel:
            await interaction.response.send_message("❌ Vouches channel not found. Make sure you have a channel with 'vouches' in the name!", ephemeral=True)
            return
        
        # Create embed
        embed = discord.Embed(
            title="🌟 Vouch",
            color=discord.Color.gold()
        )
        embed.add_field(name="User:", value=self.target_user.mention, inline=False)
        embed.add_field(name="Rating:", value=f"{stars} ({rating_value}/5)", inline=False)
        
        if self.review_message.value:
            embed.add_field(name="Review:", value=self.review_message.value, inline=False)
        
        # Get admin's top role
        admin_top_role = "No Role"
        if self.admin_user.roles:
            # Get highest role that's not @everyone
            roles = [role for role in self.admin_user.roles if role.name != "@everyone"]
            if roles:
                admin_top_role = max(roles, key=lambda r: r.position).name
        
        embed.set_footer(text=f"Submitted by {self.admin_user.display_name}, Role: {admin_top_role}")
        
        # Post to vouches channel
        message = await vouches_channel.send(embed=embed)
        
        # Add reactions
        await message.add_reaction("👍")
        await message.add_reaction("✅")
        
        await interaction.response.send_message(f"✅ Review submitted for {self.target_user.mention}!", ephemeral=True)

# Slash Commands
@bot.tree.command(name="verify", description="Display verification button")
async def verify_command(interaction: discord.Interaction):
    """Display the verification button"""
    embed = discord.Embed(
        title="🔐 DonutSMP Verification",
        description="Click the button below to verify your DonutSMP membership!",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📋 How it works:",
        value="1. Click the verify button\n2. Login with Discord\n3. We check if you're in DonutSMP\n4. Get verified instantly!",
        inline=False
    )
    embed.set_footer(text="Privacy focused - no data is stored")
    
    view = VerificationView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="rev", description="Send review prompt to a user")
@app_commands.describe(user="The user to send a review prompt to")
async def review_command(interaction: discord.Interaction, user: discord.Member):
    """Send a review prompt to a user (admin only)"""
    if not bot.is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    modal = ReviewModal(user, interaction.user)
    await interaction.response.send_modal(modal)

@bot.tree.command(name="smp", description="Check if user is DonutSMP related")
@app_commands.describe(user="The user to check")
async def check_donutsmp_command(interaction: discord.Interaction, user: discord.Member):
    """Check if a user is in DonutSMP (admin only)"""
    if not bot.is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    membership_info = await bot.check_donutsmp_membership(user.id)
    
    embed = discord.Embed(
        title="🔍 DonutSMP Membership Check",
        color=discord.Color.green() if membership_info['verified'] else discord.Color.red()
    )
    embed.add_field(name="User:", value=user.mention, inline=False)
    
    if membership_info['current_member']:
        embed.add_field(name="Current Member:", value="✅ Yes", inline=True)
        embed.add_field(name="Status:", value="Currently in DonutSMP", inline=True)
    elif membership_info['historically_verified']:
        embed.add_field(name="Current Member:", value="❌ No", inline=True)
        embed.add_field(name="Historical Member:", value="✅ Yes", inline=True)
        embed.add_field(name="Status:", value="Previously verified", inline=True)
        
        if membership_info['user_info']:
            first_verified = membership_info['user_info'].get('first_verified', 'Unknown')
            embed.add_field(name="First Verified:", value=first_verified[:10], inline=True)
    else:
        embed.add_field(name="Current Member:", value="❌ No", inline=True)
        embed.add_field(name="Historical Member:", value="❌ No", inline=True)
        embed.add_field(name="Status:", value="Never been in DonutSMP", inline=True)
    
    overall_status = "✅ Verified" if membership_info['verified'] else "❌ Not Verified"
    embed.add_field(name="Overall Status:", value=overall_status, inline=False)
    
    if not membership_info['verified']:
        embed.add_field(
            name="Add to Historical Database:", 
            value=f"```\npython seed_historical_users.py add {user.id} {user.display_name}\n```", 
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="add_historical", description="Add user to historical DonutSMP database")
@app_commands.describe(user="The user to add to historical database")
async def add_historical_command(interaction: discord.Interaction, user: discord.Member):
    """Add a user to the historical verification database (admin only)"""
    if not bot.is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    from verified_users import add_verified_user, is_historically_verified
    
    # Check if already in database
    if is_historically_verified(user.id):
        await interaction.response.send_message(f"ℹ️ {user.mention} is already in the historical database!", ephemeral=True)
        return
    
    # Add to database
    add_verified_user(user.id, user.display_name)
    
    embed = discord.Embed(
        title="✅ User Added to Historical Database",
        color=discord.Color.green()
    )
    embed.add_field(name="User:", value=user.mention, inline=False)
    embed.add_field(name="User ID:", value=f"`{user.id}`", inline=True)
    embed.add_field(name="Status:", value="Added as historical DonutSMP member", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_vouches_channel", description="Set the channel for vouches")
@app_commands.describe(channel="The channel to post vouches in")
async def set_vouches_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the vouches channel (admin only)"""
    if not bot.is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    bot.VOUCHES_CHANNEL_ID = channel.id
    await interaction.response.send_message(f"✅ Vouches channel set to {channel.mention}", ephemeral=True)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        logger.error(f"Command error: {error}")
        await ctx.send("❌ An error occurred while processing the command.")

# Run the bot
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        exit(1)
    
    bot.run(BOT_TOKEN)