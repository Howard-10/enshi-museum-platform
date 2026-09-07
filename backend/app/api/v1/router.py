from fastapi import APIRouter

from app.api.v1.routes import admin, chat, health, knowledge, media, system, visual_search

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(visual_search.router, prefix="/visual-search", tags=["visual-search"])
