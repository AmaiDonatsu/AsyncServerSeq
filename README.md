# AsyncServerSeq

AsyncServerSeq is the central server that bridges Streamer devices (TypusControlMini) with the Monitor and command console of AsyncControl.

<p align="center">
  <img src="resources\AyncGirl.png" alt="Logo" width="200" />
</p>

The backend application facilitates secure, real-time communication between multiple 'Streamer' devices (running TypusControlMini) and the 'Viewer' interface (*AsyncControl*). Leveraging FastAPI and WebSockets, it orchestrates the low-latency transmission of screen capture frames from authenticated devices to the user's control interface, while simultaneously routing control commands from AsyncControl back to the specific target devices.

The server enforces strict security boundaries, permitting communication solely between TypusControlMini and AsyncControl instances authenticated under the same user account. It validates Firebase Authentication tokens from both streamers and viewers to authorize connections. Furthermore, the application manages the generation of signed URLs for captured frames. This functionality enables integration with external AI vision models used by AsyncControl that require public resource access, allowing the server to upload frames and return secure, accessible URLs to the viewer.

Comprehensive key management is implemented to handle device authorization. While users generate keys through the AsyncControlWeb portal, AsyncServerSeq orchestrates their distribution and state. The API provides endpoints to assign keys to specific devices, track their reservation status, and release them back to the pool. This ensures that keys are correctly synchronized between the web interface, the backend, and the connected TypusControlMini devices.

## Getting Started

### Prerequisites
- **Python 3.10** or higher
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/AmaiDonatsu/AsyncServerSeq.git
   cd AsyncServerSeq
   ```

2. **Create and activate a virtual environment**
   It is recommended to use a virtual environment to manage dependencies.

   **Windows:**
   ```powershell
   python -m venv env
   .\env\Scripts\activate
   ```

   **macOS / Linux:**
   ```bash
   python3 -m venv env
   source env/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**
   - Create a `.env` file in the root directory if necessary (see `server.py` for environment variables like `HOST` and `PORT`).
   - Ensure your Firebase credentials (`firebase-credentials.json`) are placed in the `config/` directory to allow Firebase Authentication and Firestore connections.

### Running the Project

You can start the server by running the entry point script:

```bash
python server.py
```

Alternatively, you can run it using `uvicorn` directly (useful for development):

```bash
uvicorn server:app --reload
```

The server will start by default at `http://127.0.0.1:8000`.