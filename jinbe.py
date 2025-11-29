import discord
import asyncio
import json
import datetime
import os
import re
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === DATA PERSISTENCE SYSTEM ===

class DataManager:
    def __init__(self):
        self.data_file = "bot_data.json"
        self.data = self.load_data()
        
    def load_data(self):
        """Load data from JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "welcome_messages": {},
                "auto_mod": {"warnings": {}, "banned_users": {}},
                "server_configs": {}
            }
    
    def save_data(self):
        """Save data to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False
    
    def get_welcome_message(self, guild_id):
        return self.data["welcome_messages"].get(str(guild_id))
    
    def set_welcome_message(self, guild_id, message):
        self.data["welcome_messages"][str(guild_id)] = message
        self.save_data()
    
    def get_warnings(self, guild_id):
        return self.data["auto_mod"]["warnings"].get(str(guild_id), {})
    
    def add_warning(self, guild_id, user_id, warning_data):
        guild_id = str(guild_id)
        user_id = str(user_id)
        
        if guild_id not in self.data["auto_mod"]["warnings"]:
            self.data["auto_mod"]["warnings"][guild_id] = {}
            
        self.data["auto_mod"]["warnings"][guild_id][user_id] = warning_data
        self.save_data()
    
    def remove_warnings(self, guild_id, user_id):
        guild_id = str(guild_id)
        user_id = str(user_id)
        
        if guild_id in self.data["auto_mod"]["warnings"]:
            if user_id in self.data["auto_mod"]["warnings"][guild_id]:
                del self.data["auto_mod"]["warnings"][guild_id][user_id]
                self.save_data()
    
    def get_banned_users(self):
        return self.data["auto_mod"]["banned_users"]
    
    def add_banned_user(self, user_id, unban_time):
        self.data["auto_mod"]["banned_users"][str(user_id)] = unban_time.isoformat()
        self.save_data()
    
    def remove_banned_user(self, user_id):
        if str(user_id) in self.data["auto_mod"]["banned_users"]:
            del self.data["auto_mod"]["banned_users"][str(user_id)]

# Initialize data manager
data_manager = DataManager()

# === COMPREHENSIVE AUTO-MOD SYSTEM ===

