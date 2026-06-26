# app/modules/support/manager.py
from fastapi import WebSocket
from typing import Dict, List


class ConnectionManager:
    def __init__(self):
        # ساختار: { user_id: [websocket1, websocket2, ...] }
        # استفاده از لیست به این دلیل است که ممکن است کاربر از دو دستگاه همزمان لاگین باشد
        # یا همزمان کاربر و ادمین در یک روم (user_id) آنلاین باشند.
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_user_id: int):
        await websocket.accept()
        if room_user_id not in self.active_connections:
            self.active_connections[room_user_id] = []
        self.active_connections[room_user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_user_id: int):
        if room_user_id in self.active_connections:
            self.active_connections[room_user_id].remove(websocket)
            if not self.active_connections[room_user_id]:
                del self.active_connections[room_user_id]

    async def send_personal_message(self, message: dict, room_user_id: int):
        """ارسال پیام به تمام کسانی که در یک روم خاص آنلاین هستند (هم کاربر و هم ادمینی که روم را باز کرده)"""
        if room_user_id in self.active_connections:
            for connection in self.active_connections[room_user_id]:
                await connection.send_json(message)


manager = ConnectionManager()
