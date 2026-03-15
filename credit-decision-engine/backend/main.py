from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
from typing import List, Optional
import os

from routes.upload import router as upload_router
from routes.risk import router as risk_router
from routes.research import router as research_router
from routes.cam import router as cam_router

app = FastAPI(
    title="AI Credit Decisioning Engine",
    description="Production-grade credit decisioning system with AI-powered risk assessment",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(risk_router, prefix="/api", tags=["risk"])
app.include_router(research_router, prefix="/api", tags=["research"])
app.include_router(cam_router, prefix="/api", tags=["cam"])

@app.get("/")
async def root():
    return {"message": "AI Credit Decisioning Engine API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
