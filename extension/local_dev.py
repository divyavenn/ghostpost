"""
Local development server - runs FastAPI without Modal wrapper
"""
from main import api

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:api", host="127.0.0.1", port=8000, reload=True)