class AdvancedAutoMod:
    def __init__(self):
        # Common bypass patterns
        self.bypass_patterns = {
            'nigger': [r'n[i1!|]gg[e3a4@]r?s?', r'n\s*[i1]\s*g\s*g\s*[e3a4]', r'n[i1]g{2,}[e3a4]'],
            'faggot': [r'f[a4@]gg?[o0]t?s?', r'f\s*a\s*g\s*g\s*o\s*t', r'f[a4]g{1,}[o0]t'],
            'retard': [r'r[e3]t[a4@]rd?s?', r'r\s*e\s*t\s*a\s*r\s*d', r'r[3e]t[4a]rd'],
            'bitch': [r'b[i1!|]tch', r'b\s*i\s*t\s*c\s*h', r'b[i1]tch'],
            'shit': [r'sh[i1!|]t', r's\s*h\s*i\s*t', r'sh[i1]t'],
            'fuck': [r'f[u]ck', r'f\s*u\s*c\s*k', r'f[u]ck'],
            'asshole': [r'a[ss]{2,}h[o0]l[e3]', r'a\s*s\s*s\s*h\s*o\s*l\s*e'],
            'whore': [r'wh[o0]r[e3]', r'w\s*h\s*o\s*r\s*e'],
            'cunt': [r'c[u]nt', r'c\s*u\s*n\s*t'],
            'kill yourself': [r'k[i1!]ll? yours?e?lf', r'kys', r'k\s*y\s*s']
        }
    
    async def check_message(self, message):
        """Comprehensive message checking"""
        if message.author.bot or message.author.guild_permissions.administrator:
            return False
            
        content = message.content.lower()
        
        # Check for bypass patterns
        if self.detect_bypass_patterns(content):
            return True
            
        # Check for leet speak variations
        if self.detect_leet_speak(content):
            return True
            
        return False
    
    def detect_bypass_patterns(self, text):
        """Detect common bypass attempts using regex"""
        for word, patterns in self.bypass_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
        return False
    
    def detect_leet_speak(self, text):
        """Detect leet speak variations"""
        # Common leet substitutions
        leet_patterns = [
            r'[nN][1i!|][9g6][9g6][3ea@][rR]',  # nigger variations
            r'[fF][4a@][9g6][9g6][0oO][7tT]',   # faggot variations
            r'[5sS][1i!|][7tT]',                # shit variations
            r'[bB][1i!|][7tT][cC][hH]',         # bitch variations
        ]
        
        for pattern in leet_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    async def handle_violation(self, message):
        """Handle auto-mod violation with progressive penalties"""
        user_id = message.author.id
        guild_id = message.guild.id
        
        # Get current warnings
        guild_warnings = data_manager.get_warnings(guild_id)
        user_warns = guild_warnings.get(str(user_id), {"count": 0, "history": []})
        
        # Increment warning count
        user_warns["count"] += 1
        user_warns["history"].append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "message": message.content[:100],
            "channel": message.channel.name
        })
        
        warn_count = user_warns["count"]
        
        # Save to data manager
        data_manager.add_warning(guild_id, user_id, user_warns)
        
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Send warning to user (without mentioning they were warned)
        await self.send_warning_dm(message.author, warn_count, message.content)
        
        # Log in staff channel
        await self.log_violation(message, warn_count)
        
        # Apply penalties
        await self.apply_penalties(message, warn_count)
    
    async def send_warning_dm(self, user, warn_count, original_message):
        """Send warning DM to user (without mentioning they were warned)"""
        try:
            embed = discord.Embed(
                title="🛡️ Message Notice",
                color=0xffa500,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            # Don't mention that they were warned - just send a general notice
            embed.add_field(
                name="Content Review",
                value="Your recent message has been reviewed by our moderation system.",
                inline=False
            )
            
            embed.add_field(
                name="Community Guidelines",
                value="Please ensure all messages follow our server rules and community guidelines.",
                inline=False
            )
            
            embed.set_footer(text="Thank you for helping keep our community respectful")
            
            await user.send(embed=embed)
        except:
            pass  # Can't DM user
    
    async def apply_penalties(self, message, warn_count):
        """Apply progressive penalties"""
        if warn_count == 3:
            # Temp ban for 1 hour
            try:
                await message.author.ban(
                    reason=f"Auto-mod: 3 warnings for inappropriate language",
                    delete_message_days=1
                )
                
                unban_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                data_manager.add_banned_user(message.author.id, unban_time)
                
                # Schedule unban
                asyncio.create_task(self.schedule_unban(message.guild, message.author, 3600))
                
            except Exception as e:
                print(f"Ban error: {e}")
                
        elif warn_count >= 5:
            # Permanent kick
            try:
                await message.author.kick(
                    reason=f"Auto-mod: 5 warnings for inappropriate language"
                )
                # Reset warnings after kick
                data_manager.remove_warnings(message.guild.id, message.author.id)
            except Exception as e:
                print(f"Kick error: {e}")
    
    async def schedule_unban(self, guild, user, delay_seconds):
        """Schedule automatic unban"""
        await asyncio.sleep(delay_seconds)
        try:
            await guild.unban(user)
            data_manager.remove_banned_user(user.id)
        except:
            pass
    
    async def log_violation(self, message, warn_count):
        """Log violation in staff channel"""
        staff_channel = discord.utils.get(message.guild.channels, name="🔧staff-chat")
        if not staff_channel:
            # Try to find any staff/admin channel
            for channel in message.guild.text_channels:
                if "staff" in channel.name.lower() or "admin" in channel.name.lower():
                    staff_channel = channel
                    break
        
        if not staff_channel:
            return
            
        embed = discord.Embed(
            title="🛡️ Auto-Mod Action Taken",
            color=0xff6b6b,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Warnings", value=f"{warn_count}/5", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        
        action_taken = "Message deleted + Notice sent"
        if warn_count == 3:
            action_taken = "🔨 Temporarily banned for 1 hour"
        elif warn_count >= 5:
            action_taken = "👢 Kicked from server"
            
        embed.add_field(name="Action Taken", value=action_taken, inline=False)
        embed.add_field(name="Message Content", value=f"``{message.content}```", inline=False)
        
        await staff_channel.send(embed=embed)

# Initialize advanced auto-mod
advanced_auto_mod = AdvancedAutoMod()

# === ADVANCED NSFW DETECTION ===

class NSFWDetector:
    def __init__(self):
        # Sexual content patterns
        self.sexual_patterns = [
            # Explicit sexual acts
            r'\b(sex|fuck|screw|bang|bone|shag|root)\b',
            r'\b(blowjob|bj|handjob|hj|titjob)\b',
            r'\b(oral|anal|vaginal|penetration)\b',
            r'\b(orgasm|climax|cum|sperm|ejaculation)\b',
            r'\b(masturbat|jack off|jerk off|wank)\b',
            
            # Body parts (sexual context)
            r'\b(dick|cock|penis|schlong)\b',
            r'\b(pussy|vagina|cunt|coochie)\b',
            r'\b(boobs|tits|breasts|nipples)\b',
            r'\b(ass|butt|booty|buns)\b',
            
            # Innuendo and slang
            r'\b(smash|hit that|tap that|get laid)\b',
            r'\b(hook up|one night stand|friends with benefits)\b',
            r'\b(sexy|horny|aroused|turned on)\b',
            
            # Requests and invitations
            r'\b(send nudes|send pics|show me|let me see)\b',
            r'\b(wanna fuck|want to fuck|down to fuck)\b',
            r'\b(cyber|cybersex|roleplay|rp)\b'
        ]
        
        # Contextual patterns that require multiple triggers
        self.contextual_patterns = {
            "sexual_activity": [r'want to', r'let\'s', r'we should', r'do you', r'can we'],
            "descriptive": [r'big', r'small', r'hard', r'wet', r'huge', r'tight'],
            "requests": [r'send', r'show', r'give me', r'let me see', r'wanna see']
        }
        
        self.severity_threshold = 2  # Minimum triggers for action
        
    async def detect_nsfw_conversation(self, message):
        """Detect NSFW conversations with context analysis"""
        if message.author.bot or (hasattr(message.channel, 'nsfw') and message.channel.nsfw):
            return False
            
        content = message.content.lower()
        
        # Check for explicit patterns
        explicit_matches = self.check_explicit_patterns(content)
        
        # Check for contextual patterns (more sophisticated)
        contextual_score = self.analyze_context(content)
        
        # Check message history for patterns
        history_score = await self.check_conversation_history(message)
        
        total_score = explicit_matches + contextual_score + history_score
        
        return total_score >= self.severity_threshold
    
    def check_explicit_patterns(self, text):
        """Check for explicit sexual content"""
        matches = 0
        for pattern in self.sexual_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        return matches
    
    def analyze_context(self, text):
        """Analyze context for suggestive conversations"""
        score = 0
        
        # Check for suggestive combinations
        if (any(re.search(pattern, text) for pattern in self.contextual_patterns["sexual_activity"]) and
            any(re.search(pattern, text) for pattern in self.contextual_patterns["descriptive"])):
            score += 2
            
        # Check for request patterns
        if (any(re.search(pattern, text) for pattern in self.contextual_patterns["requests"]) and
            any(word in text for word in ['nudes', 'pics', 'photos', 'pictures', 'body'])):
            score += 2
            
        return score
    
    async def check_conversation_history(self, message):
        """Check recent conversation history for patterns"""
        try:
            # Get last 10 messages in the channel
            messages = []
            async for msg in message.channel.history(limit=10):
                if msg.author == message.author and not msg.author.bot:
                    messages.append(msg.content.lower())
            
            # Analyze conversation patterns
            score = 0
            sexual_terms_count = 0
            request_patterns = 0
            
            for msg in messages:
                # Count sexual terms across conversation
                for pattern in self.sexual_patterns:
                    if re.search(pattern, msg):
                        sexual_terms_count += 1
                
                # Count request patterns
                if any(pattern in msg for pattern in ['send', 'show', 'wanna see', 'let me see']):
                    request_patterns += 1
            
            # Score based on conversation patterns
            if sexual_terms_count >= 3:
                score += 2
            if request_patterns >= 2:
                score += 1
                
            return score
            
        except:
            return 0
    
    async def handle_nsfw_violation(self, message, severity):
        """Handle NSFW conversation violations"""
        user_id = message.author.id
        guild_id = message.guild.id
        
        # Get current warnings
        guild_warnings = data_manager.get_warnings(guild_id)
        user_warns = guild_warnings.get(str(user_id), {"count": 0, "nsfw_count": 0, "history": []})
        
        # Increment NSFW-specific counter
        user_warns["nsfw_count"] += 1
        user_warns["history"].append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "type": "nsfw_conversation",
            "severity": severity,
            "message": message.content[:100],
            "channel": message.channel.name
        })
        
        # Save to data manager
        data_manager.add_warning(guild_id, user_id, user_warns)
        
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Send notice (without mentioning they were warned)
        await self.send_nsfw_notice(message.author, user_warns["nsfw_count"])
        
        # Log in staff channel
        await self.log_nsfw_violation(message, user_warns["nsfw_count"], severity)
        
        # Apply penalties for repeated NSFW violations
        await self.apply_nsfw_penalties(message, user_warns["nsfw_count"])
    
    async def send_nsfw_notice(self, user, nsfw_count):
        """Send NSFW notice DM (without mentioning they were warned)"""
        try:
            embed = discord.Embed(
                title="🔞 Content Notice",
                color=0xff6b6b,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            # Don't mention that they were warned - just send a general notice
            embed.add_field(
                name="Content Review",
                value="Your recent message has been reviewed by our content moderation system.",
                inline=False
            )
            
            embed.add_field(
                name="Community Guidelines",
                value="Please ensure all conversations are appropriate for all ages and follow our server rules.",
                inline=False
            )
            
            embed.add_field(
                name="NSFW Channels",
                value="For mature discussions, please use channels marked as NSFW.",
                inline=False
            )
            
            embed.set_footer(text="Thank you for helping keep our community family-friendly")
            
            await user.send(embed=embed)
        except:
            pass
    
    async def apply_nsfw_penalties(self, message, nsfw_count):
        """Apply penalties for NSFW violations"""
        if nsfw_count == 3:
            # Temp ban for NSFW content
            try:
                await message.author.ban(
                    reason="Auto-mod: 3 NSFW content violations",
                    delete_message_days=1
                )
                
                unban_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
                data_manager.add_banned_user(message.author.id, unban_time)
                
                asyncio.create_task(self.schedule_unban(message.guild, message.author, 7200))
                
            except Exception as e:
                print(f"NSFW ban error: {e}")
                
        elif nsfw_count >= 5:
            # Kick for excessive NSFW violations
            try:
                await message.author.kick(
                    reason="Auto-mod: Excessive NSFW content violations"
                )
                data_manager.remove_warnings(message.guild.id, message.author.id)
            except Exception as e:
                print(f"NSFW kick error: {e}")
    
    async def schedule_unban(self, guild, user, delay_seconds):
        """Schedule automatic unban"""
        await asyncio.sleep(delay_seconds)
        try:
            await guild.unban(user)
            data_manager.remove_banned_user(user.id)
        except:
            pass
    
    async def log_nsfw_violation(self, message, nsfw_count, severity):
        """Log NSFW violation in staff channel"""
        staff_channel = discord.utils.get(message.guild.channels, name="🔧staff-chat")
        if not staff_channel:
            # Try to find any staff/admin channel
            for channel in message.guild.text_channels:
                if "staff" in channel.name.lower() or "admin" in channel.name.lower():
                    staff_channel = channel
                    break
        
        if not staff_channel:
            return
            
        embed = discord.Embed(
            title="🔞 NSFW Content Detected",
            color=0xff6b6b,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="NSFW Warnings", value=f"{nsfw_count}/3", inline=True)
        embed.add_field(name="Severity", value=f"Level {severity}", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        
        action = "Message deleted + Notice sent"
        if nsfw_count == 3:
            action = "🔨 Temporarily banned for 2 hours"
        elif nsfw_count >= 5:
            action = "👢 Kicked from server"
            
        embed.add_field(name="Action Taken", value=action, inline=False)
        embed.add_field(name="Message Content", value=f"``{message.content}```", inline=False)
        
        await staff_channel.send(embed=embed)

# Initialize NSFW detector
nsfw_detector = NSFWDetector()

# === BLOX FRUITS CREW TEMPLATE ===

blox_fruits_template = {
    "name": "⚔️ Blox Fruits Crew Server",
    "description": "Perfect for Blox Fruits crews with automatic bounty roles and crew management",
    "roles": {
        "owner": {"name": "👑 Fleet Admiral", "permissions": ["administrator"], "color": 0xff0000},
        "vice_captain": {"name": "⭐ Vice Captain", "permissions": ["manage_messages", "kick_members"], "color": 0xffa500},
        "officer": {"name": "🔧 Officer", "permissions": ["manage_messages"], "color": 0x00ff00},
        
        # Auto bounty roles (will be created when users join)
        "5m_bounty": {"name": "🌊 5M Bounty", "permissions": ["read_messages"], "color": 0x00bfff},
        "5m_marine": {"name": "⚓ 5M Marine", "permissions": ["read_messages"], "color": 0x00bfff},
        "10m_bounty": {"name": "🌊 10M Bounty", "permissions": ["read_messages"], "color": 0x1e90ff},
        "10m_marine": {"name": "⚓ 10M Marine", "permissions": ["read_messages"], "color": 0x1e90ff},
        "15m_bounty": {"name": "🌊 15M Bounty", "permissions": ["read_messages"], "color": 0x4169e1},
        "15m_marine": {"name": "⚓ 15M Marine", "permissions": ["read_messages"], "color": 0x4169e1},
        "20m_bounty": {"name": "🌊 20M Bounty", "permissions": ["read_messages"], "color": 0x0000ff},
        "20m_marine": {"name": "⚓ 20M Marine", "permissions": ["read_messages"], "color": 0x0000ff},
        "30m_bounty": {"name": "🌊 30M Bounty", "permissions": ["read_messages"], "color": 0x8a2be2},
        "30m_marine": {"name": "⚓ 30M Marine", "permissions": ["read_messages"], "color": 0x8a2be2},
        
        "member": {"name": "🎮 Crew Member", "permissions": ["read_messages"], "color": 0x808080}
    },
    "categories": {
        "welcome": {"name": "🏴‍☠️ WELCOME ABOARD", "position": 0},
        "crew_management": {"name": "⚓ CREW MANAGEMENT", "position": 1},
        "battle_chat": {"name": "⚔️ BATTLE & STRATEGY", "position": 2},
        "trading": {"name": "💰 TRADING & FRUITS", "position": 3},
        "voice_crew": {"name": "🎧 VOICE CHAT", "position": 4},
        "staff": {"name": "👑 OFFICER QUARTERS", "position": 5}
    },
    "channels": {
        "welcome": [
            {"name": "📜crew-rules", "type": "text", "topic": "Crew rules and guidelines"},
            {"name": "👋welcome", "type": "text", "topic": "Welcome new crew members!"},
            {"name": "📢announcements", "type": "text", "topic": "Important crew announcements"}
        ],
        "crew_management": [
            {"name": "📋crew-applications", "type": "text", "topic": "Apply to join the crew"},
            {"name": "🔄crew-updates", "type": "text", "topic": "Crew status and updates"},
            {"name": "👥crew-chat", "type": "text", "topic": "General crew discussions"},
            {"name": "🎯bounty-board", "type": "text", "topic": "Bounty hunting targets and achievements"}
        ],
        "battle_chat": [
            {"name": "⚔️battle-strategy", "type": "text", "topic": "Battle tactics and strategies"},
            {"name": "🏆pvp-arena", "type": "text", "topic": "PvP discussions and matchmaking"},
            {"name": "🎮game-updates", "type": "text", "topic": "Latest Blox Fruits updates"}
        ],
        "trading": [
            {"name": "🍎fruit-trading", "type": "text", "topic": "Fruit trading and values"},
            {"name": "💎item-trading", "type": "text", "topic": "Item and gear trading"},
            {"name": "💰belli-making", "type": "text", "topic": "Money making strategies"}
        ],
        "voice_crew": [
            {"name": "General Voice", "type": "voice"},
            {"name": "Battle Planning", "type": "voice"},
            {"name": "Trading Hub", "type": "voice"},
            {"name": "AFK", "type": "voice"}
        ],
        "staff": [
            {"name": "🔧officer-chat", "type": "text", "topic": "Officer discussions"},
            {"name": "📊crew-stats", "type": "text", "topic": "Crew statistics and management"}
        ]
    }
}

# === AUTO CREW NAME ROLE SYSTEM ===

class BloxFruitsCrewSystem:
    def __init__(self):
        self.crew_roles = {}
    
    async def create_crew_role(self, guild, crew_name):
        """Create a custom role with the server's crew name"""
        # Clean the crew name for role creation
        clean_name = crew_name[:32]  # Discord role name limit
        role_name = f"🏴‍☠️ {clean_name}"
        
        # Check if role already exists
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            return existing_role
        
        # Create new crew role
        crew_role = await guild.create_role(
            name=role_name,
            color=0x8B4513,  # Brown color for pirate theme
            hoist=True,
            mentionable=True
        )
        
        return crew_role
    
    async def setup_bounty_roles(self, guild):
        """Setup all bounty and marine roles"""
        bounty_roles = {}
        
        bounty_levels = [
            ("5m_bounty", "🌊 5M Bounty", 0x00bfff),
            ("5m_marine", "⚓ 5M Marine", 0x00bfff),
            ("10m_bounty", "🌊 10M Bounty", 0x1e90ff),
            ("10m_marine", "⚓ 10M Marine", 0x1e90ff),
            ("15m_bounty", "🌊 15M Bounty", 0x4169e1),
            ("15m_marine", "⚓ 15M Marine", 0x4169e1),
            ("20m_bounty", "🌊 20M Bounty", 0x0000ff),
            ("20m_marine", "⚓ 20M Marine", 0x0000ff),
            ("30m_bounty", "🌊 30M Bounty", 0x8a2be2),
            ("30m_marine", "⚓ 30M Marine", 0x8a2be2)
        ]
        
        for role_key, role_name, color in bounty_levels:
            role = await guild.create_role(
                name=role_name,
                color=discord.Color(color),
                hoist=False,
                mentionable=False
            )
            bounty_roles[role_key] = role
        
        return bounty_roles

# Initialize crew system
blox_fruits_system = BloxFruitsCrewSystem()

# === YOUTUBE COMMUNITY TEMPLATE ===

youtube_template = {
    "name": "🎬 YouTube Community Server",
    "description": "Perfect for YouTube creators with milestone tracking and community engagement",
    "roles": {
        "owner": {"name": "🎬 Channel Owner", "permissions": ["administrator"], "color": 0xff0000},
        "content_creator": {"name": "📹 Content Creator", "permissions": ["manage_messages"], "color": 0x00ff00},
        "editor": {"name": "✂️ Editor", "permissions": ["attach_files"], "color": 0x9370db},
        "moderator": {"name": "🛡️ Moderator", "permissions": ["manage_messages"], "color": 0x00bfff},
        
        # Milestone roles (auto-assigned based on subscriber counts)
        "1k_subs": {"name": "🥉 1K Subscribers", "permissions": ["read_messages"], "color": 0xcd7f32},
        "10k_subs": {"name": "🥈 10K Subscribers", "permissions": ["read_messages"], "color": 0xc0c0c0},
        "25k_subs": {"name": "🥇 25K Subscribers", "permissions": ["read_messages"], "color": 0xffd700},
        "50k_subs": {"name": "💎 50K Subscribers", "permissions": ["read_messages"], "color": 0xb9f2ff},
        "100k_subs": {"name": "🏆 100K Subscribers", "permissions": ["read_messages"], "color": 0xff6b6b},
        "250k_subs": {"name": "🌟 250K Subscribers", "permissions": ["read_messages"], "color": 0x9b59b6},
        "500k_subs": {"name": "🚀 500K Subscribers", "permissions": ["read_messages"], "color": 0xe74c3c},
        "1m_subs": {"name": "👑 1M Subscribers", "permissions": ["read_messages"], "color": 0xf1c40f},
        
        "subscriber": {"name": "👍 Subscriber", "permissions": ["read_messages"], "color": 0x7289da}
    },
    "categories": {
        "welcome": {"name": "🎬 WELCOME", "position": 0},
        "content": {"name": "📹 CONTENT ZONE", "position": 1},
        "community": {"name": "💬 COMMUNITY CHAT", "position": 2},
        "collaborations": {"name": "🤝 COLLABORATIONS", "position": 3},
        "support": {"name": "💡 SUPPORT & FEEDBACK", "position": 4},
        "voice": {"name": "🎧 VOICE CHAT", "position": 5}
    },
    "channels": {
        "welcome": [
            {"name": "👋welcome", "type": "text", "topic": "Welcome to our YouTube community!"},
            {"name": "📋server-rules", "type": "text", "topic": "Community guidelines and rules"},
            {"name": "🎯announcements", "type": "text", "topic": "Channel announcements and updates"}
        ],
        "content": [
            {"name": "📢yt-announcements", "type": "text", "topic": "YouTube video announcements and updates"},
            {"name": "🎥yt-uploads", "type": "text", "topic": "Latest video uploads and discussions"},
            {"name": "📊milestone-tracker", "type": "text", "topic": "Channel growth and milestone celebrations"}
        ],
        "community": [
            {"name": "💬general", "type": "text", "topic": "General community discussions"},
            {"name": "💭feedback", "type": "text", "topic": "Video feedback and suggestions"},
            {"name": "🎮off-topic", "type": "text", "topic": "Off-topic discussions"}
        ],
        "collaborations": [
            {"name": "🤝collab-requests", "type": "text", "topic": "Collaboration opportunities"},
            {"name": "💼brand-deals", "type": "text", "topic": "Brand partnership discussions"}
        ],
        "support": [
            {"name": "❓q-and-a", "type": "text", "topic": "Questions and answers about content"},
            {"name": "💡video-ideas", "type": "text", "topic": "Suggest video ideas and topics"},
            {"name": "🔧technical-help", "type": "text", "topic": "Technical support and help"}
        ],
        "voice": [
            {"name": "General Voice", "type": "voice"},
            {"name": "Content Planning", "type": "voice"},
            {"name": "Community Hangout", "type": "voice"}
        ]
    }
}

# === YOUTUBE MILESTONE SYSTEM ===

class YouTubeMilestoneSystem:
    def __init__(self):
        self.milestone_channels = {}
        self.subscriber_roles = {
            1000: "1k_subs",
            10000: "10k_subs", 
            25000: "25k_subs",
            50000: "50k_subs",
            100000: "100k_subs",
            250000: "250k_subs", 
            500000: "500k_subs",
            1000000: "1m_subs"
        }
    
    async def setup_milestone_channels(self, guild):
        """Setup milestone tracking channels"""
        milestone_channels = {}
        
        milestone_levels = [
            ("1k_subs", "🥉 1K Subscribers"),
            ("10k_subs", "🥈 10K Subscribers"),
            ("25k_subs", "🥇 25K Subscribers"),
            ("50k_subs", "💎 50K Subscribers"),
            ("100k_subs", "🏆 100K Subscribers"),
            ("250k_subs", "🌟 250K Subscribers"),
            ("500k_subs", "🚀 500K Subscribers"),
            ("1m_subs", "👑 1M Subscribers")
        ]
        
        for role_key, role_name in milestone_levels:
            channel = await guild.create_text_channel(
                name=role_name,
                topic=f"Channel milestone: {role_name}"
            )
            milestone_channels[role_key] = channel
        
        return milestone_channels
    
    async def update_milestone(self, guild, subscriber_count):
        """Update milestone roles and channels"""
        milestone_levels = [
            (1000, "1k_subs"),
            (10000, "10k_subs"),
            (25000, "25k_subs"),
            (50000, "50k_subs"),
            (100000, "100k_subs"),
            (250000, "250k_subs"),
            (500000, "500k_subs"),
            (1000000, "1m_subs")
        ]
        
        for count, role_key in milestone_levels:
            if subscriber_count >= count:
                role = discord.utils.get(guild.roles, name=self.milestone_channels[role_key].name)
                if role:
                    await self.milestone_channels[role_key].send(f"🎉 Reached {count} subscribers!")
                    await self.assign_milestone_role(guild, role)
            else:
                break
    
    async def assign_milestone_role(self, guild, role):
        """Assign milestone role to all subscribers"""
        for member in guild.members:
            if not member.bot:
                await member.add_roles(role)

# Initialize milestone system
youtube_milestone_system = YouTubeMilestoneSystem()

# === REACTION ROLE SYSTEM ===

class ReactionRoleSystem:
    def __init__(self):
        self.reaction_roles = {}
    
    async def setup_reaction_roles(self, guild, category_id):
        category = guild.get_channel(category_id)
        if not category: 
            return False
        reaction_role_channel = await guild.create_text_channel(name=" реакција за улоге", category=category)
        self.reaction_roles[guild.id] = reaction_role_channel.id
        return True

reaction_role_system = ReactionRoleSystem()

# === TEMPORARY VOICE CHANNELS SYSTEM ===

class TempVoiceSystem:
    def __init__(self):
        self.temp_channels = {}
        self.creator_channels = {}
    
    async def setup_temp_voice(self, guild, category_id, creator_channel_name="➕ Create Voice"):
        category = guild.get_channel(category_id)
        if not category: 
            return False
        creator_channel = await guild.create_voice_channel(name=creator_channel_name, category=category)
        self.creator_channels[guild.id] = creator_channel.id
        return True

temp_voice_system = TempVoiceSystem()

class YouTubeMilestoneSystem:
    def __init__(self):
        self.milestone_channels = {}
        self.subscriber_roles = {
            1000: "1k_subs",
            10000: "10k_subs", 
            25000: "25k_subs",
            50000: "50k_subs",
            100000: "100k_subs",
            250000: "250k_subs", 
            500000: "500k_subs",
            1000000: "1m_subs"
        }
    
    async def setup_milestone_channels(self, guild):
        """Setup milestone tracking channels"""
        milestone_channels = {}
        
        milestone_levels = [
            ("1k_subs", "🥉 1K Subscribers"),
            ("10k_subs", "🥈 10K Subscribers"),
            ("25k_subs", "🥇 25K Subscribers"),
            ("50k_subs", "💎 50K Subscribers"),
            ("100k_subs", "🏆 100K Subscribers"),
            ("250k_subs", "🌟 250K Subscribers"),
            ("500k_subs", "🚀 500K Subscribers"),
            ("1m_subs", "👑 1M Subscribers")
        ]
        
        for role_key, role_name in milestone_levels:
            channel = await guild.create_text_channel(
                name=role_name,
                topic=f"Channel milestone: {role_name}"
            )
            milestone_channels[role_key] = channel
        
        return milestone_channels
    
    async def update_milestone(self, guild, subscriber_count):
        """Update milestone roles and channels"""
        milestone_levels = [
            (1000, "1k_subs"),
            (10000, "10k_subs"),
            (25000, "25k_subs"),
            (50000, "50k_subs"),
            (100000, "100k_subs"),
            (250000, "250k_subs"),
            (500000, "500k_subs"),
            (1000000, "1m_subs")
        ]
        
        for count, role_key in milestone_levels:
            if subscriber_count >= count:
                role = discord.utils.get(guild.roles, name=self.milestone_channels[role_key].name)
                if role:
                    await self.milestone_channels[role_key].send(f"🎉 Reached {count} subscribers!")
                    await self.assign_milestone_role(guild, role)
            else:
                break
    
    async def assign_milestone_role(self, guild, role):
        """Assign milestone role to all subscribers"""
        for member in guild.members:
            if not member.bot:
                await member.add_roles(role)

# Initialize milestone system
youtube_milestone_system = YouTubeMilestoneSystem()

# === ANTI SPAM SYSTEM ===

class AntiSpamSystem:
    def __init__(self):
        self.message_counts = {}
        self.spam_threshold = 5  # Number of messages in 10 seconds to trigger spam detection
        self.cooldown_duration = 10  # Cooldown duration in seconds
    
    async def check_message(self, message):
        """Check if a message is spam"""
        if message.author.bot:
            return False
        
        user_id = message.author.id
        guild_id = message.guild.id
        
        if guild_id not in self.message_counts:
            self.message_counts[guild_id] = {}
        
        if user_id not in self.message_counts[guild_id]:
            self.message_counts[guild_id][user_id] = []
        
        # Add message timestamp
        self.message_counts[guild_id][user_id].append(datetime.datetime.now(datetime.timezone.utc))
        
        # Remove old timestamps
        self.message_counts[guild_id][user_id] = [
            t for t in self.message_counts[guild_id][user_id]
            if t > datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=self.cooldown_duration)
        ]
        
        # Check if user has exceeded the spam threshold
        if len(self.message_counts[guild_id][user_id]) >= self.spam_threshold:
            return True
        
        return False
    
    async def handle_spam(self, message):
        """Handle spam detection"""
        user_id = message.author.id
        guild_id = message.guild.id
        
        # Get current warnings
        guild_warnings = data_manager.get_warnings(guild_id)
        user_warns = guild_warnings.get(str(user_id), {"count": 0, "history": []})
        
        # Increment warning count
        user_warns["count"] += 1
        user_warns["history"].append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "type": "spam",
            "message": message.content[:100],
            "channel": message.channel.name
        })
        
        warn_count = user_warns["count"]
        
        # Save to data manager
        data_manager.add_warning(guild_id, user_id, user_warns)
        
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Send warning to user (without mentioning they were warned)
        await self.send_spam_notice(message.author, warn_count)
        
        # Log in staff channel
        await self.log_spam_violation(message, warn_count)
        
        # Apply penalties
        await self.apply_spam_penalties(message, warn_count)
    
    async def send_spam_notice(self, user, warn_count):
        """Send spam notice DM (without mentioning they were warned)"""
        try:
            embed = discord.Embed(
                title="🚨 Spam Notice",
                color=0xff6b6b,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            # Don't mention that they were warned - just send a general notice
            embed.add_field(
                name="Content Review",
                value="Your recent message has been reviewed by our moderation system.",
                inline=False
            )
            
            embed.add_field(
                name="Community Guidelines",
                value="Please ensure all messages follow our server rules and community guidelines.",
                inline=False
            )
            
            embed.set_footer(text="Thank you for helping keep our community respectful")
            
            await user.send(embed=embed)
        except:
            pass  # Can't DM user
    
    async def apply_spam_penalties(self, message, warn_count):
        """Apply penalties for spam"""
        if warn_count == 3:
            # Temp ban for spamming
            try:
                await message.author.ban(
                    reason="Auto-mod: 3 spam warnings",
                    delete_message_days=1
                )
                
                unban_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                data_manager.add_banned_user(message.author.id, unban_time)
                
                # Schedule unban
                asyncio.create_task(self.schedule_unban(message.guild, message.author, 3600))
                
            except Exception as e:
                print(f"Spam ban error: {e}")
                
        elif warn_count >= 5:
            # Kick for excessive spamming
            try:
                await message.author.kick(
                    reason="Auto-mod: Excessive spam warnings"
                )
                data_manager.remove_warnings(message.guild.id, message.author.id)
            except Exception as e:
                print(f"Spam kick error: {e}")
    
    async def schedule_unban(self, guild, user, delay_seconds):
        """Schedule automatic unban"""
        await asyncio.sleep(delay_seconds)
        try:
            await guild.unban(user)
            data_manager.remove_banned_user(user.id)
        except:
            pass
    
    async def log_spam_violation(self, message, warn_count):
        """Log spam violation in staff channel"""
        staff_channel = discord.utils.get(message.guild.channels, name="🔧staff-chat")
        if not staff_channel:
            # Try to find any staff/admin channel
            for channel in message.guild.text_channels:
                if "staff" in channel.name.lower() or "admin" in channel.name.lower():
                    staff_channel = channel
                    break
        
        if not staff_channel:
            return
            
        embed = discord.Embed(
            title="🚨 Spam Detected",
            color=0xff6b6b,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Warnings", value=f"{warn_count}/5", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        
        action = "Message deleted + Notice sent"
        if warn_count == 3:
            action = "🔨 Temporarily banned for 1 hour"
        elif warn_count >= 5:
            action = "👢 Kicked from server"
            
        embed.add_field(name="Action Taken", value=action, inline=False)
        embed.add_field(name="Message Content", value=f"``{message.content}```", inline=False)
        
        await staff_channel.send(embed=embed)

# Initialize anti-spam system
anti_spam = AntiSpamSystem()

# Initialize YouTube system
youtube_system = YouTubeMilestoneSystem()

# === AUTO RULES SYSTEM ===

class RulesSystem:
    def __init__(self):
        self.default_rules = {
            "general": [
                "💬 **Be Respectful**: No harassment, hate speech, or discrimination",
                "🚫 **No Spamming**: Don't flood channels with messages",
            ],
            "nsfw": [
                "🔞 **No NSFW Content**: No explicit content in NSFW channels",
                "🚫 **No Spamming**: Don't flood channels with messages",
            ],
            "gaming": [
                "🎮 **Be Respectful**: No harassment, hate speech, or discrimination",
                "🚫 **No Spamming**: Don't flood channels with messages",
                "🎤 **Voice Chat Etiquette**: No earrape, background noise, or music without consent",
                "🔞 **NSFW Content**: Keep it appropriate for all ages",
                "⚔️ **Game Fairly**: No cheating, hacking, or exploiting",
                "📢 **Follow Discord TOS**: https://discord.com/terms"
            ],
            "music": [
                "🎵 **Share Responsively**: Only share music you have rights to",
                "🚫 **No Music Spam**: Don't flood with song links",
                "🎤 **Respect Artists**: No unauthorized distribution",
                "💬 **Constructive Feedback**: Be helpful in music discussions",
                "📢 **Follow Discord TOS**: https://discord.com/terms"
            ],
            "friends": [
                "👥 **Respect Privacy**: Don't share personal info without consent",
                "💬 **Be Kind**: No bullying or harassment",
                "📱 **No Spam**: Keep conversations meaningful",
                "🎮 **Game Together**: Invite others to join activities",
                "📢 **Follow Discord TOS**: https://discord.com/terms"
            ],
            "bloxfruits": [
                "🏴‍☠️ **Be Respectful**: No harassment, hate speech, or discrimination",
                "⚔️ **Game Fairly**: No cheating, exploiting, or hacking",
                "💰 **Trading Rules**: Use official trading channels only",
                "📢 **Follow Discord TOS**: https://discord.com/terms"
            ],
            "youtube": [
                "🎬 **Be Respectful**: No harassment, hate speech, or discrimination",
                "🚫 **No Spamming**: Don't flood channels with messages",
                "💬 **Constructive Feedback**: Be helpful in discussions",
                "📢 **Follow Discord TOS**: https://discord.com/terms"
            ]
        }

async def setup_rules_channel(guild, template_name, owner_role):
    """Create rules channel and post auto-generated rules"""
    # Check if a rules channel already exists in the welcome category
    welcome_category = discord.utils.get(guild.categories, name=lambda n: "WELCOME" in n.upper())
    
    # Check for existing rules channels with various possible names
    existing_rules_channel = None
    if welcome_category:
        for channel in welcome_category.text_channels:
            if any(rule_name in channel.name.lower() for rule_name in ["rules", "rule", "guidelines", "terms"]):
                existing_rules_channel = channel
                break
    
    # If no existing rules channel found, create one
    if not existing_rules_channel:
        rules_channel = await guild.create_text_channel(
            name="📜rules-config",
            topic="Server rules configuration - Only Owner & Bot can access"
        )
    else:
        # Use existing rules channel
        rules_channel = existing_rules_channel
    
    # Set permissions - only owner and bot can access (if we created a new channel)
    if not existing_rules_channel:
        await rules_channel.set_permissions(guild.default_role, view_channel=False)
        if owner_role:
            await rules_channel.set_permissions(owner_role, view_channel=True, send_messages=True)
        await rules_channel.set_permissions(guild.me, view_channel=True, send_messages=True)
    
    # Post auto-generated rules
    rules_system = RulesSystem()
    rules = rules_system.default_rules.get(template_name, [])
    
    # Check if rules message already exists to avoid duplicates
    try:
        async for message in rules_channel.history(limit=5):
            if "Auto-Generated Server Rules" in message.content or (message.embeds and message.embeds[0].title == "🛡️ Auto-Generated Server Rules"):
                # Rules message already exists, don't post again
                return rules_channel
    except:
        pass  # Continue with posting rules if we can't check history
    
    embed = discord.Embed(
        title="🛡️ Auto-Generated Server Rules",
        description="These rules were automatically generated for your server template.",
        color=0x00ff00
    )
    
    for i, rule in enumerate(rules, 1):
        embed.add_field(name=f"Rule #{i}", value=rule, inline=False)
    
    embed.add_field(
        name="⚙️ How to Edit Rules",
        value="Use `/editrules` to modify these rules. Only server owners can edit rules.",
        inline=False
    )
    
    await rules_channel.send(embed=embed)
    return rules_channel

# === WELCOME SYSTEM ===

class WelcomeSystem:
    def __init__(self):
        # Remove self.welcome_messages - now using data_manager
        pass
    
    def get_default_welcome(self, template_name):
        defaults = {
            "gaming": "🎮 Welcome {member} to our gaming community! Check out the rules and introduce yourself!",
            "music": "🎵 Welcome {member} to our music server! Share your favorite tracks and enjoy the vibe!",
            "friends": "👋 Hey {member}! Welcome to our friend group. Make yourself at home!",
            "bloxfruits": "🏴‍☠️ Ahoy {member}! Welcome aboard our Blox Fruits crew! Check the rules and introduce yourself!",
            "youtube": "🎬 Welcome {member} to our YouTube community! Don't forget to subscribe and introduce yourself!"
        }
        return defaults.get(template_name, "Welcome {member} to the server!")

welcome_system = WelcomeSystem()

# === STAFF CHANNEL SETUP ===

async def setup_staff_channel(guild, staff_roles):
    """Create staff-only channel"""
    try:
        staff_channel = await guild.create_text_channel(
            name="🔧staff-chat",
            topic="Staff discussions and coordination"
        )
        
        # Set permissions - only staff roles can access
        await staff_channel.set_permissions(guild.default_role, view_channel=False)
        for role in staff_roles:
            if role:  # Check if role exists
                await staff_channel.set_permissions(role, view_channel=True, send_messages=True)
        await staff_channel.set_permissions(guild.me, view_channel=True, send_messages=True)
        
        # Welcome message for staff
        embed = discord.Embed(
            title="👋 Welcome to Staff Chat",
            description="This channel is for staff discussions, coordination, and important server matters.",
            color=0x7289da
        )
        embed.add_field(
            name="Available Commands",
            value="• `/announce` - Make server announcements\n• `/welcome` - Set welcome message\n• `/editrules` - Modify server rules",
            inline=False
        )
        
        await staff_channel.send(embed=embed)
        return staff_channel
    except Exception as e:
        print(f"Staff channel setup error: {e}")
        return None

class TemplateSystem:
    """Advanced template management system"""
    
    def __init__(self):
        self.templates = self._load_templates()
        self.server_configs = {}
        self.backup_snapshots = {}
        
    def _load_templates(self) -> Dict:
        return {
            "gaming": {
                "name": "🎮 Ultimate Gaming Community",
                "description": "Complete gaming server with esports ready structure",
                "roles": {
                    "owner": {"name": "👑 Owner", "permissions": ["administrator"], "color": 0xff0000},
                    "head_admin": {"name": "⚡ Head Admin", "permissions": ["manage_guild", "manage_roles"], "color": 0xff4500},
                    "admin": {"name": "🔧 Admin", "permissions": ["manage_channels", "manage_messages"], "color": 0xffa500},
                    "moderator": {"name": "🛡️ Moderator", "permissions": ["manage_messages", "kick_members"], "color": 0x00ff00},
                    "event_host": {"name": "🎯 Event Host", "permissions": ["mute_members", "move_members"], "color": 0x9370db},
                    "vip_member": {"name": "⭐ VIP Member", "permissions": ["priority_speaker"], "color": 0xffff00},
                    "member": {"name": "🎮 Member", "permissions": ["read_messages"], "color": 0x00bfff}
                },
                "categories": {
                    "welcome": {"name": "🚀 WELCOME", "position": 0},
                    "main_chat": {"name": "💬 MAIN CHAT", "position": 1},
                    "gaming_zones": {"name": "🎮 GAMING ZONES", "position": 2},
                    "esports": {"name": "🏆 ESPORTS", "position": 3},
                    "voice_channels": {"name": "🎧 VOICE CHAT", "position": 4},
                    "staff": {"name": "🔧 STAFF ZONE", "position": 5}
                },
                "channels": {
                    "welcome": [
                        {"name": "📋rules", "type": "text", "topic": "Server rules and guidelines"},
                        {"name": "🎉welcome", "type": "text", "topic": "Welcome new members!"},
                        {"name": "📢announcements", "type": "text", "topic": "Important server announcements"}
                    ],
                    "main_chat": [
                        {"name": "💬general", "type": "text", "topic": "General discussion"},
                        {"name": "📸memes", "type": "text", "topic": "Share your favorite memes"},
                        {"name": "🎮gaming-news", "type": "text", "topic": "Latest gaming news"}
                    ],
                    "gaming_zones": [
                        {"name": "🎯fps-games", "type": "text", "topic": "FPS games discussion"},
                        {"name": "🧙rpg-games", "type": "text", "topic": "RPG games discussion"},
                        {"name": "🎲casual-games", "type": "text", "topic": "Casual games chat"}
                    ],
                    "esports": [
                        {"name": "🏆tournaments", "type": "text", "topic": "Tournament announcements"},
                        {"name": "📊leaderboards", "type": "text", "topic": "Server leaderboards"},
                        {"name": "🤝scrims", "type": "text", "topic": "Find scrim partners"}
                    ],
                    "voice_channels": [
                        {"name": "🎧General Voice", "type": "voice"},
                        {"name": "🎮Gaming Lobby 1", "type": "voice"},
                        {"name": "🎮Gaming Lobby 2", "type": "voice"},
                        {"name": "🏆Tournament Voice", "type": "voice"},
                        {"name": "🤫AFK", "type": "voice"}
                    ],
                    "staff": [
                        {"name": "🔧staff-chat", "type": "text", "topic": "Staff discussions"},
                        {"name": "📋staff-commands", "type": "text", "topic": "Bot command channel"}
                    ]
                }
            },
            "music": {
                "name": "🎵 Ultimate Music Community", 
                "description": "Perfect server for music lovers and creators",
                "roles": {
                    "owner": {"name": "👑 Owner", "permissions": ["administrator"], "color": 0xff0000},
                    "curator": {"name": "🎼 Curator", "permissions": ["manage_messages", "manage_roles"], "color": 0x00ff00},
                    "dj": {"name": "🎧 DJ", "permissions": ["priority_speaker", "mute_members"], "color": 0x9370db},
                    "artist": {"name": "🎤 Artist", "permissions": ["attach_files"], "color": 0xff69b4},
                    "member": {"name": "🎵 Listener", "permissions": ["read_messages"], "color": 0x00bfff}
                },
                "categories": {
                    "welcome": {"name": "🎵 WELCOME", "position": 0},
                    "music_chat": {"name": "💬 MUSIC CHAT", "position": 1},
                    "genres": {"name": "🎶 MUSIC GENRES", "position": 2},
                    "events": {"name": "🎪 EVENTS", "position": 3},
                    "voice_stages": {"name": "🎤 VOICE & STAGES", "position": 4}
                },
                "channels": {
                    "welcome": [
                        {"name": "🎵welcome", "type": "text", "topic": "Welcome to our music community!"},
                        {"name": "📋rules", "type": "text", "topic": "Server rules and guidelines"},
                        {"name": "🎼introductions", "type": "text", "topic": "Introduce yourself!"},
                        {"name": "📢announcements", "type": "text", "topic": "Important server announcements"}
                    ],
                    "music_chat": [
                        {"name": "💬general", "type": "text", "topic": "General music discussion"},
                        {"name": "🎧song-requests", "type": "text", "topic": "Request your favorite songs"},
                        {"name": "📻music-news", "type": "text", "topic": "Latest music news"}
                    ],
                    "genres": [
                        {"name": "🎸rock-metal", "type": "text", "topic": "Rock and Metal discussion"},
                        {"name": "🎹electronic", "type": "text", "topic": "Electronic music lovers"},
                        {"name": "🎤hiphop-rap", "type": "text", "topic": "HipHop & Rap zone"},
                        {"name": "🎼classical-jazz", "type": "text", "topic": "Classical and Jazz"}
                    ],
                    "events": [
                        {"name": "🎪events", "type": "text", "topic": "Upcoming music events"},
                        {"name": "🏆charts", "type": "text", "topic": "Weekly music charts"},
                        {"name": "🎵spotify-playlists", "type": "text", "topic": "Share your playlists"}
                    ],
                    "voice_stages": [
                        {"name": "🎧Music Lounge", "type": "voice"},
                        {"name": "🎤Live Stage", "type": "stage"},
                        {"name": "🎼Chill Zone", "type": "voice"},
                        {"name": "🎶Listening Party", "type": "voice"}
                    ]
                }
            },
            "friends": {
                "name": "👥 Ultimate Friends Hangout",
                "description": "Cozy server for friends and small communities",
                "roles": {
                    "owner": {"name": "👑 Owner", "permissions": ["administrator"], "color": 0xff0000},
                    "member": {"name": "😊 Friend", "permissions": ["read_messages"], "color": 0x00bfff}
                },
                "categories": {
                    "welcome": {"name": "👋 WELCOME", "position": 0},
                    "main_chat": {"name": "💬 CHAT ZONE", "position": 1},
                    "media": {"name": "📸 MEDIA", "position": 2},
                    "activities": {"name": "🎮 ACTIVITIES", "position": 3},
                    "voice": {"name": "🎧 VOICE CHAT", "position": 4}
                },
                "channels": {
                    "welcome": [
                        {"name": "👋welcome", "type": "text", "topic": "Welcome to our friend group!"},
                        {"name": "📋server-info", "type": "text", "topic": "Server information"},
                        {"name": "📢announcements", "type": "text", "topic": "Important server announcements"}
                    ],
                    "main_chat": [
                        {"name": "💬general", "type": "text", "topic": "General chat"},
                        {"name": "🤪random", "type": "text", "topic": "Random discussions"},
                        {"name": "💭thoughts", "type": "text", "topic": "Share your thoughts"}
                    ],
                    "media": [
                        {"name": "📸photos", "type": "text", "topic": "Share your photos"},
                        {"name": "🎬videos", "type": "text", "topic": "Share interesting videos"},
                        {"name": "🎵music", "type": "text", "topic": "Music recommendations"}
                    ],
                    "activities": [
                        {"name": "🎮gaming", "type": "text", "topic": "Gaming discussions"},
                        {"name": "🎬movie-night", "type": "text", "topic": "Movie night planning"},
                        {"name": "🍿recommendations", "type": "text", "topic": "Share recommendations"}
                    ],
                    "voice": [
                        {"name": "🎧General Voice", "type": "voice"},
                        {"name": "🎮Gaming Voice", "type": "voice"},
                        {"name": "🍿Chill Zone", "type": "voice"},
                        {"name": "💤AFK", "type": "voice"}
                    ]
                }
            },
            "bloxfruits": blox_fruits_template,
            "youtube": youtube_template
        }

    def get_template(self, name: str) -> Optional[Dict]:
        """Get template by name"""
        return self.templates.get(name)

class TemplateSelectView(View):
    """Interactive template selection view"""
    
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        self.value = None
        
    @discord.ui.select(
        placeholder="Choose a template...",
        options=[
            discord.SelectOption(label="🎮 Gaming Community", value="gaming", description="Complete gaming server with esports setup"),
            discord.SelectOption(label="🎵 Music Community", value="music", description="Perfect for music lovers and creators"),
            discord.SelectOption(label="👥 Friends Hangout", value="friends", description="Cozy server for friends"),
            discord.SelectOption(label="⚔️ Blox Fruits Crew", value="bloxfruits", description="Perfect for Blox Fruits crews with automatic bounty roles"),
            discord.SelectOption(label="🎬 YouTube Community", value="youtube", description="Perfect for YouTube creators with milestone tracking")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.value = select.values[0]
        await interaction.response.send_message(f"✅ Selected {select.values[0]} template! Use `/apply {select.values[0]}` to create it.", ephemeral=True)
        self.stop()

class AdvancedTemplateBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='/', intents=intents, help_command=None)
        self.template_system = TemplateSystem()
        self.setup_complete = False
        
    async def setup_hook(self):
        """Bot startup tasks"""
        # Note: auto_backup will be started in on_ready
        
    @tasks.loop(hours=24)
    async def auto_backup(self):
        """Auto backup template configurations"""
        try:
            print("Auto-backup completed")
        except Exception as e:
            print(f"Auto-backup error: {e}")
        
    async def on_ready(self):
        print(f'🤖 {self.user.name} is online!')
        print(f'📊 Serving {len(self.guilds)} servers')
        
        # Try global sync first for better reliability
        try:
            synced = await self.tree.sync()
            print(f"✅ Global commands synced: {len(synced)} commands")
        except Exception as e:
            print(f"❌ Global sync failed: {e}")
        
        # Then try per-guild sync as fallback
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=guild)
                print(f"✅ Commands synced for guild: {guild.name}")
            except Exception as e:
                print(f"⚠️ Guild sync failed for {guild.name}: {e}")
        
        # Set bot avatar if not already set
        try:
            if self.user.avatar is None:
                print("⚠️ Bot avatar not set. Consider setting an avatar in the Discord Developer Portal.")
        except Exception as e:
            print(f"⚠️ Avatar check error: {e}")
        
        # Restore active temp bans
        await self.restore_active_bans()
        
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/help for templates"))
        self.auto_backup.start()
        
    async def restore_active_bans(self):
        """Restore active temporary bans on bot restart"""
        banned_users = data_manager.get_banned_users()
        current_time = datetime.datetime.now(datetime.timezone.utc)
        
        # Create a copy of the dictionary to avoid RuntimeError during iteration
        banned_users_copy = dict(banned_users)
        
        for user_id_str, unban_time_str in banned_users_copy.items():
            try:
                unban_time = datetime.datetime.fromisoformat(unban_time_str)
                if unban_time > current_time:
                    # Schedule unban for remaining time
                    remaining = (unban_time - current_time).total_seconds()
                    user_id = int(user_id_str)
                    
                    # Find user in any guild
                    for guild in self.guilds:
                        try:
                            user = await guild.fetch_member(user_id)
                            if user:
                                asyncio.create_task(advanced_auto_mod.schedule_unban(guild, user, remaining))
                                break
                        except:
                            continue
                else:
                    # Remove expired bans
                    data_manager.remove_banned_user(user_id_str)
            except Exception as e:
                print(f"Error restoring ban for {user_id_str}: {e}")

    async def on_member_join(self, member):
        """Enhanced welcome system for new members"""
        try:
            # Auto assign member role based on template type
            member_role = None
            
            # Detect template type by checking for template-specific channels
            gaming_channel = discord.utils.get(member.guild.channels, name="🎮gaming-news")
            music_channel = discord.utils.get(member.guild.channels, name="🎧song-requests")
            blox_fruits_channel = discord.utils.get(member.guild.channels, name="📜crew-rules")
            youtube_channel = discord.utils.get(member.guild.channels, name="📊milestone-tracker")
            
            # Assign appropriate role based on detected template
            if blox_fruits_channel:
                # Blox Fruits template
                member_role = discord.utils.get(member.guild.roles, name="🎮 Crew Member")
            elif youtube_channel:
                # YouTube template
                member_role = discord.utils.get(member.guild.roles, name="👍 Subscriber")
            elif gaming_channel:
                # Gaming template
                member_role = discord.utils.get(member.guild.roles, name="🎮 Member")
            elif music_channel:
                # Music template
                member_role = discord.utils.get(member.guild.roles, name="🎵 Listener")
            else:
                # Friends template (default/fallback)
                member_role = discord.utils.get(member.guild.roles, name="😊 Friend")
                
            # If no template-specific role found, try generic ones
            if not member_role:
                member_role = discord.utils.get(member.guild.roles, name="Member")
            if not member_role:
                member_role = discord.utils.get(member.guild.roles, name="🎮 Member")
            if not member_role:
                member_role = discord.utils.get(member.guild.roles, name="🎵 Listener")
            if not member_role:
                member_role = discord.utils.get(member.guild.roles, name="😊 Friend")
                
            if member_role:
                try:
                    await member.add_roles(member_role)
                except Exception as e:
                    print(f"Could not assign member role: {e}")
            
            # Find welcome channel (check multiple possible names)
            welcome_channel = discord.utils.get(member.guild.channels, name="welcome")
            if not welcome_channel:
                welcome_channel = discord.utils.get(member.guild.channels, name="🎉welcome")
            if not welcome_channel:
                welcome_channel = discord.utils.get(member.guild.channels, name="👋welcome")
                
            # If still not found, we don't create one automatically to avoid duplicates
            # The template should already have created one
            
            if welcome_channel and welcome_channel.permissions_for(member.guild.me).send_messages:
                # Get welcome message from data_manager
                welcome_message = data_manager.get_welcome_message(member.guild.id)
                if not welcome_message:
                    # Detect template type and use appropriate default
                    gaming_channel = discord.utils.get(member.guild.channels, name="🎮gaming-news")
                    music_channel = discord.utils.get(member.guild.channels, name="🎧song-requests")
                    
                    if gaming_channel:
                        welcome_message = welcome_system.get_default_welcome("gaming")
                    elif music_channel:
                        welcome_message = welcome_system.get_default_welcome("music")
                    else:
                        welcome_message = welcome_system.get_default_welcome("friends")
                
                # Format welcome message with support for multiple placeholder variations
                formatted_message = welcome_message
                replacements = {
                    '{member}': member.mention,
                    '{user}': member.mention,
                    '{mention}': member.mention,
                    '{name}': member.name,
                    '{username}': member.name,
                    '{server}': member.guild.name,
                    '{guild}': member.guild.name,
                    '{count}': str(len(member.guild.members)),
                    '{members}': str(len(member.guild.members)),
                    '{membercount}': str(len(member.guild.members))
                }
                
                for placeholder, value in replacements.items():
                    formatted_message = formatted_message.replace(placeholder, value)
                
                embed = discord.Embed(
                    title=f"🎉 Welcome {member.name}!",
                    description=formatted_message,
                    color=0x00ff00
                )
                embed.add_field(name="Member Count", value=f"#{len(member.guild.members)}", inline=True)
                # Fix the deprecated datetime.utcnow() warning
                embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text=f"ID: {member.id}")
                
                await welcome_channel.send(embed=embed)
                
        except Exception as e:
            print(f"Welcome error: {e}")
            
    async def on_message(self, message):
        if message.guild and not message.author.bot:
            # Check for bad words first
            if await advanced_auto_mod.check_message(message):
                await advanced_auto_mod.handle_violation(message)
            
            # Then check for NSFW conversations (separate system)
            elif await nsfw_detector.detect_nsfw_conversation(message):
                severity = nsfw_detector.check_explicit_patterns(message.content)
                await nsfw_detector.handle_nsfw_violation(message, severity)
    
        await bot.process_commands(message)

async def delete_all_channels(guild):
    """Delete ALL existing channels in the server"""
    try:
        # Delete all text channels
        for channel in guild.text_channels:
            try:
                await channel.delete()
                await asyncio.sleep(0.5)  # Rate limit protection
            except Exception as e:
                print(f"Error deleting text channel {channel.name}: {e}")
                continue
        
        # Delete all voice channels
        for channel in guild.voice_channels:
            try:
                await channel.delete()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error deleting voice channel {channel.name}: {e}")
                continue
        
        # Delete all stage channels
        for channel in guild.stage_channels:
            try:
                await channel.delete()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error deleting stage channel {channel.name}: {e}")
                continue
        
        # Delete all categories
        for category in guild.categories:
            try:
                await category.delete()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error deleting category {category.name}: {e}")
                continue
                
        return True
    except Exception as e:
        print(f"Error in delete_all_channels: {e}")
        return False

async def delete_template_roles(guild):
    """Delete template-specific roles to prevent role accumulation"""
    try:
        # List of template-specific role names to delete
        template_role_names = [
            # Gaming template roles
            "👑 Owner", "⚡ Head Admin", "🔧 Admin", "🛡️ Moderator", 
            "🎯 Event Host", "⭐ VIP Member", "🎮 Member",
            
            # Music template roles
            "🎼 Curator", "🎧 DJ", "🎤 Artist", "🎵 Listener",
            
            # Friends template roles
            "😊 Friend",
            
            # Blox Fruits template roles
            "🏴‍☠️ Fleet Admiral", "⭐ Vice Captain", "🔧 Officer", 
            "🎮 Crew Member", "🌊 5M Bounty", "⚓ 5M Marine",
            "🌊 10M Bounty", "⚓ 10M Marine", "🌊 15M Bounty", "⚓ 15M Marine",
            "🌊 20M Bounty", "⚓ 20M Marine", "🌊 30M Bounty", "⚓ 30M Marine",
            
            # YouTube template roles
            "🎬 Channel Owner", "📹 Content Creator", "✂️ Editor", "🛡️ Moderator",
            "🥉 1K Subscribers", "🥈 10K Subscribers", "🥇 25K Subscribers",
            "💎 50K Subscribers", "🏆 100K Subscribers", "🌟 250K Subscribers",
            "🚀 500K Subscribers", "👑 1M Subscribers", "👍 Subscriber"
        ]
        
        # Delete template-specific roles
        deleted_count = 0
        for role in guild.roles:
            # Skip @everyone role and bot's own role
            if role.name == "@everyone" or role.managed:
                continue
                
            # Check if role name matches any template role
            if role.name in template_role_names:
                try:
                    await role.delete()
                    deleted_count += 1
                    print(f"Deleted template role: {role.name}")
                    await asyncio.sleep(0.5)  # Rate limit protection
                except Exception as e:
                    print(f"Error deleting role {role.name}: {e}")
                    continue
        
        print(f"Deleted {deleted_count} template-specific roles")
        return True
    except Exception as e:
        print(f"Error in delete_template_roles: {e}")
        return False

# Initialize bot
bot = AdvancedTemplateBot()

# === SLASH COMMANDS ===

@bot.tree.command(name="templates", description="View available templates with interactive menu")
async def templates(interaction: discord.Interaction):
    """Show available templates with interactive menu"""
    # Check if user is server owner
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎨 Available Server Templates",
        description="Choose from our professionally designed templates:",
        color=0x7289da
    )
    
    templates = bot.template_system.templates
    for template_id, template in templates.items():
        embed.add_field(
            name=f"{template['name']}",
            value=f"{template['description']}\nUse `/apply {template_id}`",
            inline=False
        )
    
    embed.set_footer(text="React with 🎮, 🎵, or 👥 to select a template")
    view = TemplateSelectView(bot)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    # Add reaction buttons for quick selection
    try:
        # Get the message that was just sent
        message = await interaction.original_response()
        await message.add_reaction("🎮")
        await message.add_reaction("🎵") 
        await message.add_reaction("👥")
    except:
        pass

