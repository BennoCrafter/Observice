from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import aiofiles
import os
from fastapi.routing import APIRouter

livelog_router = APIRouter()


# Mount the static directory for additional assets
livelog_router.mount("/static", StaticFiles(directory="app/routes/static"), name="static")

@livelog_router.get("/")
async def get():
    # Asynchronously load the index.html file
    async with aiofiles.open("app/routes/livelog/index.html", mode="r") as f:
        html_content = await f.read()
    return HTMLResponse(html_content)

async def tail_log_file(file_path: str, websocket: WebSocket, debug: bool = False):
    """
    Tail the log file asynchronously, sending new lines to the websocket.
    """
    try:
        if not os.path.exists(file_path):
            await websocket.send_text(f"Log file '{file_path}' does not exist.")
            return
        async with aiofiles.open(file_path, mode="r") as log_file:
            await websocket.send_text(await log_file.read())

            await log_file.seek(0, 2)

            while True:
                line = await log_file.readline()
                if line:
                    try:
                        await websocket.send_text(line.rstrip())
                        if debug:
                            print(f"Sent log: {line.rstrip()}")
                    except WebSocketDisconnect:
                        print("WebSocket disconnected, stopping log streaming.")
                        break
                else:
                    await asyncio.sleep(1)

    except Exception as e:
        # If an error occurs while reading the log file, send an error message.
        try:
            await websocket.send_text(f"Error reading log file: {e}")
        except WebSocketDisconnect:
            print("WebSocket disconnected while handling error.")

@livelog_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Accepts a websocket connection and streams log updates.
    """
    await websocket.accept()
    try:
        await tail_log_file("/Users/benno/coding/Observice/scratches/livelog/app.log", websocket, debug=True)
    except WebSocketDisconnect:
        print("Client disconnected from websocket")
    except Exception as e:
        print(f"Unexpected error in websocket: {e}")
