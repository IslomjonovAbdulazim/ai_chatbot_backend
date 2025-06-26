import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chatplatform.db")

# Authentication Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OpenAI Configuration - Enhanced with latest parameters
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Latest model
OPENAI_TEMPERATURE = os.getenv("OPENAI_TEMPERATURE", "0.7")  # Creativity level
OPENAI_MAX_TOKENS = os.getenv("OPENAI_MAX_TOKENS", "2048")  # Response length
OPENAI_TIMEOUT = os.getenv("OPENAI_TIMEOUT", "60")  # Request timeout
OPENAI_TOP_P = os.getenv("OPENAI_TOP_P", "0.9")  # Nucleus sampling
OPENAI_FREQUENCY_PENALTY = os.getenv("OPENAI_FREQUENCY_PENALTY", "0.1")  # Reduce repetition
OPENAI_PRESENCE_PENALTY = os.getenv("OPENAI_PRESENCE_PENALTY", "0.1")  # Encourage new topics

# API Configuration
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))  # Requests per minute
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "10000"))  # Characters
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))  # Messages

# Feature Flags
ENABLE_USAGE_TRACKING = os.getenv("ENABLE_USAGE_TRACKING", "true").lower() == "true"
ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
ENABLE_DEBUG_LOGGING = os.getenv("ENABLE_DEBUG_LOGGING", "false").lower() == "true"

# Model Configuration Presets
MODEL_PRESETS = {
    "creative": {
        "temperature": 0.9,
        "top_p": 0.95,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.3
    },
    "balanced": {
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.1,
        "presence_penalty": 0.1
    },
    "precise": {
        "temperature": 0.3,
        "top_p": 0.8,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0
    }
}

# Default preset
DEFAULT_MODEL_PRESET = os.getenv("DEFAULT_MODEL_PRESET", "balanced")


# Validation
def validate_config():
    """Validate required configuration values"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    if not SECRET_KEY or SECRET_KEY == "your-secret-key-change-this":
        print("⚠️  WARNING: Using default SECRET_KEY. Please set a secure secret key!")

    if not GOOGLE_CLIENT_ID:
        print("⚠️  WARNING: GOOGLE_CLIENT_ID not set. Google authentication will not work.")

    print("✅ Configuration validated successfully")


# Auto-validate on import
if __name__ != "__main__":
    try:
        validate_config()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        raise