@bot.tree.command(name="apply", description="Apply a template to the server (WILL DELETE ALL EXISTING CHANNELS)")
@discord.app_commands.describe(template_name="The template to apply: gaming, music, friends, bloxfruits, or youtube")
async def apply(interaction: discord.Interaction, template_name: str = None):
    """Apply a template to the server (WILL DELETE ALL EXISTING CHANNELS)"""
    
    # Check if user is server owner
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        return
    
    if not template_name:
        await interaction.response.send_message("❌ Please specify a template: `/apply gaming`, `/apply music`, `/apply friends`, `/apply bloxfruits`, or `/apply youtube`", ephemeral=True)
        return
        
    template_name = template_name.lower()
    templates = bot.template_system.templates
    
    if template_name not in templates:
        await interaction.response.send_message("❌ Invalid template. Use `/templates` to see available options.", ephemeral=True)
        return
        
    template = templates[template_name]
    
    # WARNING embed - this is destructive!
    embed = discord.Embed(
        title=f"⚠️ DANGEROUS ACTION: Applying {template['name']}",
        description="**THIS WILL DELETE ALL EXISTING CHANNELS AND CATEGORIES!**",
        color=0xff0000
    )
    embed.add_field(
        name="🚨 WARNING", 
        value="• All current channels will be PERMANENTLY deleted\n• All categories will be removed\n• Only roles and members will be preserved\n• This action cannot be undone!",
        inline=False
    )
    embed.add_field(name="New Template Includes", value=f"• {len(template['roles'])} Roles\n• {len(template['categories'])} Categories\n• Multiple new channels", inline=False)
    embed.add_field(name="Estimated Time", value="60-90 seconds", inline=True)
    
    # Send the warning message
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Since we can't use buttons with slash commands in this context, we'll proceed directly
    await setup_template(interaction, template_name, template)

