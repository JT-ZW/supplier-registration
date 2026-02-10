#!/usr/bin/env python
"""
Simple entry point to start the FastAPI backend server.
Run with: python app.py
"""

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print(f"🚀 Starting {settings.APP_NAME}")
    print(f"📝 Environment: {settings.APP_ENV}")
    print(f"🔗 Server: http://{settings.HOST}:{settings.PORT}")
    print(f"📚 API Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"🔄 Auto-reload: {'Enabled' if settings.DEBUG else 'Disabled'}")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
        access_log=settings.DEBUG,
    )
