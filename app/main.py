from fastapi import FastAPI

from app.ws.chat import router as chat_router

app = FastAPI(title = "Mini Rag Chatbot")

app.include_router(chat_router)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}