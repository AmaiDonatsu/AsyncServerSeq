import fastapi
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = fastapi.FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def read_root():
    return {"Hello": "World"}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)