from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio
from typing import Dict, Any

from src.core.config import settings
from src.core.state_manager import SessionManager, session_manager
from src.agents.orchestrator import OrchestratorAgent
from src.models.session import SessionState
from src.api.routers import sessions, conversations, agents


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global orchestrator instance
orchestrator: OrchestratorAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Multi-Agent Support System...")
    
    # Initialize orchestrator
    global orchestrator
    orchestrator = OrchestratorAgent()
    
    # Set up dependencies
    orchestrator.set_dependencies(session_manager, None)  # Tool registry to be added later
    
    logger.info("System started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Multi-Agent Support System...")
    
    # Clean up orchestrator
    if orchestrator and orchestrator.coordination_manager:
        await orchestrator.coordination_manager.shutdown()
    
    # Clean up session manager
    await session_manager.cleanup_expired_sessions()
    
    logger.info("System shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Multi-Agent Customer Support System",
    description="AI-powered customer support system with multiple specialized agents",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router, prefix=f"{settings.api_v1_str}/sessions", tags=["sessions"])
app.include_router(conversations.router, prefix=f"{settings.api_v1_str}/conversations", tags=["conversations"])
app.include_router(agents.router, prefix=f"{settings.api_v1_str}/agents", tags=["agents"])


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_message(self, session_id: str, message: Dict[str, Any]):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {str(e)}")
                self.disconnect(session_id)


manager = ConnectionManager()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication."""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Process message through orchestrator
            try:
                if orchestrator:
                    response = await orchestrator.handle_user_input(session_id, data)
                    
                    # Send response back to client
                    await manager.send_message(session_id, {
                        "type": "agent_response",
                        "data": response
                    })
                else:
                    await manager.send_message(session_id, {
                        "type": "error",
                        "message": "System not ready"
                    })
                    
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": "An error occurred processing your request"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(session_id)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Multi-Agent Customer Support System",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": "2025-01-11T00:00:00Z",  # Would use actual timestamp
        "components": {
            "api": "healthy",
            "orchestrator": "healthy" if orchestrator else "not_initialized",
            "session_manager": "healthy"
        }
    }
    
    # Check Redis connection
    try:
        await session_manager.redis_client.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="System not ready")
    
    # Get coordination metrics
    coordination_metrics = await orchestrator.get_coordination_metrics()
    
    # Get session metrics
    active_sessions = await session_manager.get_active_sessions()
    
    return {
        "coordination": coordination_metrics,
        "sessions": {
            "active_count": len(active_sessions),
            "active_sessions": active_sessions[:10]  # Return first 10 for debugging
        },
        "system": {
            "orchestrator_ready": orchestrator is not None,
            "agents_registered": list(orchestrator.agents.keys()) if orchestrator else []
        }
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return {
        "error": "Internal server error",
        "message": "An unexpected error occurred"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )