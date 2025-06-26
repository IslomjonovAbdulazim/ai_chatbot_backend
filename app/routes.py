from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import time
from app.database import get_db
from app.models import User, Chat, Message, Usage
from app.auth import verify_google_token, create_access_token, get_current_user
from app.utils import chat_with_ai, track_usage, generate_chat_title, ai_service
from app.config import MAX_MESSAGE_LENGTH, MAX_CONVERSATION_HISTORY, ENABLE_RATE_LIMITING

router = APIRouter()

# Rate limiting storage (in production, use Redis)
user_request_times = {}


def check_rate_limit(user_id: str) -> bool:
    """Simple rate limiting: max 30 requests per minute"""
    if not ENABLE_RATE_LIMITING:
        return True

    current_time = time.time()
    if user_id not in user_request_times:
        user_request_times[user_id] = []

    # Remove requests older than 1 minute
    user_request_times[user_id] = [
        req_time for req_time in user_request_times[user_id]
        if current_time - req_time < 60
    ]

    # Check if under limit
    if len(user_request_times[user_id]) >= 30:
        return False

    user_request_times[user_id].append(current_time)
    return True


# Enhanced Schemas
class GoogleAuth(BaseModel):
    token: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('Message content cannot be empty')
        return v.strip()


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tokens: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int

    class Config:
        from_attributes = True


class ChatCreateRequest(BaseModel):
    title: Optional[str] = None
    initial_message: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    avatar: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UsageStats(BaseModel):
    total_tokens: int
    total_messages: int
    today_tokens: int
    today_messages: int
    this_week_tokens: int
    this_month_tokens: int


class AIModelSettings(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=4000)
    model: Optional[str] = None


# Auth Routes
@router.post("/auth/google", response_model=Token)
async def google_login(auth: GoogleAuth, db: Session = Depends(get_db)):
    """Enhanced Google authentication with user profile"""
    try:
        google_user = verify_google_token(auth.token)

        user = db.query(User).filter(User.google_id == google_user["sub"]).first()

        if not user:
            user = User(
                google_id=google_user["sub"],
                email=google_user["email"],
                name=google_user["name"],
                avatar=google_user.get("picture")
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"👤 New user registered: {user.email}")
        else:
            # Update user info in case it changed
            user.name = google_user["name"]
            user.avatar = google_user.get("picture")
            user.updated_at = datetime.utcnow()
            db.commit()

        access_token = create_access_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "avatar": user.avatar
            }
        }

    except Exception as e:
        print(f"❌ Authentication error: {e}")
        raise HTTPException(status_code=400, detail="Authentication failed")


@router.get("/auth/verify", response_model=UserProfile)
async def verify_token(current_user: User = Depends(get_current_user)):
    """Verify token and return user profile"""
    return current_user


