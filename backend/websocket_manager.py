# websocket_manager.py
from fastapi import WebSocket, WebSocketDisconnect

conexiones = {}

async def conectar(websocket: WebSocket, subasta_id: int):
    await websocket.accept()

    if subasta_id not in conexiones:
        conexiones[subasta_id] = []

    conexiones[subasta_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        conexiones[subasta_id].remove(websocket)


async def notificar_puja(subasta_id: int, nuevo_precio: float):
    if subasta_id in conexiones:
        for ws in conexiones[subasta_id]:
            await ws.send_json({"tipo": "nueva_puja", "nuevo_precio": nuevo_precio})
