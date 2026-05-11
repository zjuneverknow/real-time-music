from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

try:
    from ..services.mood_processing import MoodProcessor
    from .socket_flow import run_music_socket
except ImportError:
    from services.mood_processing import MoodProcessor
    from api.socket_flow import run_music_socket


app = FastAPI(title="Emotion-Driven Music Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = MoodProcessor()


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/music")
async def music_socket(websocket: WebSocket) -> None:
    await run_music_socket(websocket, processor)
