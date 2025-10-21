import firebase_admin
from firebase_admin import credentials, storage, firestore, auth
from google.cloud.firestore import Client as FirestoreClient
import os
from dotenv import load_dotenv

from typing import Optional

load_dotenv()

class FirebaseConfig:
    """
    Config class to manage Firebase Admin SDK initialization and services
    """
    _initialized = False
    _bucket = None
    _firestore_db: Optional[FirestoreClient] = None
    
    @classmethod
    def initialize(cls):
        """
        Init Firebase Admin SDK with credentials
         --- IGNORE ---
        """
        if cls._initialized:
            print("Firebase ya está inicializado")
            return
        
        try:
            cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'config/firebase-credentials.json')
            
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
            
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
            
            cls._bucket = storage.bucket()
            
            cls._firestore_db = firestore.client()
            
            cls._initialized = True
            
            print(f"✓ Firebase inicializado correctamente")
            print(f"✓ Cloud Storage bucket conectado: {bucket_name}")
            print(f"✓ Firestore database conectado")
            
        except Exception as e:
            print(f"✗ Error al inicializar Firebase: {str(e)}")
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
        
        decoded_token = auth.verify_id_token(id_token)
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
