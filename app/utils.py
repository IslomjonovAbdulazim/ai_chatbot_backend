import openai
from sqlalchemy.orm import Session
from datetime import date
from app.config import OPENAI_API_KEY
from app.models import Usage

openai.api_key = OPENAI_API_KEY


def count_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)"""
    return len(text) // 4


async def chat_with_ai(messages: list) -> tuple[str, int, int]:
    """Send messages to OpenAI and return response with token counts"""
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=messages
        )

        content = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        return content, input_tokens, output_tokens
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


def track_usage(db: Session, user_id: str, input_tokens: int, output_tokens: int):
    """Track daily token usage for user"""
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


def generate_chat_title(content: str) -> str:
    """Generate a simple chat title from first message"""
    words = content.split()[:4]
    return " ".join(words) + ("..." if len(content.split()) > 4 else "")