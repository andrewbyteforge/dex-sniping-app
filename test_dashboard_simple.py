"""
Very simple dashboard test without any complex imports.
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Create minimal test app
app = FastAPI(title="Test Dashboard")

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse("""
    <html>
    <head><title>Dashboard Test</title></head>
    <body style="background: #1a1b3e; color: white; font-family: Arial; padding: 20px;">
        <h1>🚀 Dashboard Connection Test</h1>
        <p>✅ If you can see this, the dashboard server is working!</p>
        <p>⏰ Time: <span id="time"></span></p>
        <script>
            setInterval(() => {
                document.getElementById('time').textContent = new Date().toLocaleTimeString();
            }, 1000);
        </script>
    </body>
    </html>
    """)

@app.get("/api/test")
async def test_api():
    return {"status": "working", "message": "Dashboard API is functional"}

async def main():
    print("🔧 SIMPLE DASHBOARD CONNECTION TEST")
    print("=" * 50)
    print("Starting basic web server on http://localhost:8000")
    print("If this works, the issue is with imports, not the web server")
    print("Press Ctrl+C to stop")
    
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
    
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped")