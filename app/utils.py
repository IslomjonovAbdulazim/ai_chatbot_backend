import httpx
import json
import os
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from datetime import date
from app.config import OPENAI_API_KEY
from app.models import Usage


class MultiProviderAIService:
    def __init__(self):
        # Primary OpenAI Configuration
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

        # Alternative providers for geographic restrictions
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")  # OpenRouter (global access)
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")  # Claude API
        self.groq_key = os.getenv("GROQ_API_KEY")  # Groq (fast inference)
        self.together_key = os.getenv("TOGETHER_API_KEY")  # Together AI

        # Model configuration
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))

        # VPN/Proxy settings
        self.use_proxy = os.getenv("USE_PROXY", "false").lower() == "true"
        self.proxy_url = os.getenv("PROXY_URL")  # e.g., "http://proxy:8080"

        print(f"🤖 Multi-Provider AI Service initialized")
        print(f"🌍 Available providers:")
        print(f"   OpenAI: {'✅' if self.openai_api_key else '❌'}")
        print(f"   OpenRouter: {'✅' if self.openrouter_key else '❌'}")
        print(f"   Anthropic: {'✅' if self.anthropic_key else '❌'}")
        print(f"   Groq: {'✅' if self.groq_key else '❌'}")
        print(f"   Together: {'✅' if self.together_key else '❌'}")
        print(f"   Proxy: {'✅' if self.use_proxy and self.proxy_url else '❌'}")

    async def chat_with_openai_direct(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """Try OpenAI directly (might fail in restricted regions)"""
        if not self.openai_api_key:
            raise Exception("OpenAI API key not configured")

        proxy_config = None
        if self.use_proxy and self.proxy_url:
            proxy_config = self.proxy_url
            print(f"🌐 Using proxy: {self.proxy_url}")

        async with httpx.AsyncClient(proxies=proxy_config) as client:
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

    async def chat_with_openrouter(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """Use OpenRouter as alternative (supports global access)"""
        if not self.openrouter_key:
            raise Exception("OpenRouter API key not configured")

        # Map model names for OpenRouter
        openrouter_model = "openai/gpt-4o-mini" if self.model == "gpt-4o-mini" else "openai/gpt-3.5-turbo"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "HTTP-Referer": "http://localhost:8000",  # Required by OpenRouter
                    "X-Title": "AI Chatbot",
                    "Content-Type": "application/json"
                },
                json={
                    "model": openrouter_model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"OpenRouter API error: {response.status_code} - {error_text}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

            return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    async def chat_with_groq(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """Use Groq for fast inference (global access)"""
        if not self.groq_key:
            raise Exception("Groq API key not configured")

        # Groq models
        groq_model = "llama3-8b-8192"  # Fast and efficient

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": groq_model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"Groq API error: {response.status_code} - {error_text}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

            return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    async def chat_with_together(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """Use Together AI (global access)"""
        if not self.together_key:
            raise Exception("Together API key not configured")

        together_model = "meta-llama/Llama-2-7b-chat-hf"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.together_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": together_model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"Together API error: {response.status_code} - {error_text}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

            return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    async def chat_completion(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """
        Try multiple providers in order of preference
        """
        providers = []

        # Add available providers in order of preference
        if self.openrouter_key:
            providers.append(("OpenRouter", self.chat_with_openrouter))

        if self.groq_key:
            providers.append(("Groq", self.chat_with_groq))

        if self.together_key:
            providers.append(("Together AI", self.chat_with_together))

        if self.openai_api_key and (self.use_proxy or os.getenv("FORCE_OPENAI") == "true"):
            providers.append(("OpenAI", self.chat_with_openai_direct))

        if not providers:
            raise Exception("No AI providers configured. Please set up at least one API key.")

        # Try each provider
        for provider_name, provider_func in providers:
            try:
                print(f"🤖 Trying {provider_name}...")
                content, input_tokens, output_tokens = await provider_func(messages)
                print(f"✅ {provider_name} successful!")
                return content, input_tokens, output_tokens

            except Exception as e:
                print(f"❌ {provider_name} failed: {e}")
                continue

        # If all providers fail
        raise Exception("All AI providers failed. Please check your API keys and internet connection.")


# Initialize the service
try:
    ai_service = MultiProviderAIService()
    print("✅ Multi-Provider AI Service initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize AI Service: {e}")
    ai_service = None


async def chat_with_ai(messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
    """
    Enhanced chat function with multiple provider support
    """
    if not ai_service:
        return "AI service is not properly configured. Please check your API keys.", 0, 0

    try:
        return await ai_service.chat_completion(messages)

    except Exception as e:
        print(f"🆘 All providers failed: {e}")

        # Geographic restriction specific message
        if "not supported" in str(e) or "403" in str(e):
            return """🌍 **Geographic Restriction Detected**

OpenAI API is not available in your region. To use this chatbot, you have several options:

1. **Use Alternative AI Providers** (Recommended):
   - Set up OpenRouter API key (global access): https://openrouter.ai
   - Set up Groq API key (free, fast): https://console.groq.com
   - Set up Together AI: https://api.together.xyz

2. **Use VPN/Proxy**:
   - Set USE_PROXY=true in your .env file
   - Add PROXY_URL=http://your-proxy:port

3. **Alternative Solutions**:
   - Use Anthropic Claude API
   - Use local AI models with Ollama

Please check the updated README for setup instructions.""", 0, 0

        return f"❌ AI Error: {str(e)}", 0, 0


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