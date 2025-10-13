# AsyncServer - FastAPI con Firebase Cloud Storage

API construida con FastAPI e integración con Firebase Cloud Storage para gestión de archivos.

## 📋 Requisitos Previos

- Python 3.8+
- Cuenta de Firebase con Cloud Storage habilitado
- Archivo de credenciales de Firebase (Service Account)

## 🚀 Configuración Inicial

### 1. Instalar Dependencias

Las dependencias ya están instaladas en el entorno virtual. Si necesitas reinstalarlas:

```powershell
.\env\Scripts\Activate.ps1
pip install fastapi uvicorn firebase-admin python-dotenv
```

### 2. Configurar Firebase

#### a) Obtener Credenciales de Firebase

1. Ve a [Firebase Console](https://console.firebase.google.com/)
2. Selecciona tu proyecto (o crea uno nuevo)
3. Ve a **Configuración del Proyecto** (ícono de engranaje) → **Cuentas de servicio**
4. Haz clic en **Generar nueva clave privada**
5. Guarda el archivo JSON descargado como `firebase-credentials.json`

#### b) Colocar el Archivo de Credenciales

Copia el archivo descargado a la carpeta `config/`:
```powershell
copy C:\ruta\de\descarga\tu-proyecto-firebase-adminsdk-xxxxx.json config\firebase-credentials.json
```

#### c) Habilitar Cloud Storage

1. En Firebase Console, ve a **Storage**
2. Haz clic en **Comenzar**
3. Configura las reglas de seguridad según tus necesidades
4. Copia el nombre de tu bucket (ejemplo: `tu-proyecto.appspot.com`)

### 3. Configurar Variables de Entorno

Edita el archivo `.env` y actualiza estos valores:

```env
# Configuración de Firebase
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_STORAGE_BUCKET=tu-proyecto.appspot.com  # ⚠️ CAMBIA ESTO

# Configuración del servidor
HOST=0.0.0.0
PORT=8000
```

**⚠️ IMPORTANTE:** Reemplaza `tu-proyecto.appspot.com` con el nombre real de tu bucket.

## ▶️ Ejecutar el Servidor

### Activar el entorno virtual (si no está activado):
```powershell
.\env\Scripts\Activate.ps1
```

### Iniciar el servidor:
```powershell
python server.py
```

El servidor estará disponible en: `http://localhost:8000`

## 📚 Documentación de la API

Una vez el servidor esté corriendo, accede a:

- **Swagger UI (interactiva):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 🛣️ Endpoints Disponibles

### General

- `GET /` - Información básica del servidor
- `GET /health` - Estado del servidor y Firebase

### Cloud Storage (`/storage`)

#### 📤 Subir Archivo
```
POST /storage/upload
```
- **Parámetros:**
  - `file`: Archivo a subir (form-data)
  - `folder`: (Opcional) Carpeta destino
- **Retorna:** Información del archivo y URL pública

#### 📥 Descargar Archivo
```
GET /storage/download/{file_path}
```
- **Parámetros:**
  - `file_path`: Ruta completa del archivo
- **Retorna:** El archivo para descargar

#### 📋 Listar Archivos
```
GET /storage/list
```
- **Parámetros (query):**
  - `prefix`: (Opcional) Filtrar por carpeta
- **Retorna:** Lista de archivos con metadatos

#### 🗑️ Eliminar Archivo
```
DELETE /storage/delete/{file_path}
```
- **Parámetros:**
  - `file_path`: Ruta completa del archivo
- **Retorna:** Confirmación de eliminación

#### 🔗 Generar URL Firmada
```
GET /storage/url/{file_path}
```
- **Parámetros:**
  - `file_path`: Ruta del archivo
  - `expiration_minutes`: (Query, default: 60) Tiempo de expiración
- **Retorna:** URL temporal firmada

## 🧪 Probar los Endpoints

### Ejemplo con cURL (PowerShell):

#### Subir un archivo:
```powershell
curl -X POST "http://localhost:8000/storage/upload?folder=test" `
  -H "accept: application/json" `
  -H "Content-Type: multipart/form-data" `
  -F "file=@C:\ruta\a\tu\archivo.jpg"
```

#### Listar archivos:
```powershell
curl http://localhost:8000/storage/list
```

#### Descargar un archivo:
```powershell
curl -o archivo_descargado.jpg http://localhost:8000/storage/download/test/archivo.jpg
```

## 📁 Estructura del Proyecto

```
AsyncServer/
├── server.py              # Aplicación principal
├── .env                   # Variables de entorno
├── .gitignore            # Archivos ignorados por git
├── config/
│   ├── firebase_config.py           # Configuración de Firebase
│   └── firebase-credentials.json    # Credenciales (NO SUBIR A GIT)
├── routes/
│   ├── keys.py           # Rutas existentes
│   └── storage.py        # Rutas de Cloud Storage
└── env/                  # Entorno virtual
```

## 🔒 Seguridad

### ⚠️ Archivos Sensibles

El archivo `.gitignore` ya está configurado para **NO subir** a Git:
- `config/firebase-credentials.json` - Credenciales de Firebase
- `.env` - Variables de entorno
- `env/` - Entorno virtual

### 🔐 Reglas de Seguridad en Firebase

Por defecto, los archivos son públicos. Para mayor seguridad, configura reglas en Firebase Storage:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      // Permitir lectura a todos, escritura solo autenticados
      allow read;
      allow write: if request.auth != null;
    }
  }
}
```

## 🐛 Solución de Problemas

### Error: "No se encontró el archivo de credenciales"
- Verifica que `firebase-credentials.json` esté en la carpeta `config/`
- Confirma que la ruta en `.env` sea correcta

### Error: "FIREBASE_STORAGE_BUCKET no está configurada"
- Edita `.env` y actualiza `FIREBASE_STORAGE_BUCKET` con tu bucket real

### Error: "Firebase no se pudo inicializar"
- Verifica que tu bucket de Storage esté habilitado en Firebase Console
- Confirma que las credenciales tengan permisos de Storage

### El servidor arranca pero Storage no funciona
- Revisa la consola al iniciar el servidor
- Verifica los mensajes de estado de Firebase
- Usa el endpoint `/health` para verificar el estado

## 🔄 Próximos Pasos

1. ✅ Configurar Firebase (completado)
2. 📝 Implementar autenticación de usuarios
3. 🖼️ Añadir procesamiento de imágenes
4. 📊 Implementar límites de tamaño de archivo
5. 🗂️ Gestión de carpetas y organización
6. 📈 Agregar métricas y logging

## 📖 Recursos Adicionales

- [Documentación de FastAPI](https://fastapi.tiangolo.com/)
- [Firebase Admin SDK para Python](https://firebase.google.com/docs/admin/setup)
- [Firebase Cloud Storage](https://firebase.google.com/docs/storage)

## 📝 Notas

- Los archivos subidos con el endpoint `/upload` se hacen públicos automáticamente
- Para URLs privadas temporales, usa el endpoint `/url`
- El tamaño máximo de archivo depende de la configuración de FastAPI (default: sin límite)

---

**¿Necesitas ayuda?** Revisa la documentación interactiva en `/docs` cuando el servidor esté corriendo.
