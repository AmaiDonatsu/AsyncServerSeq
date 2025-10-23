# AsyncServer - FastAPI with Firebase Cloud Storage and WebSocket Streaming

API built with FastAPI and integrated with Firebase Cloud Storage for file management and real-time streaming via WebSocket.

## 🧭 Purpose and role in AsyncControl

AsyncServer is the central backend API and WebSocket hub for the AsyncControl ecosystem:

- AsyncControl Mobile App (Android/iOS): captures the screen and streams frames to the server.
- AsyncControl Web Console: lets users create profiles, manage devices and API keys, and view live streams.
- This Server/API (you are here): authenticates users, manages accounts and keys, brokers real-time streams, and exposes Cloud Storage utilities.

### What it does

- Identity and accounts: Uses Firebase Auth ID tokens; all requests are scoped to the authenticated user (UID).
- API Key management: Create/list/update keys stored in Firestore, bound to the user. Fields include `device`, `name`, `secretKey`, and `reserved` to indicate availability. See `routes/keys.py`.
- Real-time streaming: Mobile devices transmit frames via `WS /ws/stream` and viewers connect via `WS /ws/view`. The server validates `token + secretKey + device` against Firestore and routes frames to all viewers for that user/device. See `routes/ws_endpoint.py`.
- File operations: Upload, download, list, delete, and generate signed URLs in Firebase Cloud Storage.

### Data flow (high level)

1) User signs in (Firebase Auth) and gets an ID token.
2) From the Web Console, the user creates an API key in Firestore for a specific `device`.
3) The Mobile App starts streaming with `token + secretKey + device` → server validates and accepts the stream.
4) The Web Console joins as a viewer with the same `token + secretKey + device` → server forwards frames in real time.

Security model: Double validation (Firebase Auth + Firestore key binding) and per-user isolation using a connection ID of `uid:device`. Only the owner can manage keys, and viewers must match the same user/device. One active streamer is tracked per `uid:device`.

## 📋 Prerequisites

- Python 3.8+
- Firebase account with Cloud Storage enabled
- Firebase Service Account credentials file

## 🚀 Initial Setup

### 1) Install Dependencies

Dependencies are already installed in the virtual environment. If you need to reinstall them:

```powershell
./env/Scripts/Activate.ps1
pip install fastapi uvicorn firebase-admin python-dotenv
```

### 2) Configure Firebase

#### a) Get Firebase Credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (or create a new one)
3. Go to Project Settings (gear icon) → Service Accounts
4. Click Generate new private key
5. Save the downloaded JSON as `firebase-credentials.json`

#### b) Place the Credentials File

Copy the downloaded file to the `config/` folder:

```powershell
copy C:\path\to\download\your-project-firebase-adminsdk-xxxxx.json config\firebase-credentials.json
```

#### c) Enable Cloud Storage

1. In Firebase Console, go to Storage
2. Click Get started
3. Configure security rules as needed
4. Copy your bucket name (example: `your-project.appspot.com`)

### 3) Configure Environment Variables

Edit the `.env` file and update these values:

```env
# Firebase configuration
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-project.appspot.com  # ⚠️ CHANGE THIS

# Server configuration
HOST=0.0.0.0
PORT=8000
```

⚠️ IMPORTANT: Replace `your-project.appspot.com` with your actual bucket name.

## ▶️ Run the Server

### Activate the virtual environment (if not already active):

```powershell
./env/Scripts/Activate.ps1
```

### Start the server:

```powershell
python server.py
```

The server will be available at: `http://localhost:8000`

## 📚 API Documentation

Once the server is running, access:

- Swagger UI (interactive): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🛣️ Available Endpoints

### General

- `GET /` - Basic server information
- `GET /health` - Server and Firebase status

### 🌐 WebSocket Streaming (`/ws`)

#### 📡 Real-Time Stream (Transmitter)
```
WS /ws/stream
```
- Query parameters:
  - `token`: Firebase Auth ID token
  - `secretKey`: Firestore secret key
  - `device`: Device name
- Functionality: Real-time screen streaming from mobile apps
- Role: TRANSMITTER — sends frames to the server

#### 👁️ View Stream (Viewer) ⭐ NEW
```
WS /ws/view
```
- Query parameters:
  - `token`: Firebase Auth ID token
  - `secretKey`: Firestore secret key
  - `device`: Device name to view
- Functionality: View your own stream in real time
- Role: VIEWER — receives frames from the server
- Use cases:
  - 📹 View remote security cameras
  - 💻 Monitor screens in shops/offices
  - 🏠 Home surveillance
- Requirements: There must be an active stream for that device
- Full documentation: see `docs/ENDPOINT_VIEW_STREAM.md`

#### 📊 Connection Status
```
GET /ws/status
```
- Returns:
  - Number of active streamers
  - Number of viewers per stream
  - List of devices currently streaming

🚀 WebSocket Quickstart: see `docs/QUICKSTART_WEBSOCKET.md`

### Cloud Storage (`/storage`)

#### 📤 Upload File
```
POST /storage/upload
```
- Parameters:
  - `file`: File to upload (form-data)
  - `folder`: (Optional) Destination folder
- Returns: File info and public URL

