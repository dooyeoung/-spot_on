from starlette.websockets import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.usernames = {}
        self.quiz_results: dict[str, int] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def all_disconnect(self):
        del self.active_connections
        self.active_connections = []

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(
        self,
        message: dict,
    ):
        for connection in self.active_connections:
            await connection.send_json(message)
