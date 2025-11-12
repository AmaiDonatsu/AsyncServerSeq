from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/device", tags=["device_control"])

@router.post("/command")
async def send_command(command: str):
    # Logic to send command to the device
    print(f"Command sent to device: {command}")
    return {"status": "success", "command": command}
@router.post("/test")
async def test_device():
    # Logic to test device connectivity
    print("Device connectivity test initiated")
    return {"status": "success", "message": "Device connectivity test initiated"}