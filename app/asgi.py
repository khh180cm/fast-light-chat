"""ASGI application with Socket.IO integration."""

import socketio

from app.main import create_app
from app.sockets.server import sio

# Create FastAPI app
fastapi_app = create_app()

# Create Socket.IO ASGI app that wraps FastAPI
# Socket.IO will handle /socket.io/* routes
# FastAPI will handle all other routes
app = socketio.ASGIApp(
    sio,
    other_asgi_app=fastapi_app,
    socketio_path="/socket.io",
)
