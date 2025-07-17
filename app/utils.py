import httpx
import os
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from datetime import date
from app.models import Usage


class AIService:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_api_url = "https://api.openai.com/v1/chat/completions"
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))

        if not self.openai_api_key:
            raise Exception("OPENAI_API_KEY not found in environment variables")

        print(f"🤖 OpenAI Service initialized with model: {self.model}")

    async def chat_completion(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """Send messages to OpenAI and get response"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.openai_api_url,
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"OpenAI API error: {response.status_code} - {error_text}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

            return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


# Initialize the service
try:
    ai_service = AIService()
    print("✅ OpenAI Service initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize OpenAI Service: {e}")
    ai_service = None


async def chat_with_ai(messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
    """Chat with OpenAI"""
    if not ai_service:
        return "AI service is not properly configured. Please check your OPENAI_API_KEY.", 0, 0

    try:
        return await ai_service.chat_completion(messages)
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")
        return f"❌ AI Error: {str(e)}", 0, 0


def track_usage(db: Session, user_id: str, input_tokens: int, output_tokens: int):
    """Track usage in database"""
    try:
        today = date.today()

        usage = db.query(Usage).filter(
            Usage.user_id == user_id,
            Usage.date == today
        ).first()

        if usage:
            usage.input_tokens += input_tokens
            usage.output_tokens += output_tokens
            usage.total_tokens += (input_tokens + output_tokens)
            usage.message_count += 1
        else:
            usage = Usage(
                user_id=user_id,
                date=today,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                message_count=1
            )
            db.add(usage)

        db.commit()
        print(f"📊 Usage tracked: User {user_id[:8]}... used {input_tokens + output_tokens} tokens")

    except Exception as e:
        print(f"⚠️ Usage tracking error: {e}")
        db.rollback()


def generate_chat_title(content: str) -> str:
    """Generate smart chat title"""
    content = content.strip()
    prefixes_to_remove = ["hi", "hello", "hey", "can you", "could you", "please", "i need", "help me"]

    words = content.lower().split()
    for prefix in prefixes_to_remove:
        prefix_words = prefix.split()
        if words[:len(prefix_words)] == prefix_words:
            words = words[len(prefix_words):]
            break

    meaningful_words = [word for word in words if len(word) > 2][:6]

    if not meaningful_words:
        meaningful_words = content.split()[:4]

    title = " ".join(meaningful_words)

    if title:
        title = title[0].upper() + title[1:]

    return title[:50] + ("..." if len(title) > 50 else "") or "New Chat"


def count_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)"""
    return len(text) // 4