#### 📥 Download File
```
GET /storage/download/{file_path}
```
- Parameters:
  - `file_path`: Full file path
- Returns: The file contents for download

#### 📋 List Files
```
GET /storage/list
```
- Query parameters:
  - `prefix`: (Optional) Filter by folder
- Returns: List of files with metadata

#### 🗑️ Delete File
```
DELETE /storage/delete/{file_path}
```
- Parameters:
  - `file_path`: Full file path
- Returns: Deletion confirmation

#### 🔗 Generate Signed URL
```
GET /storage/url/{file_path}
```
- Parameters:
  - `file_path`: File path
  - `expiration_minutes`: (Query, default: 60) Expiration time
- Returns: Temporary signed URL

## 🧪 Try the Endpoints

### Example with cURL (PowerShell):

#### Upload a file
```powershell
curl -X POST "http://localhost:8000/storage/upload?folder=test" `
  -H "accept: application/json" `
  -H "Content-Type: multipart/form-data" `
  -F "file=@C:\path\to\your\file.jpg"
```

#### List files
```powershell
curl http://localhost:8000/storage/list
```

#### Download a file
```powershell
curl -o downloaded_file.jpg http://localhost:8000/storage/download/test/file.jpg
```

## 📁 Project Structure

```
AsyncServer/
├── server.py              # Main application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── .gitignore             # Files ignored by Git
├── config/
│   ├── firebase_config.py           # Firebase configuration
│   ├── auth_dependencies.py         # Authentication
│   └── firebase-credentials.json    # Credentials (DO NOT COMMIT)
├── routes/
│   ├── keys.py           # API keys management
│   ├── storage.py        # Cloud Storage endpoints
│   └── ws_endpoint.py    # WebSocket streaming ⭐ NEW
├── docs/
│   ├── WEBSOCKET_STREAMING.md       # Full WebSocket guide ⭐
│   ├── QUICKSTART_WEBSOCKET.md      # Quickstart ⭐
│   └── REACT_NATIVE_INTEGRATION.md  # Mobile examples ⭐
├── test/
│   ├── test_websocket.py            # WebSocket tests ⭐
│   └── simulate_client.py           # Simulated client ⭐
└── env/                  # Virtual environment
```

## 🔒 Security

### ⚠️ Sensitive Files

The `.gitignore` is configured to avoid committing:
- `config/firebase-credentials.json` — Firebase credentials
- `.env` — Environment variables
- `env/` — Virtual environment

### 🔐 Firebase Security Rules

By default, files may be public. For stronger security, configure Firebase Storage rules:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      // Allow read for all, write only for authenticated users
      allow read;
      allow write: if request.auth != null;
    }
  }
}
```

## 🐛 Troubleshooting

### Error: "Credentials file not found"
- Ensure `firebase-credentials.json` exists in the `config/` folder
- Confirm the path in `.env` is correct

### Error: "FIREBASE_STORAGE_BUCKET is not set"
- Edit `.env` and update `FIREBASE_STORAGE_BUCKET` with your real bucket

### Error: "Firebase failed to initialize"
- Verify your Storage bucket is enabled in Firebase Console
- Confirm the credentials have Storage permissions

### Server starts but Storage doesn’t work
- Check console logs when starting the server
- Verify Firebase status messages
- Use the `/health` endpoint to verify status

## ✨ Key Features

- ✅ Firebase Cloud Storage — Upload, download, list, delete files
- ✅ Firebase Auth — User authentication
- ✅ Firestore — Database for API key management
- ✅ WebSocket Streaming — Real-time streaming with authentication
- ✅ Robust Authentication — Double validation (Auth + Firestore)
- ✅ Interactive Documentation — Automatic Swagger UI
- ✅ CORS Enabled — Ready for mobile and web apps

## 🔄 Next Steps

1. ✅ Configure Firebase (done)
2. ✅ Implement user authentication (done)
3. ✅ WebSocket streaming (done) ⭐
4. 🖼️ Add image processing
5. 📊 Implement file size limits
6. 🗂️ Folder management and organization
7. 📈 Add metrics and logging

## 📖 Docs and Resources

### Project Docs

- 📡 WebSocket Streaming: `docs/WEBSOCKET_STREAMING.md` — Full guide
- 🚀 WS Quickstart: `docs/QUICKSTART_WEBSOCKET.md` — Setup in 5 minutes
- 📱 React Native: `docs/REACT_NATIVE_INTEGRATION.md` — Mobile examples
- 🔐 Authentication: `docs/AUTENTICACION_FIREBASE.md`
- 🗄️ Firestore: `docs/GUIA_FIRESTORE.md`

### External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Firebase Admin SDK for Python](https://firebase.google.com/docs/admin/setup)
- [Firebase Cloud Storage](https://firebase.google.com/docs/storage)
- [WebSocket Protocol RFC 6455](https://www.rfc-editor.org/rfc/rfc6455)

## 📝 Notes

- Files uploaded via `/upload` are made public automatically
- For private temporary URLs, use the `/url` endpoint
- The maximum file size depends on FastAPI configuration (default: no hard limit)

---

Need help? Check the interactive docs at `/docs` when the server is running.
