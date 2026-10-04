import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"Starting Medical VR Training Backend on http://{host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