async def setup_template(interaction: discord.Interaction, template_name: str, template: dict):
    """Main template setup function - DELETES ALL EXISTING CHANNELS FIRST"""
    
    guild = interaction.guild
    
    try:
        # Send initial progress message to the first available channel
        progress_channel = None
        progress_msg = None
        
        # Try to find an existing channel for progress updates
        for chan in guild.text_channels:
            if chan.permissions_for(guild.me).send_messages:
                progress_channel = chan
                break
        
        # If no channel available, we'll send updates via DM until we can create channels
        if not progress_channel:
            try:
                await interaction.user.send("🔄 **Starting DESTRUCTIVE template setup...** (0%) - Please check your server for progress updates.")
            except:
                pass  # Can't DM user
        
        # If we found a channel, send the initial progress message
        if progress_channel:
            try:
                progress_msg = await progress_channel.send("🔄 **Starting DESTRUCTIVE template setup...** (0%)")
            except:
                pass
        
        # === STEP 1: DELETE ALL EXISTING CHANNELS (25%) ===
        if progress_msg:
            try:
                await progress_msg.edit(content="🗑️ **DELETING ALL EXISTING CHANNELS...** (25%)")
            except:
                # If we can't edit the message, try to send a new one
                try:
                    progress_msg = await progress_channel.send("🗑️ **DELETING ALL EXISTING CHANNELS...** (25%)")
                except:
                    pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🗑️ **DELETING ALL EXISTING CHANNELS...** (25%)")
            except:
                pass
        
        # Delete all existing channels
        deletion_success = await delete_all_channels(guild)
        if not deletion_success:
            error_msg = "❌ Failed to delete some existing channels. Setup cancelled."
            if progress_msg:
                try:
                    await progress_msg.edit(content=error_msg)
                except:
                    # Try to send a new message
                    try:
                        if progress_channel:
                            await progress_channel.send(error_msg)
                    except:
                        pass
            # Send error message to user
            try:
                await interaction.user.send(error_msg)
            except:
                pass
            return
            
        # Delete template-specific roles to prevent accumulation
        await delete_template_roles(guild)
        await asyncio.sleep(2)
            
        await asyncio.sleep(2)
        
        # After deletion, we need to create a new channel for progress updates
        progress_channel = None
        progress_msg = None
        
        # Create a temporary category and channel for progress updates
        try:
            temp_category = await guild.create_category("⚙️ Setup Progress")
            progress_channel = await guild.create_text_channel("📋setup-progress", category=temp_category)
        except Exception as e:
            # If we can't create channels, continue with DM updates
            try:
                await interaction.user.send("🔄 **Creating temporary progress channel...** (30%)")
            except:
                pass
        
        # If we successfully created a progress channel, send update
        if progress_channel:
            try:
                progress_msg = await progress_channel.send("🔄 **Creating temporary progress channel...** (30%)")
            except:
                pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🔄 **Creating roles...** (50%)")
            except:
                pass
        
        # === STEP 2: Create Roles (50%) ===
        if progress_msg:
            try:
                await progress_msg.edit(content="🔄 **Creating roles...** (50%)")
            except:
                # Try to send a new message
                try:
                    progress_msg = await progress_channel.send("🔄 **Creating roles...** (50%)")
                except:
                    pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🔄 **Creating roles...** (50%)")
            except:
                pass
                
        role_mapping = {}
        
        for role_key, role_data in template['roles'].items():
            try:
                # Check if role already exists
                existing_role = discord.utils.get(guild.roles, name=role_data['name'])
                if existing_role:
                    role_mapping[role_key] = existing_role
                    continue
                    
                # Create new role
                permissions = discord.Permissions()
                for perm in role_data.get('permissions', []):
                    setattr(permissions, perm, True)
                    
                new_role = await guild.create_role(
                    name=role_data['name'],
                    permissions=permissions,
                    color=discord.Color(role_data.get('color', 0x000000)),
                    hoist=True if role_key in ['owner', 'admin', 'moderator'] else False,
                    mentionable=True if role_key in ['owner', 'admin'] else False
                )
                role_mapping[role_key] = new_role
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Role creation error: {e}")
                continue
        
        # === STEP 3: Create Categories (75%) ===
        if progress_msg:
            try:
                await progress_msg.edit(content="🔄 **Creating categories...** (75%)")
            except:
                # Try to send a new message
                try:
                    progress_msg = await progress_channel.send("🔄 **Creating categories...** (75%)")
                except:
                    pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🔄 **Creating categories...** (75%)")
            except:
                pass
                
        category_mapping = {}
        
        for cat_key, cat_data in template['categories'].items():
            try:
                new_category = await guild.create_category(
                    name=cat_data['name'],
                    position=cat_data.get('position', 0)
                )
                category_mapping[cat_key] = new_category
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Category creation error: {e}")
                continue
        
        # === STEP 4: Create Channels (90%) ===
        if progress_msg:
            try:
                await progress_msg.edit(content="🔄 **Creating channels...** (90%)")
            except:
                # Try to send a new message
                try:
                    progress_msg = await progress_channel.send("🔄 **Creating channels...** (90%)")
                except:
                    pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🔄 **Creating channels...** (90%)")
            except:
                pass
        
        channel_count = 0
        for cat_key, channels in template['channels'].items():
            if cat_key not in category_mapping:
                continue
                
            category = category_mapping[cat_key]
            
            for channel_data in channels:
                try:
                    if channel_data['type'] == 'text':
                        new_channel = await guild.create_text_channel(
                            name=channel_data['name'],
                            category=category,
                            topic=channel_data.get('topic', '')
                        )
                    elif channel_data['type'] == 'voice':
                        new_channel = await guild.create_voice_channel(
                            name=channel_data['name'],
                            category=category
                        )
                    elif channel_data['type'] == 'stage':
                        new_channel = await guild.create_stage_channel(
                            name=channel_data['name'],
                            category=category
                        )
                    
                    channel_count += 1
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    print(f"Channel creation error: {e}")
                    continue
        
        # === STEP 5: Setup New Features (95%) ===
        if progress_msg:
            try:
                await progress_msg.edit(content="🔄 **Setting up additional features...** (95%)")
            except:
                # Try to send a new message
                try:
                    progress_msg = await progress_channel.send("🔄 **Setting up additional features...** (95%)")
                except:
                    pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🔄 **Setting up additional features...** (95%)")
            except:
                pass
        
        # Get owner role
        owner_role = discord.utils.get(guild.roles, name="👑 Owner")
        if not owner_role:
            owner_role = discord.utils.get(guild.roles, name="Owner")
        
        # Get staff roles (only from roles that were actually created)
        staff_roles = []
        staff_role_names = ["👑 Owner", "⚡ Head Admin", "🔧 Admin", "🛡️ Moderator", "Owner", "Admin", "Moderator"]
        for role_key, role_data in template['roles'].items():
            if role_data['name'] in staff_role_names:
                if role_key in role_mapping:
                    staff_roles.append(role_mapping[role_key])
        
        # Setup new features
        await setup_rules_channel(guild, template_name, owner_role)
        await setup_staff_channel(guild, staff_roles)
        
        # Set up basic permissions
        try:
            staff_category = category_mapping.get('staff')
            if staff_category:
                await staff_category.set_permissions(guild.default_role, view_channel=False)
                
            if staff_category and role_mapping.get('moderator'):
                await staff_category.set_permissions(role_mapping['moderator'], view_channel=True)
                
        except Exception as e:
            print(f"Permission error: {e}")
        
        # Set up default welcome message based on template
        welcome_message = welcome_system.get_default_welcome(template_name)
        data_manager.set_welcome_message(guild.id, welcome_message)
        
        # === STEP 6: Final Setup (100%) ===
        if progress_msg:
            try:
                await progress_msg.edit(content="🔄 **Finalizing setup...** (100%)")
            except:
                # Try to send a new message
                try:
                    progress_msg = await progress_channel.send("🔄 **Finalizing setup...** (100%)")
                except:
                    pass
        else:
            # Send update via DM
            try:
                await interaction.user.send("🔄 **Finalizing setup...** (100%)")
            except:
                pass
        
        # === COMPLETION MESSAGE ===
        completion_embed = discord.Embed(
            title=f"✅ {template['name']} Setup Complete!",
            description=f"Server has been completely transformed with the {template['name']} template.",
            color=0x00ff00,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        completion_embed.add_field(
            name="📊 Setup Summary",
            value=f"• All old channels deleted\n• {len(role_mapping)} roles configured\n• {len(category_mapping)} categories created\n• {channel_count} channels created",
            inline=False
        )
        
        completion_embed.add_field(
            name="🎯 Next Steps",
            value="1. Assign moderator roles to trusted members\n2. Customize channel topics\n3. Set up your welcome message\n4. Configure bot permissions",
            inline=False
        )
        
        completion_embed.add_field(
            name="🆕 New Features Added",
            value="• Auto-generated rules in 📜rules-config or existing rules channel\n• Staff-only channel 🔧staff-chat\n• Announcement system `/announce`\n• Welcome system `/welcome`",
            inline=False
        )
        
        completion_embed.set_footer(text=f"Template applied by {interaction.user}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        # Send completion message
        success_sent = False
        if progress_msg:
            try:
                await progress_msg.edit(content=None, embed=completion_embed)
                success_sent = True
            except:
                # Try to send a new message
                try:
                    await progress_channel.send(embed=completion_embed)
                    success_sent = True
                except:
                    pass
        
        # If we couldn't send to the progress channel, try DM
        if not success_sent:
            try:
                await interaction.user.send(embed=completion_embed)
                success_sent = True
            except:
                pass
                
        # Final fallback - try to send to any available channel
        if not success_sent:
            try:
                for chan in guild.text_channels:
                    if chan.permissions_for(guild.me).send_messages:
                        await chan.send(embed=completion_embed)
                        break
            except:
                pass
                
    except Exception as e:
        # Handle errors
        error_embed = discord.Embed(
            title="❌ Template Setup Failed",
            description=f"An error occurred during setup: {str(e)}",
            color=0xff0000
        )
        # Try to send error message to user via DM
        try:
            await interaction.user.send(embed=error_embed)
        except:
            # Try to send to any available channel
            try:
                for chan in guild.text_channels:
                    if chan.permissions_for(guild.me).send_messages:
                        await chan.send(embed=error_embed)
                        break
            except:
                pass

@bot.tree.command(name="help", description="Show help menu")
async def help_command(interaction: discord.Interaction):
    """Show help menu"""
    embed = discord.Embed(
        title="🤖 Template Bot Help",
        description="Advanced server template system with moderation & utilities",
        color=0x7289da
    )
    
    commands_list = [
        ("`/templates`", "View available templates with interactive menu"),
        ("`/apply <template>`", "🚨 APPLY TEMPLATE (deletes all existing channels)"),
        ("`/quote [message_link] [reply_text]`", "🎨 Create beautiful quotes from message links"),
        ("`/announce <message>`", "Make announcements in announcements channel"),
        ("`/welcome <message>`", "Set custom welcome message"),
        ("`/editrules <rules>`", "Edit server rules (Owner only)"),
        ("`!lock <#channel>`", "🔒 Lock a channel to prevent messages"),
        ("`!unlock <#channel>`", "🔓 Unlock a locked channel"),
        ("`/sync`", "Sync commands manually (if not showing)"),
        ("`/global_sync`", "Force global command sync (Owner only)"),
        ("`/help`", "Show this help menu")
    ]
    
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    # Add template info
    embed.add_field(
        name="📋 Available Templates",
        value="• 🎮 Gaming Community\n• 🎵 Music Community\n• 👥 Friends Hangout\n• ⚔️ Blox Fruits Crew\n• 🎬 YouTube Community",
        inline=False
    )
    
    # Add context menu info
    embed.add_field(
        name="🖱️ Context Menus",
        value="Right-click on any message → **Apps** → **Create Quote** (Easiest method!)",
        inline=False
    )
    
    embed.add_field(
        name="🔗 Message Link Method",
        value="Right-click on any message → **Copy Message Link** → Use `/quote <link>`",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ WARNING",
        value="Using `/apply` will **PERMANENTLY DELETE** all existing channels!",
        inline=False
    )
    
    embed.set_footer(text="Use with caution!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="sync", description="Manually sync commands if they're not showing up")
async def sync_commands(interaction: discord.Interaction):
    """Manually sync commands if they're not showing up"""
    # Check if user is server owner
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        return
    
    try:
        await interaction.response.send_message("🔄 Syncing commands... This may take a few seconds.", ephemeral=True)
        await bot.tree.sync(guild=interaction.guild)
        await interaction.edit_original_response(content="✅ Commands synced successfully!")
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ Failed to sync commands: {e}")

@bot.tree.command(name="global_sync", description="Force global command sync (Owner only)")
async def global_sync(interaction: discord.Interaction):
    """Force global command sync"""
    # Check if user is bot owner
    app_info = await bot.application_info()
    if interaction.user.id != app_info.owner.id:
        await interaction.response.send_message("❌ Only bot owner can use this command.", ephemeral=True)
        return
    
    try:
        await interaction.response.send_message("🔄 Syncing commands globally...", ephemeral=True)
        synced = await bot.tree.sync()
        await interaction.edit_original_response(content=f"✅ Global sync complete! {len(synced)} commands synced.")
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ Global sync failed: {e}")

# === ANNOUNCEMENT COMMAND ===

@bot.tree.command(name="announce", description="Make an announcement in the announcements channel")
@discord.app_commands.describe(message="Your announcement message")
async def announce(interaction: discord.Interaction, message: str):
    """Post announcement in announcements channel"""
    try:
        # Check if user is server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
            return
    
        # Find announcements channel - check ALL possible names used in templates
        announcements_channel = None
        possible_names = [
            "announcements", "📢announcements", "🎯announcements",
            "📢yt-announcements"
        ]
        
        for name in possible_names:
            announcements_channel = discord.utils.get(interaction.guild.channels, name=name)
            if announcements_channel:
                break
        
        # If still not found, create it with template-appropriate naming
        if not announcements_channel:
            try:
                # Determine template type based on existing channels/roles
                template_type = "general"  # default
                
                # Check for template-specific indicators
                if discord.utils.get(interaction.guild.channels, name="🎮gaming-news"):
                    template_type = "gaming"
                elif discord.utils.get(interaction.guild.channels, name="🎧song-requests"):
                    template_type = "music" 
                elif discord.utils.get(interaction.guild.channels, name="⚔️battle-strategy"):
                    template_type = "bloxfruits"
                elif discord.utils.get(interaction.guild.channels, name="📊milestone-tracker"):
                    template_type = "youtube"
                elif discord.utils.get(interaction.guild.roles, name="😊 Friend"):
                    template_type = "friends"
                
                # Choose appropriate channel name based on template
                channel_names = {
                    "gaming": "📢announcements",
                    "music": "📢announcements", 
                    "friends": "📢announcements",
                    "bloxfruits": "📢announcements",
                    "youtube": "📢yt-announcements",
                    "general": "📢announcements"
                }
                
                channel_name = channel_names.get(template_type, "📢announcements")
                
                # Find or create appropriate category
                category = None
                category_names = [
                    "🚀 WELCOME", "🎵 WELCOME", "👋 WELCOME", "🏴‍☠️ WELCOME ABOARD",
                    "🎬 WELCOME", "WELCOME"
                ]
                
                for cat_name in category_names:
                    category = discord.utils.get(interaction.guild.categories, name=cat_name)
                    if category:
                        break
                
                # If no category found, create one
                if not category:
                    category = await interaction.guild.create_category("📢 ANNOUNCEMENTS")
                
                # Create announcements channel
                announcements_channel = await interaction.guild.create_text_channel(
                    channel_name,
                    category=category,
                    topic="Important server announcements"
                )
                
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Could not create announcements channel: {str(e)}\n"
                    "Please ensure the bot has 'Manage Channels' permission.", 
                    ephemeral=True
                )
                return
        
        # Create announcement embed
        embed = discord.Embed(
            title="📢 Server Announcement",
            description=message,
            color=0xffd700,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_author(
            name=interaction.user.display_name, 
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        embed.set_footer(text=f"Announcement by {interaction.user.display_name}")
        
        try:
            # Try to send with @everyone ping first
            await announcements_channel.send("@everyone", embed=embed)
            await interaction.response.send_message("✅ Announcement posted with @everyone ping!", ephemeral=True)
        except discord.Forbidden:
            try:
                # If @everyone fails, try without ping
                await announcements_channel.send(embed=embed)
                await interaction.response.send_message("✅ Announcement posted! (No ping due to permissions)", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to post announcement: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to post announcement: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Error in announce command: {str(e)}")
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

# === WELCOME COMMAND ===

@bot.tree.command(name="welcome", description="Set custom welcome message for new members")
@discord.app_commands.describe(message="Your custom welcome message (use {member} for member mention)")
async def set_welcome(interaction: discord.Interaction, message: str):
    """Set custom welcome message"""
    # Check if user is server owner
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        return
    
    # Use data_manager instead of welcome_system.welcome_messages
    data_manager.set_welcome_message(interaction.guild.id, message)
    
    # Create a safe preview by formatting with actual values
    # Support multiple placeholder variations
    preview = message
    replacements = {
        '{member}': interaction.user.mention,
        '{user}': interaction.user.mention,
        '{mention}': interaction.user.mention,
        '{name}': interaction.user.name,
        '{username}': interaction.user.name,
        '{server}': interaction.guild.name,
        '{guild}': interaction.guild.name,
        '{count}': str(len(interaction.guild.members)),
        '{members}': str(len(interaction.guild.members)),
        '{membercount}': str(len(interaction.guild.members))
    }
    
    for placeholder, value in replacements.items():
        preview = preview.replace(placeholder, value)
    
    embed = discord.Embed(
        title="✅ Welcome Message Set!",
        description="**Preview:**\n" + preview,
        color=0x00ff00
    )
    embed.add_field(
        name="📝 Supported Placeholders",
        value=(
            "• `{member}`, `{user}`, `{mention}` - Member mention\n"
            "• `{name}`, `{username}` - Member name\n"
            "• `{server}`, `{guild}` - Server name\n"
            "• `{count}`, `{members}`, `{membercount}` - Member count"
        ),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === EDIT RULES COMMAND ===

@bot.tree.command(name="editrules", description="Edit server rules (Owner only)")
@discord.app_commands.describe(rules="New rules (one per line)")
async def edit_rules(interaction: discord.Interaction, rules: str):
    """Edit server rules - Owner only"""
    # Check if user is server owner
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        return
    
    # Find rules channel
    rules_channel = discord.utils.get(interaction.guild.channels, name="📜rules-config")
    if not rules_channel:
        await interaction.response.send_message("❌ Rules channel not found!", ephemeral=True)
        return
    
    # Parse rules
    rules_list = [rule.strip() for rule in rules.split('\n') if rule.strip()]
    
    # Create new rules embed
    embed = discord.Embed(
        title="🛡️ Server Rules (Edited)",
        description="These rules were customized by the server owner.",
        color=0xffa500
    )
    
    for i, rule in enumerate(rules_list, 1):
        embed.add_field(name=f"Rule #{i}", value=rule, inline=False)
    
    embed.add_field(
        name="📝 Last Updated",
        value=f"Edited by {interaction.user.mention} at <t:{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}:F>",
        inline=False
    )
    
    # Clear old rules and send new ones
    await rules_channel.purge(limit=10)
    await rules_channel.send(embed=embed)
    await interaction.response.send_message("✅ Rules updated successfully!", ephemeral=True)

# === LOCK CHANNEL COMMAND (PREFIX) ===

@bot.command(name="lock")
async def lock_channel(ctx, channel: discord.TextChannel = None):
    """Lock a channel - prevents @everyone from sending messages
    Usage: !lock <#channel> or !lock (for current channel)
    """
    # Check if user is server owner
    if ctx.author.id != ctx.guild.owner_id:
        return
    
    # Default to current channel if not specified
    target_channel = channel or ctx.channel
    
    # Lock the channel by denying send_messages for @everyone
    try:
        await target_channel.set_permissions(
            ctx.guild.default_role,
            send_messages=False,
            add_reactions=False,
            create_public_threads=False,
            create_private_threads=False
        )
        
        # Create lock embed
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{target_channel.mention} has been locked by {ctx.author.mention}.",
            color=0xff6b6b,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Locked by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        # Send lock notification in the channel
        await target_channel.send(embed=embed)
        
    except discord.Forbidden:
        pass
    except Exception as e:
        pass

# === UNLOCK CHANNEL COMMAND (PREFIX) ===

@bot.command(name="unlock")
async def unlock_channel(ctx, channel: discord.TextChannel = None):
    """Unlock a channel - allows @everyone to send messages again
    Usage: !unlock <#channel> or !unlock (for current channel)
    """
    # Check if user is server owner
    if ctx.author.id != ctx.guild.owner_id:
        return
    
    # Default to current channel if not specified
    target_channel = channel or ctx.channel
    
    # Unlock the channel by allowing send_messages for @everyone
    try:
        await target_channel.set_permissions(
            ctx.guild.default_role,
            send_messages=None,
            add_reactions=None,
            create_public_threads=None,
            create_private_threads=None
        )
        
        # Create unlock embed
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{target_channel.mention} has been unlocked by {ctx.author.mention}.",
            color=0x00ff00,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Unlocked by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        # Send unlock notification in the channel
        await target_channel.send(embed=embed)
        
    except discord.Forbidden:
        pass
    except Exception as e:
        pass

# === QUOTE SYSTEM ===

@bot.tree.command(name="quote", description="Create a beautiful quote from a message")
@discord.app_commands.describe(message_link="Link to the message you want to quote (right-click → Copy Message Link)")
@discord.app_commands.describe(reply_text="Your reply text")
async def quote_command(interaction: discord.Interaction, message_link: str = None, reply_text: str = None):
    """Create a stylish quote from any message using its link"""
    try:
        # If no message link provided, try to get from reference
        if not message_link:
            # For slash commands, we need to get the message link from the interaction context
            # This is a limitation of slash commands - they don't have direct access to replied messages
            await interaction.response.send_message(
                "❌ Please provide a message link.\n"
                "Right-click the message → **Copy Message Link** → Use that link with this command.\n"
                "Or use the context menu: Right-click message → **Apps** → **Create Quote**", 
                ephemeral=True
            )
            return
            
        # Parse the message link
        try:
            # Expected format: https://discord.com/channels/{guild_id}/{channel_id}/{message_id}
            parts = message_link.split('/')
            if len(parts) < 2:
                raise ValueError("Invalid link format")
                
            message_id = int(parts[-1])
            channel_id = int(parts[-2])
            
            # Get channel (might be same or different channel)
            if channel_id == interaction.channel_id:
                channel = interaction.channel
            else:
                channel = bot.get_channel(channel_id)
                if not channel:
                    channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            await interaction.response.send_message("❌ Invalid message link format! Please use the 'Copy Message Link' option.", ephemeral=True)
            return

        # Fetch the message
        try:
            referenced_message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found! Make sure the link is correct and I have access to that channel.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to read that message!", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"❌ Error fetching message: {str(e)}", ephemeral=True)
            return

        # Create the quote embed
        embed = discord.Embed(
            color=0x5865F2,
            timestamp=referenced_message.created_at
        )
        
        # Set author with original message info
        embed.set_author(
            name=f"{referenced_message.author.display_name} said:",
            icon_url=referenced_message.author.display_avatar.url
        )
        
        # Add the quoted message (truncate if too long)
        quoted_content = referenced_message.content
        if len(quoted_content) > 1000:
            quoted_content = quoted_content[:997] + "..."
        
        embed.add_field(
            name="",
            value=quoted_content,
            inline=False
        )
        
        # Add attachments info if present
        if referenced_message.attachments:
            attachment_text = f"📎 {len(referenced_message.attachments)} attachment(s)"
            if referenced_message.attachments[0].content_type and referenced_message.attachments[0].content_type.startswith('image/'):
                attachment_text += " 🖼️"
                # If it's an image, set it as the embed image
                if referenced_message.attachments[0].content_type.startswith('image/'):
                    embed.set_image(url=referenced_message.attachments[0].url)
            embed.add_field(name="Attachments", value=attachment_text, inline=True)
        
        # Add reactions info if present
        if referenced_message.reactions:
            reaction_text = " ".join([f"{reaction.emoji} {reaction.count}" for reaction in referenced_message.reactions[:5]])
            embed.add_field(name="Reactions", value=reaction_text, inline=True)
        
        # Add reply text if provided
        if reply_text:
            embed.add_field(
                name=f"💬 {interaction.user.display_name} replied:",
                value=reply_text,
                inline=False
            )
        
        # Add footer with context
        embed.set_footer(
            text=f"Quoted by {interaction.user.display_name} • #{referenced_message.channel.name}",
            icon_url=interaction.user.display_avatar.url
        )
        
        # Add jump link to original message
        embed.description = f"[Jump to original message]({referenced_message.jump_url})"
        
        # Send the quote
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error creating quote: {str(e)}", ephemeral=True)

# === CONTEXT MENU QUOTE (Right-click on message) ===

@bot.tree.context_menu(name="Create Quote")
async def quote_context_menu(interaction: discord.Interaction, message: discord.Message):
    """Right-click context menu to quote a message"""
    # Create the quote embed
    embed = discord.Embed(
        color=0x5865F2,
        timestamp=message.created_at
    )
    
    embed.set_author(
        name=f"{message.author.display_name} said:",
        icon_url=message.author.display_avatar.url
    )
    
    # Truncate message content if needed
    quoted_content = message.content
    if len(quoted_content) > 1000:
        quoted_content = quoted_content[:997] + "..."
    
    embed.add_field(name="", value=quoted_content, inline=False)
    
    # Add attachments info if present
    if message.attachments:
        attachment_text = f"📎 {len(message.attachments)} attachment(s)"
        if message.attachments[0].content_type and message.attachments[0].content_type.startswith('image/'):
            attachment_text += " 🖼️"
            # If it's an image, set it as the embed image
            if message.attachments[0].content_type.startswith('image/'):
                embed.set_image(url=message.attachments[0].url)
        embed.add_field(name="Attachments", value=attachment_text, inline=True)
    
    # Add reactions info if present
    if message.reactions:
        reaction_text = " ".join([f"{reaction.emoji} {reaction.count}" for reaction in message.reactions[:5]])
        embed.add_field(name="Reactions", value=reaction_text, inline=True)
    
    embed.set_footer(
        text=f"Quoted by {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url
    )
    
    embed.description = f"[Jump to original message]({message.jump_url})"
    
    await interaction.response.send_message(embed=embed)

# === REACTION ROLE EVENT HANDLERS ===

@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id in reaction_role_system.reaction_roles:
        guild = bot.get_guild(payload.guild_id)
        role_id = reaction_role_system.reaction_roles.get(str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role:
                member = guild.get_member(payload.user_id)
                if member and not member.bot: 
                    await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.message_id in reaction_role_system.reaction_roles:
        guild = bot.get_guild(payload.guild_id)
        role_id = reaction_role_system.reaction_roles.get(str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role:
                member = guild.get_member(payload.user_id)
                if member and not member.bot: 
                    await member.remove_roles(role)

# === TEMPORARY VOICE CHANNELS EVENT HANDLER ===

@bot.event
async def on_voice_state_update(member, before, after):
    if (after.channel and after.channel.id in temp_voice_system.creator_channels.values()):
        guild = member.guild
        category = after.channel.category
        temp_channel = await guild.create_voice_channel(name=f"🎤 {member.display_name}'s Room", category=category, user_limit=10)
        await member.move_to(temp_channel)
        temp_voice_system.temp_channels[temp_channel.id] = {'owner': member.id, 'created_at': datetime.datetime.now(datetime.timezone.utc)}
    if before.channel and before.channel.id in temp_voice_system.temp_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            del temp_voice_system.temp_channels[before.channel.id]

# === ERROR HANDLING ===

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need administrator permissions to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `/help` for available commands.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")

# === RUN THE BOT ===
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("ERROR: DISCORD_TOKEN not found in environment variables or .env file")
        exit(1)