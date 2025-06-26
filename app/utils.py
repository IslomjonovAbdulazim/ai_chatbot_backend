import httpx
import json
import os
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from datetime import date
from app.config import OPENAI_API_KEY
from app.models import Usage


class ModernAIService:
    def __init__(self):
        # OpenAI Configuration with latest parameters
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        self.top_p = float(os.getenv("OPENAI_TOP_P", "0.9"))
        self.frequency_penalty = float(os.getenv("OPENAI_FREQUENCY_PENALTY", "0.1"))
        self.presence_penalty = float(os.getenv("OPENAI_PRESENCE_PENALTY", "0.1"))

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        print(f"🤖 Modern AI Service initialized with OpenAI {self.model}")
        print(f"📊 Parameters: temp={self.temperature}, max_tokens={self.max_tokens}, top_p={self.top_p}")

    async def chat_completion(
            self,
            messages: List[Dict[str, str]],
            system_prompt: Optional[str] = None,
            response_format: Optional[str] = None
    ) -> Tuple[str, int, int]:
        """
        Advanced chat completion with modern OpenAI API features
        """

        # Prepare messages with system prompt if provided
        formatted_messages = []

        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt
            })

        # Add conversation messages
        formatted_messages.extend(messages)

        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": False
        }

        # Add response format if specified
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient() as client:
                print(f"🚀 Sending request to OpenAI API...")

                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code != 200:
                    error_detail = await self._extract_error_detail(response)
                    raise Exception(f"OpenAI API error: {response.status_code} - {error_detail}")

                result = response.json()

                # Extract response data
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

                print(
                    f"✅ OpenAI response completed, tokens used: {total_tokens} (in: {input_tokens}, out: {output_tokens})")

                return content, input_tokens, output_tokens

        except httpx.TimeoutException:
            print("⏱️ OpenAI API request timed out")
            raise Exception("OpenAI API request timed out. Please try again.")
        except httpx.RequestError as e:
            print(f"🌐 Network error: {e}")
            raise Exception("Network error occurred. Please check your connection and try again.")
        except Exception as e:
            print(f"❌ AI chat error: {str(e)}")
            raise Exception(f"AI service error: {str(e)}")

    async def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extract detailed error information from API response"""
        try:
            error_data = response.json()
            return error_data.get("error", {}).get("message", response.text)
        except:
            return response.text

    def _get_conversation_system_prompt(self) -> str:
        """Get enhanced system prompt for general conversation"""
        return """You are Claude, a helpful, harmless, and honest AI assistant created by Anthropic. 

Key characteristics:
- Be conversational, engaging, and genuinely helpful
- Provide accurate, well-researched information
- Admit when you're unsure about something
- Be creative and thoughtful in your responses
- Maintain context throughout our conversation
- Ask clarifying questions when needed
- Provide examples and explanations when helpful
- Be concise but thorough

Always strive to be genuinely useful while maintaining a friendly, professional tone."""

    def generate_smart_title(self, content: str) -> str:
        """Generate an intelligent chat title from the first message"""
        # Remove common prefixes
        content = content.strip()
        prefixes_to_remove = ["hi", "hello", "hey", "can you", "could you", "please", "i need", "help me"]

        words = content.lower().split()
        for prefix in prefixes_to_remove:
            prefix_words = prefix.split()
            if words[:len(prefix_words)] == prefix_words:
                words = words[len(prefix_words):]
                break

        # Take meaningful words, limit to 6 words max
        meaningful_words = [word for word in words if len(word) > 2][:6]

        if not meaningful_words:
            # Fallback to first few words if no meaningful words found
            meaningful_words = content.split()[:4]

        title = " ".join(meaningful_words)

        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]

        return title[:50] + ("..." if len(title) > 50 else "") or "New Chat"


# Initialize the modern AI service
ai_service = ModernAIService()


async def chat_with_ai(messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
    """
    Modern chat function using the enhanced AI service
    """
    system_prompt = ai_service._get_conversation_system_prompt()

    try:
        return await ai_service.chat_completion(
            messages=messages,
            system_prompt=system_prompt
        )
    except Exception as e:
        # Provide a helpful fallback response
        print(f"🆘 Chat service fallback activated: {str(e)}")
        fallback_response = "I apologize, but I'm experiencing technical difficulties right now. Please try again in a moment. If the problem persists, the service may be temporarily unavailable."
        return fallback_response, 0, 0


def track_usage(db: Session, user_id: str, input_tokens: int, output_tokens: int):
    """Enhanced usage tracking with better error handling"""
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
        print(f"📊 Usage tracked: User {user_id[:8]}... used {input_tokens + output_tokens} tokens today")

    except Exception as e:
        print(f"⚠️ Usage tracking error: {e}")
        # Don't let usage tracking failures break the chat
        db.rollback()


def generate_chat_title(content: str) -> str:
    """Generate smart chat title using the AI service"""
    return ai_service.generate_smart_title(content)


# Legacy function for backward compatibility
def count_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)"""
    return len(text) // 4