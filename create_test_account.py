#!/usr/bin/env python3
"""
Create Test Account and Generate 30-Day Token
Run this script to create a test user and generate a long-lasting token
"""

import sys
import os
from jose import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, create_tables
from app.models import User
from app.config import SECRET_KEY, ALGORITHM


def create_test_account_and_token():
    """Create a test user account and generate a 30-day token"""

    # Ensure tables exist
    create_tables()

    # Create database session
    db = SessionLocal()

    try:
        # Test user data
        test_user_id = "test-user-123"
        test_email = "testuser@chatbot.dev"
        test_name = "Test Student"

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == test_email).first()
        if existing_user:
            print(f"User already exists with ID: {existing_user.id}")
            user_id = existing_user.id
        else:
            # Create new test user
            test_user = User(
                id=test_user_id,
                google_id="test-google-id-123",
                email=test_email,
                name=test_name,
                avatar="https://via.placeholder.com/100"
            )

            db.add(test_user)
            db.commit()
            db.refresh(test_user)

            print(f"✅ Created test user: {test_user.name}")
            user_id = test_user.id

        # Generate 30-day token
        token_data = {
            "sub": str(user_id),
            "exp": datetime.utcnow() + timedelta(days=30),
            "iat": datetime.utcnow()
        }

        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        print("\n" + "=" * 70)
        print("🎉 TEST ACCOUNT & TOKEN GENERATED")
        print("=" * 70)
        print(f"User ID:     {user_id}")
        print(f"Email:       {test_email}")
        print(f"Name:        {test_name}")
        print(f"Token:       {token}")
        print(f"Expires:     {datetime.utcnow() + timedelta(days=30)}")
        print("=" * 70)
        print("\n📝 Usage Instructions:")
        print("1. Use this token in your API requests:")
        print(f'   Authorization: Bearer {token}')
        print("\n2. Test the token with curl:")
        print(f'   curl -H "Authorization: Bearer {token}" http://localhost:8000/auth/verify')
        print("\n3. Or in your frontend:")
        print(f'   localStorage.setItem("token", "{token}");')
        print("\n⚠️  WARNING: This is for development/testing only!")
        print("   Do NOT use in production!")

        return token, user_id

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return None, None
    finally:
        db.close()


if __name__ == "__main__":
    create_test_account_and_token()