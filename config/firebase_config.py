import firebase_admin
from firebase_admin import credentials, storage, firestore, auth
from google.cloud.firestore import Client as FirestoreClient
import os
import json
import base64
from dotenv import load_dotenv

from typing import Optional

load_dotenv()

class FirebaseConfig:
    """
    Config class to manage Firebase Admin SDK initialization and services
    """
    _initialized = False
    _bucket = None
    _firestore_db = None
    
    @classmethod
    def initialize(cls):
        if cls._initialized: return
        
        try:
            debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
            
            bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
            service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
            gcp_key_base64 = os.getenv('GCP_KEY_BASE64')
            cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')

            if debug_mode:
                print("="*50)
                print("🔧 FIREBASE CONFIG DEBUG")
                #print(f"  - BUCKET: {bucket_name}")
                print(f"  - GCP_KEY_BASE64 (len): {len(gcp_key_base64) if gcp_key_base64 else 0}")
                #print(f"  - SERVICE_ACCOUNT_JSON (len): {len(service_account_json) if service_account_json else 0}")
                #print(f"  - CRED_PATH: {cred_path}")
                print("="*50)

            cred_dict = None

            if gcp_key_base64:
                try:
                    print("⚙️ Procesando GCP_KEY_BASE64...")
                    decoded_json = base64.b64decode(gcp_key_base64).decode('utf-8')
                    cred_dict = json.loads(decoded_json)
                except Exception as e:
                    print(f"✗ Error al decodificar GCP_KEY_BASE64: {str(e)}")
                    raise
            elif service_account_json:
                try:
                    # Cargamos el string como diccionario
                    cred_dict = json.loads(service_account_json)
                except Exception as e:
                    print(f"✗ Error fatal en credenciales JSON: {str(e)}")
                    raise

            if cred_dict:
                # 🧪 CORRECCIÓN CRUCIAL:
                # Railway y otras plataformas a veces escapan las barras invertidas.
                # Esto asegura que los saltos de línea sean reales para la firma criptográfica.
                if "private_key" in cred_dict:
                    original_key = cred_dict["private_key"]
                    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
                    
                    if debug_mode:
                        print(f"  🔑 Private Key procesada.")
                        print(f"  - Original contiene \n literal: {'\n' in original_key}")
                        print(f"  - Final contiene salto de línea real: {'\n' in cred_dict['private_key']}")
                        # Mostramos solo inicio y fin por seguridad, pero suficiente para validar formato
                        safe_key_preview = cred_dict['private_key'][:40] + "..." + cred_dict['private_key'][-40:]
                        print(f"  - Key Preview: {safe_key_preview}")

                if debug_mode:
                    print(f"  - Project ID: {cred_dict.get('project_id')}")
                    print(f"  - Client Email: {cred_dict.get('client_email')}")
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
                
                # Tip científico: Si el proyecto sale como 'None', forzamos el ID del JSON
                project_id = cred_dict.get('project_id')
                print(f"✓ Firebase autenticado para el proyecto: {project_id}")

            elif cred_path and os.path.exists(cred_path):
                print(f"⚙️ Cargando credenciales desde archivo: {cred_path}")
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
            else:
                raise ValueError("No se encontraron credenciales de Firebase (Archivo, JSON o Base64)")
            
            cls._bucket = storage.bucket()
            cls._firestore_db = firestore.client()
            cls._initialized = True
            print(f"✓ Firebase inicializado correctamente")
        except Exception as e:
            print(f"✗ Error crítico al inicializar Firebase: {str(e)}")
            raise

    @classmethod
    def get_bucket(cls):
        """
        Returnns the Storage bucket instance
        """
        if not cls._initialized:
            cls.initialize()
        return cls._bucket
    
    @classmethod
    def is_initialized(cls):
        return cls._initialized
    
    @classmethod
    def get_firestore(cls) -> FirestoreClient:
        """
        Returns the Firestore Database instance
        
        Returns:
            firestore.Client: Client to access Firestore collections
        
        Example:
            db = FirebaseConfig.get_firestore()
            keys_ref = db.collection('keys')
            docs = keys_ref.stream()
        """
        if not cls._initialized:
            cls.initialize()
        
        if cls._firestore_db is None:
            raise RuntimeError("Firestore client not initialized")
        
        return cls._firestore_db
    
    @classmethod
    def verify_token(cls, id_token: str) -> dict:
        """
        Verifies a Firebase ID token and returns the decoded token
        
        Args:
            id_token: Token JWT enviado desde el frontend
        
        Returns:
            dict:
                - uid: user ID
                - email: Email
                - email_verified: Email verified status
                - name: user name (if available)
                - picture: URL of the user's picture (if available)
        
        Raises:
            auth.InvalidIdTokenError
            auth.ExpiredIdTokenError
            auth.RevokedIdTokenError
        
        Example:
            try:
                decoded_token = FirebaseConfig.verify_token(token)
                user_id = decoded_token['uid']
                email = decoded_token['email']
            except Exception as e:
                print(f"Token inválido: {e}")
        """
        if not cls._initialized:
            cls.initialize()
        
        # tolerar 10 segundos de skew de reloj
        decoded_token = auth.verify_id_token(id_token, clock_skew_seconds=10)
        return decoded_token
    
    @classmethod
    def get_user_by_id(cls, user_id: str):
        """
        Obtains a user record by their user ID
        
        Args:
            user_id
        
        Returns:
            UserRecord: user registro with all their information
        
        Example:
            user = FirebaseConfig.get_user_by_id('abc123')
            print(user.email, user.display_name)
        """
        if not cls._initialized:
            cls.initialize()
        
        return auth.get_user(user_id)