# Chat Routes
@router.get("/chats", response_model=List[ChatResponse])
async def get_chats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        limit: int = 50
):
    """Get user's chat history with pagination"""
    if not check_rate_limit(current_user.id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    chats = (db.query(Chat)
             .filter(Chat.user_id == current_user.id)
             .order_by(Chat.updated_at.desc())
             .limit(limit)
             .all())

    return chats


@router.post("/chats", response_model=ChatResponse)
async def create_chat(
        chat_request: ChatCreateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Create a new chat with optional initial message"""
    if not check_rate_limit(current_user.id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    title = chat_request.title or "New Chat"

    # If initial message provided, generate smart title
    if chat_request.initial_message:
        title = generate_chat_title(chat_request.initial_message)

    chat = Chat(user_id=current_user.id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)

    print(f"💬 New chat created: {chat.id} - {title}")
    return chat


@router.delete("/chats/{chat_id}")
async def delete_chat(
        chat_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Delete a chat and all its messages"""
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    message_count = len(chat.messages)
    db.delete(chat)
    db.commit()

    print(f"🗑️ Chat deleted: {chat_id} ({message_count} messages)")
    return {"message": "Chat deleted successfully", "deleted_messages": message_count}


# Message Routes
@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(
        chat_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get chat messages with conversation history"""
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = (db.query(Message)
                .filter(Message.chat_id == chat_id)
                .order_by(Message.created_at)
                .all())

    return messages


@router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
        chat_id: str,
        message: MessageCreate,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Send a message and get AI response"""
    if not check_rate_limit(current_user.id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment.")

    # Verify chat ownership
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    try:
        # Save user message
        user_message = Message(
            chat_id=chat_id,
            role="user",
            content=message.content,
            tokens=0
        )
        db.add(user_message)

        # Get conversation history (limit to recent messages for context)
        recent_messages = (db.query(Message)
                           .filter(Message.chat_id == chat_id)
                           .order_by(Message.created_at.desc())
                           .limit(MAX_CONVERSATION_HISTORY)
                           .all())

        # Reverse to get chronological order
        recent_messages.reverse()

        # Format messages for OpenAI
        openai_messages = []
        for msg in recent_messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        # Add the new user message
        openai_messages.append({"role": "user", "content": message.content})

        print(f"🤖 Processing message for chat {chat_id}: {len(openai_messages)} messages in context")

        # Get AI response
        ai_response, input_tokens, output_tokens = await chat_with_ai(openai_messages)

        # Save AI message
        ai_message = Message(
            chat_id=chat_id,
            role="assistant",
            content=ai_response,
            tokens=output_tokens
        )
        db.add(ai_message)

        # Update chat metadata
        if chat.message_count == 0:
            # Update title based on first message
            chat.title = generate_chat_title(message.content)

        chat.message_count += 2
        chat.updated_at = datetime.utcnow()

        # Commit all changes
        db.commit()
        db.refresh(ai_message)

        # Track usage in background
        background_tasks.add_task(track_usage, db, str(current_user.id), input_tokens, output_tokens)

        print(f"✅ Message processed successfully: {input_tokens + output_tokens} tokens used")
        return ai_message

    except Exception as e:
        db.rollback()
        print(f"❌ Message processing error: {e}")

        # Provide helpful error messages
        if "rate limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="AI service is currently busy. Please try again in a moment.")
        elif "timeout" in str(e).lower():
            raise HTTPException(status_code=408, detail="Request timed out. Please try again.")
        else:
            raise HTTPException(status_code=500,
                                detail="Sorry, I'm having trouble processing your message. Please try again.")


# User Routes
@router.get("/user/profile", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user


@router.get("/user/usage", response_model=UsageStats)
async def get_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get comprehensive usage statistics"""
    from datetime import timedelta

    # Get all usage records
    all_usage = db.query(Usage).filter(Usage.user_id == current_user.id).all()

    # Calculate totals
    total_tokens = sum(u.total_tokens for u in all_usage)
    total_messages = sum(u.message_count for u in all_usage)

    # Today's usage
    today = date.today()
    today_usage = db.query(Usage).filter(
        Usage.user_id == current_user.id,
        Usage.date == today
    ).first()

    # This week's usage
    week_start = today - timedelta(days=today.weekday())
    week_usage = db.query(Usage).filter(
        Usage.user_id == current_user.id,
        Usage.date >= week_start
    ).all()

    # This month's usage
    month_start = today.replace(day=1)
    month_usage = db.query(Usage).filter(
        Usage.user_id == current_user.id,
        Usage.date >= month_start
    ).all()

    return {
        "total_tokens": total_tokens,
        "total_messages": total_messages,
        "today_tokens": today_usage.total_tokens if today_usage else 0,
        "today_messages": today_usage.message_count if today_usage else 0,
        "this_week_tokens": sum(u.total_tokens for u in week_usage),
        "this_month_tokens": sum(u.total_tokens for u in month_usage)
    }


@router.get("/user/usage/chart")
async def get_usage_chart(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get usage data for charting"""
    usage = (db.query(Usage)
             .filter(Usage.user_id == current_user.id)
             .order_by(Usage.date.desc())
             .limit(30)  # Last 30 days
             .all())

    return [
        {
            "date": str(u.date),
            "tokens": u.total_tokens,
            "messages": u.message_count,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens
        }
        for u in reversed(usage)
    ]


# AI Model Management
@router.get("/ai/models")
async def get_available_models():
    """Get available AI models and presets"""
    from app.config import MODEL_PRESETS

    return {
        "current_model": ai_service.model,
        "available_presets": MODEL_PRESETS,
        "current_settings": {
            "temperature": ai_service.temperature,
            "max_tokens": ai_service.max_tokens,
            "top_p": ai_service.top_p
        }
    }


# Health Check
@router.get("/health")
async def health_check():
    """API health check with service status"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "ai_service": "operational",
        "database": "connected"
    }