import json
from fastapi import WebSocket, WebSocketDisconnect

class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_text()
        await self.handle_message(websocket, data)

    async def handle_message(self, websocket: WebSocket, data: str):
        msg = json.loads(data)
        if msg.get("type") == "subscribe":
            task_ids = msg.get("task_ids", [])
            self.disconnect(websocket)
            for tid in task_ids:
                if tid not in self._connections:
                    self._connections[tid] = []
                if websocket not in self._connections[tid]:
                    self._connections[tid].append(websocket)
        else:
            if "_all" not in self._connections:
                self._connections["_all"] = []
            if websocket not in self._connections["_all"]:
                self._connections["_all"].append(websocket)

    def disconnect(self, websocket: WebSocket):
        for tid in list(self._connections.keys()):
            self._connections[tid] = [ws for ws in self._connections[tid] if ws != websocket]
            if not self._connections[tid]:
                del self._connections[tid]

    async def broadcast_task_update(self, task_id: str, status: str, progress: int, stage_detail: str):
        from datetime import datetime, timezone
        message = json.dumps({
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "stage_detail": stage_detail,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        connections = self._connections.get(task_id, []) + self._connections.get("_all", [])
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                pass


ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
