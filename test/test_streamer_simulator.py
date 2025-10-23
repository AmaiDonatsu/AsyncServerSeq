"""
Simulador de Streamer para Testing
Envía imágenes alternadas (example0.png y example1.png) cada segundo
"""

import asyncio
import websockets
import json
import sys
from pathlib import Path

# Configuración
WS_URL = "ws://localhost:8000/ws/stream"
IMAGE_FOLDER = Path(__file__).parent / "img"
IMAGE_1 = IMAGE_FOLDER / "example0.png"
IMAGE_2 = IMAGE_FOLDER / "example1.png"
FRAME_INTERVAL = 1.0  # segundos entre frames


async def simulate_stream(token: str, secret_key: str, device: str):
    """
    Simula un streamer enviando imágenes alternadas
    
    Args:
        token: Firebase Auth ID token
        secret_key: Secret key de Firestore
        device: Nombre del dispositivo
    """
    
    # URL con query parameters
    url = f"{WS_URL}?token={token}&secretKey={secret_key}&device={device}"
    
    print("="*60)
    print("🎬 Iniciando simulador de streamer")
    print(f"📱 Device: {device}")
    print(f"🔑 SecretKey: {secret_key[:20]}...")
    print(f"🌐 Conectando a: {WS_URL}")
    print("="*60)
 
    if not IMAGE_1.exists():
        print(f"❌ Error: No se encuentra {IMAGE_1}")
        return
    
    if not IMAGE_2.exists():
        print(f"❌ Error: No se encuentra {IMAGE_2}")
        return
    
    print(f"✅ Imagen 1 encontrada: {IMAGE_1.name} ({IMAGE_1.stat().st_size} bytes)")
    print(f"✅ Imagen 2 encontrada: {IMAGE_2.name} ({IMAGE_2.stat().st_size} bytes)")
    print()
    
    try:
        async with websockets.connect(url) as websocket:
            print("✅ Conexión WebSocket establecida")
            
            # Recibir mensaje de bienvenida
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"📨 Mensaje de bienvenida: {welcome_data.get('message')}")
            print(f"👤 User ID: {welcome_data.get('user_id')}")
            print()
            
            frame_count = 0
            images = [IMAGE_1, IMAGE_2]
            
            print("🎥 Iniciando envío de frames...")
            print(f"⏱️ Intervalo: {FRAME_INTERVAL} segundo(s) entre frames")
            print("🔄 Presiona Ctrl+C para detener")
            print()
            
            while True:
                current_image = images[frame_count % 2]
                
                with open(current_image, 'rb') as f:
                    image_data = f.read()
                
                frame_count += 1
                await websocket.send(image_data)
                
                print(f"📸 Frame {frame_count} enviado | Imagen: {current_image.name} | Tamaño: {len(image_data)} bytes")
                
                try:
                    ack = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    ack_data = json.loads(ack)
                    if ack_data.get('type') == 'frame_ack':
                        print(f"   ✅ ACK recibido: Frame #{ack_data.get('frame_number')}")
                except asyncio.TimeoutError:
                    print(f"   ⚠️ No se recibió ACK (timeout)")
                except Exception as e:
                    print(f"   ⚠️ Error al recibir ACK: {e}")
                
                print()
                
                await asyncio.sleep(FRAME_INTERVAL)
    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 Conexión cerrada: {e}")
    
    except KeyboardInterrupt:
        print("\n⏹️ Simulación detenida por el usuario")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """
    Función principal - solicita credenciales y ejecuta el simulador
    """
    print("\n" + "="*60)
    print("🎬 SIMULADOR DE STREAMER")
    print("="*60 + "\n")
    
    # Solicitar credenciales
    print("Por favor ingresa las credenciales:")
    print()
    
    token = input("🎫 Firebase Auth Token: ").strip()
    if not token:
        print("❌ Error: El token no puede estar vacío")
        sys.exit(1)
    
    secret_key = input("🔑 Secret Key: ").strip()
    if not secret_key:
        print("❌ Error: El secret key no puede estar vacío")
        sys.exit(1)
    
    device = input("📱 Device Name: ").strip()
    if not device:
        print("❌ Error: El device name no puede estar vacío")
        sys.exit(1)
    
    print()
    
    try:
        asyncio.run(simulate_stream(token, secret_key, device))
    except KeyboardInterrupt:
        print("\n👋 Adiós!")


if __name__ == "__main__":
    main()
