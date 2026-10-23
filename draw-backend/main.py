from fastapi import FastAPI, WebSocket
from typing import List
import pexpect
import sys

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.process = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data["action"] == "start_draw":
                print("Starting draw process...")
                # Lancer le processus Julia avec pexpect
                manager.process = pexpect.spawn('julia draw_matchups_first.jl', encoding='utf-8')
                
                while True:
                    try:
                        # on attend soit un texte, soit la demande d'entrée
                        index = manager.process.expect([
                            pexpect.EOF,
                            'Appuyez sur la barre'
                        ])
                        
                        # Récupération de toute la sortie
                        output = manager.process.before
                        if output:
                            print(f"Output received: {output}")
                            await manager.broadcast({
                                "type": "terminal_output",
                                "data": output
                            })
                        
                        # on attend une entrée
                        if index == 1:
                            print("Input required...")
                            await websocket.send_json({
                                "type": "wait_for_input",
                                "data": None
                            })
                            break
                        
                        #processus est terminé
                        elif index == 0:
                            print("Process ended")
                            await manager.broadcast({
                                "type": "draw_completed",
                                "data": None
                            })
                            break
                            
                    except Exception as e:
                        print(f"Error reading output: {e}")
                        break

            elif data["action"] == "continue_draw":
                if manager.process and manager.process.isalive():
                    print("Sending continue command...")
                    try:
                        manager.process.sendline(" ")
                        print("Continue command sent")
                        
                        # Attend la prochaine sortie
                        while True:
                            try:
                                index = manager.process.expect([
                                    pexpect.EOF,
                                    'Appuyez sur la barre'
                                ])
                                
                                output = manager.process.before
                                if output:
                                    print(f"Output after continue: {output}")
                                    await manager.broadcast({
                                        "type": "terminal_output",
                                        "data": output
                                    })
                                
                                if index == 1:
                                    await websocket.send_json({
                                        "type": "wait_for_input",
                                        "data": None
                                    })
                                    break
                                elif index == 0:
                                    print("Process ended after continue")
                                    break
                                    
                            except Exception as e:
                                print(f"Error after continue: {e}")
                                break
                                
                    except Exception as e:
                        print(f"Error sending continue command: {e}")
                else:
                    print("Process is not running")

    except Exception as e:
        print(f"Websocket error: {e}")
        print(f"Error details: {str(e)}")
    finally:
        if manager.process and manager.process.isalive():
            manager.process.terminate()
        manager.disconnect(websocket)