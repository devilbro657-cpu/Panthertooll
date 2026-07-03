# API Configuration
API_BASE_URL = "https://games.accbazaar.shop"
API_KEY = "panthers_2ddLsqRHczTEdmQhMmhTf3aArxXQ8EaHYU0HZQ"  # Replace with your actual API key


COLORS = {
    'primary': '#2563eb',
    'primary_dark': '#1d4ed8',
    'secondary': '#059669',
    'background': '#f0f4f8',
    'card_bg': '#ffffff',
    'success': '#059669',
    'error': '#dc2626',
    'pending': '#d97706',
    'text_primary': '#1a202c',
    'text_secondary': '#64748b',
    'border': '#e2e8f0',
    'input_bg': '#f1f5f9',
}

AVAILABLE_APPS = [
    "567slot_game", "Yono_vip", "mbmbet_game", "yonoslot_game",
    "789jackpot_game", "okrummy_game", "Yono777_game", "toprummy_game",
    "Yonogame_game", "spincrush_game", "hirummy_game", "indslot_game",
    "maha_game", "Spin777_game", "Hindi777_game", "Bingo_game",
    "jaiho777_game", "jaiho91_game", "Rummyludo_game", "Shareslots_game",
    "SpinLucky_game"
]

APP_PRICES = {app: 3.0 for app in AVAILABLE_APPS}

FLASK_SECRET_KEY = "panther_secret_key_2024"
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5001
FLASK_DEBUG = True

OTP_SEND_DELAY = 2  # 2 seconds gap between OTPs