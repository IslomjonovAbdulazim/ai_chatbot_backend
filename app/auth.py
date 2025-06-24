from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, GOOGLE_CLIENT_ID
from app.database import get_db
from app.models import User

security = HTTPBearer()

# Special test token for students
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZXhwIjoxNzUzMzU5NDM3LCJpYXQiOjE3NTA3Njc0Mzd9.JoFPZ1qT9jbG-Vj2rQ8eb-AFXvtt0pHVj-4bie1505c"


def create_test_user():
    """Create a mock user object for testing"""

    class MockUser:
        def __init__(self):
            self.id = "test-user-123"
            self.google_id = "test-google-123"
            self.email = "student@test.com"
            self.name = "Test Student"
            self.avatar = "https://via.placeholder.com/100"
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    return MockUser()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_google_token(token: str):
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        return idinfo
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Google token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials

    # Check if it's the special test token
    if token == TEST_TOKEN:
        print("🎯 Using test token - bypassing validation")

        # Try to get user from database, if not found create mock user
        try:
            user = db.query(User).filter(User.id == "test-user-123").first()
            if user:
                return user
            else:
                # Create the test user in database if it doesn't exist
                test_user = User(
                    id="test-user-123",
                    google_id="test-google-123",
                    email="student@test.com",
                    name="Test Student",
                    avatar="https://via.placeholder.com/100"
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
                print("✅ Created test user in database")
                return test_user
        except Exception as e:
            print(f"Database error, using mock user: {e}")
            # If database fails, return mock user
            return create_test_user()

    # Normal token validation for other tokens
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user