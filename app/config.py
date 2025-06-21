import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chatplatform.db")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30