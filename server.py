import fastapi
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from config.firebase_config import FirebaseConfig
from routes.storage import router as storage_router
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación
    Se ejecuta al iniciar y al cerrar el servidor
    """
    # Startup: Inicializar Firebase
    print("🚀 Iniciando servidor...")
    try:
        FirebaseConfig.initialize()
        print("✓ Firebase Cloud Storage listo")
    except Exception as e:
        print(f"⚠ Advertencia: Firebase no se pudo inicializar: {e}")
        print("El servidor continuará pero las funciones de Storage no estarán disponibles")
    
    yield
    
    # Shutdown
    print("👋 Cerrando servidor...")

# Crear la aplicación con lifespan
app = fastapi.FastAPI(
    title="AsyncServer API",
    description="API con integración de Firebase Cloud Storage",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(storage_router)

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