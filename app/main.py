from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from contextlib import asynccontextmanager
from app.routes import router
from app.database import create_tables
from app.config import validate_config, ENABLE_DEBUG_LOGGING

# Configure logging
if ENABLE_DEBUG_LOGGING:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("chatbot")
else:
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("chatbot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifespan management"""
    # Startup
    logger.info("🚀 Starting AI Chatbot Backend...")

    try:
        # Validate configuration
        validate_config()

        # Create database tables
        create_tables()
        logger.info("📄 Database tables created/verified")

        # Test AI service connection
        from app.utils import ai_service
        logger.info(f"🤖 AI Service initialized with model: {ai_service.model}")

        logger.info("✅ Application startup completed successfully")

    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down AI Chatbot Backend...")


# Create FastAPI app with enhanced configuration
app = FastAPI(
    title="Modern AI Chatbot API",
    description="Advanced chatbot backend with OpenAI integration, Google Auth, and modern features",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Security Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# CORS Middleware with enhanced configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"]
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time to response headers"""
    start_time = time.time()

    # Log request
    if ENABLE_DEBUG_LOGGING:
        logger.info(f"📥 {request.method} {request.url}")

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 3))

    # Log response
    if ENABLE_DEBUG_LOGGING:
        logger.info(f"📤 {response.status_code} - {process_time:.3f}s")

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors gracefully"""
    logger.error(f"🚨 Unhandled error: {exc} on {request.url}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "error_type": type(exc).__name__,
            "timestamp": time.time()
        }
    )


# Custom HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Enhanced HTTP error responses"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


# Include routers
app.include_router(router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """API welcome message with status"""
    return {
        "message": "🤖 Modern AI Chatbot API",
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "OpenAI GPT-4o-mini integration",
            "Google OAuth authentication",
            "Real-time chat with AI",
            "Conversation history",
            "Usage analytics",
            "Rate limiting",
            "Modern async architecture"
        ],
        "docs": "/docs",
        "health": "/api/health"
    }


# API Info endpoint
@app.get("/info")
async def api_info():
    """Detailed API information"""
    return {
        "name": "Modern AI Chatbot API",
        "version": "2.0.0",
        "description": "Advanced chatbot backend with latest OpenAI integration",
        "endpoints": {
            "authentication": "/api/auth/*",
            "chats": "/api/chats/*",
            "messages": "/api/chats/{chat_id}/messages",
            "user": "/api/user/*",
            "ai": "/api/ai/*",
            "health": "/api/health"
        },
        "features": {
            "ai_model": "gpt-4o-mini",
            "authentication": "Google OAuth 2.0",
            "rate_limiting": True,
            "usage_tracking": True,
            "conversation_history": True
        }
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("🎯 Starting development server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info" if ENABLE_DEBUG_LOGGING else "warning"
    )