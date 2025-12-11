import fastapi
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from config.firebase_config import FirebaseConfig
from routes.storage import router as storage_router
from routes.keys import router as keys_router
from routes.ws_endpoint import router as ws_router
from routes.file_manager import router as file_manager_router
from routes.device_controler import router as device_control_router
from routes.docs import router as docs_router
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    """
    Manages the lifespan of the application
    """
    print("🚀 Iniciando servidor...")
    try:
        FirebaseConfig.initialize()
        print("✓ Firebase Cloud Storage listo")
        print("✓ Firebase Firestore listo")
    except Exception as e:
        print(f"⚠ Advertencia: Firebase no se pudo inicializar: {e}")
        print("El servidor continuará pero las funciones de Firebase no estarán disponibles")
    
    yield
    
    print("👋 Cerrando servidor...")

app = fastapi.FastAPI(
    title="AsyncServer API",
    description="API con integración de Firebase Cloud Storage",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(storage_router)
app.include_router(keys_router)
app.include_router(ws_router)
app.include_router(file_manager_router)
app.include_router(device_control_router)
app.include_router(docs_router)

@app.get("/")
async def read_root():
    """Endpoint de prueba"""
    firebase_status = "conectado" if FirebaseConfig.is_initialized() else "no conectado"
    return {
        "message": "AsyncServer API",
        "status": "running",
        "firebase_storage": firebase_status
    }

@app.get("/health")
async def health_check():
    """Verificar el estado del servidor y servicios"""
    return {
        "status": "healthy",
        "firebase_initialized": FirebaseConfig.is_initialized()
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=host, port=port)