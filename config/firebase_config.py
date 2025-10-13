import firebase_admin
from firebase_admin import credentials, storage
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class FirebaseConfig:
    """
    Configuración y gestión de Firebase Admin SDK
    """
    _initialized = False
    _bucket = None
    
    @classmethod
    def initialize(cls):
        """
        Inicializa Firebase Admin SDK con las credenciales
        """
        if cls._initialized:
            print("Firebase ya está inicializado")
            return
        
        try:
            # Ruta al archivo de credenciales de Firebase
            cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'config/firebase-credentials.json')
            
            # Nombre del bucket de Storage
            bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
            
            if not os.path.exists(cred_path):
                raise FileNotFoundError(
                    f"No se encontró el archivo de credenciales en: {cred_path}\n"
                    "Por favor, descarga tu archivo de credenciales desde Firebase Console."
                )
            
            if not bucket_name:
                raise ValueError(
                    "La variable FIREBASE_STORAGE_BUCKET no está configurada en .env\n"
                    "Ejemplo: FIREBASE_STORAGE_BUCKET=tu-proyecto.appspot.com"
                )
            
            # Inicializar Firebase Admin
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
            
            # Obtener referencia al bucket
            cls._bucket = storage.bucket()
            cls._initialized = True
            
            print(f"✓ Firebase inicializado correctamente")
            print(f"✓ Bucket conectado: {bucket_name}")
            
        except Exception as e:
            print(f"✗ Error al inicializar Firebase: {str(e)}")
            raise
    
    @classmethod
    def get_bucket(cls):
        """
        Retorna la instancia del bucket de Storage
        """
        if not cls._initialized:
            cls.initialize()
        return cls._bucket
    
    @classmethod
    def is_initialized(cls):
        """
        Verifica si Firebase está inicializado
        """
        return cls._initialized
