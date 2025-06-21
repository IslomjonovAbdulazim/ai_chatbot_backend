from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
from app.database import get_db
from app.models import User, Chat, Message, Usage
from app.auth import verify_google_token, create_access_token, get_current_user
from app.utils import chat_with_ai, track_usage, generate_chat_title

router = APIRouter()


# Schemas
class GoogleAuth(BaseModel):
    token: str


class Token(BaseModel):
    access_token: str
    token_type: str


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    avatar: Optional[str]


class UsageStats(BaseModel):
    total_tokens: int
    total_messages: int
    today_tokens: int
    today_messages: int


# Auth Routes
@router.post("/auth/google", response_model=Token)
async def google_login(auth: GoogleAuth, db: Session = Depends(get_db)):
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

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


# Chat Routes
@router.get("/chats", response_model=List[ChatResponse])
async def get_chats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chats = db.query(Chat).filter(Chat.user_id == current_user.id).order_by(Chat.updated_at.desc()).all()
    return chats


@router.post("/chats", response_model=ChatResponse)
async def create_chat(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = Chat(user_id=current_user.id, title="New Chat")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.delete(chat)
    db.commit()
    return {"message": "Chat deleted"}


# Message Routes
@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()
    return messages


@router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(chat_id: str, message: MessageCreate, current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Save user message
    user_message = Message(
        chat_id=chat_id,
        role="user",
        content=message.content
    )
    db.add(user_message)

    # Get chat history
    messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()
    openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]
    openai_messages.append({"role": "user", "content": message.content})

    # Get AI response
    try:
        ai_response, input_tokens, output_tokens = await chat_with_ai(openai_messages)

        # Save AI message
        ai_message = Message(
            chat_id=chat_id,
            role="assistant",
            content=ai_response,
            tokens=output_tokens
        )
        db.add(ai_message)

        # Update chat title if first message
        if chat.message_count == 0:
            chat.title = generate_chat_title(message.content)

        chat.message_count += 2
        chat.updated_at = datetime.utcnow()

        # Track usage
        track_usage(db, str(current_user.id), input_tokens, output_tokens)

        db.commit()
        db.refresh(ai_message)
        return ai_message

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# User Routes
@router.get("/user/profile", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/user/usage", response_model=UsageStats)
async def get_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total = db.query(Usage).filter(Usage.user_id == current_user.id).all()
    today = db.query(Usage).filter(Usage.user_id == current_user.id, Usage.date == date.today()).first()

    return {
        "total_tokens": sum(u.total_tokens for u in total),
        "total_messages": sum(u.message_count for u in total),
        "today_tokens": today.total_tokens if today else 0,
        "today_messages": today.message_count if today else 0
    }


@router.get("/user/usage/chart")
async def get_usage_chart(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    usage = db.query(Usage).filter(Usage.user_id == current_user.id).order_by(Usage.date).all()
    return [{"date": str(u.date), "tokens": u.total_tokens, "messages": u.message_count} for u in usage]