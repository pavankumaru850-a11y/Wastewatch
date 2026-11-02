"""run.py -- convenience launcher. Equivalent to:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
