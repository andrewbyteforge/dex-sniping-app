"""
Debug script to test dashboard components and identify issues.
"""

import sys
import os
import asyncio
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_dashboard_imports():
    """Test if dashboard imports work correctly."""
    print("🔍 TESTING DASHBOARD IMPORTS")
    print("=" * 50)
    
    try:
        print("1. Testing FastAPI import...")
        import fastapi
        print(f"   ✅ FastAPI version: {fastapi.__version__}")
    except ImportError as e:
        print(f"   ❌ FastAPI not installed: {e}")
        print("   💡 Install with: pip install fastapi")
        return False
    
    try:
        print("2. Testing Uvicorn import...")
        import uvicorn
        print(f"   ✅ Uvicorn available")
    except ImportError as e:
        print(f"   ❌ Uvicorn not installed: {e}")
        print("   💡 Install with: pip install uvicorn")
        return False
    
    try:
        print("3. Testing dashboard server import...")
        from api.dashboard_server import app, dashboard_server
        print("   ✅ Dashboard server imported successfully")
    except ImportError as e:
        print(f"   ❌ Dashboard server import failed: {e}")
        print("   💡 Check if api/dashboard_server.py exists")
        return False
    except Exception as e:
        print(f"   ❌ Dashboard server error: {e}")
        print(f"   📋 Full error: {traceback.format_exc()}")
        return False
    
    try:
        print("4. Testing dashboard initialization...")
        await dashboard_server.initialize()
        print("   ✅ Dashboard server initialized")
    except Exception as e:
        print(f"   ❌ Dashboard initialization failed: {e}")
        print(f"   📋 Full error: {traceback.format_exc()}")
        return False
    
    return True

async def test_minimal_server():
    """Test if we can start a minimal FastAPI server."""
    print("\n🚀 TESTING MINIMAL SERVER")
    print("=" * 50)
    
    try:
        from fastapi import FastAPI
        import uvicorn
        
        # Create minimal app
        test_app = FastAPI(title="Test Dashboard")
        
        @test_app.get("/")
        async def root():
            return {"message": "Dashboard test successful"}
        
        @test_app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        print("1. Starting test server on port 8001...")
        
        config = uvicorn.Config(
            test_app,
            host="127.0.0.1",
            port=8001,
            log_level="error"
        )
        
        server = uvicorn.Server(config)
        
        # Start server in background
        server_task = asyncio.create_task(server.serve())
        
        # Wait a moment for startup
        await asyncio.sleep(2)
        
        if not server_task.done():
            print("   ✅ Test server started successfully")
            print("   🌐 Test URL: http://localhost:8001")
            
            # Test endpoint
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:8001/health") as response:
                        if response.status == 200:
                            print("   ✅ Health endpoint working")
                        else:
                            print(f"   ⚠️ Health endpoint returned {response.status}")
            except Exception as e:
                print(f"   ⚠️ Could not test endpoint: {e}")
            
            # Stop server
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            
            print("   ✅ Test server stopped")
            return True
        else:
            print("   ❌ Test server failed to start")
            return False
            
    except Exception as e:
        print(f"   ❌ Minimal server test failed: {e}")
        print(f"   📋 Full error: {traceback.format_exc()}")
        return False

def check_file_structure():
    """Check if required files exist."""
    print("\n📁 CHECKING FILE STRUCTURE")
    print("=" * 50)
    
    required_files = [
        "api/__init__.py",
        "api/dashboard_server.py",
        "web/templates/dashboard.html",
        "trading/__init__.py",
        "trading/executor.py"
    ]
    
    all_exist = True
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - Missing")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("\n📦 CHECKING DEPENDENCIES")
    print("=" * 50)
    
    required_packages = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("aiohttp", "HTTP client"),
        ("jinja2", "Template engine"),
        ("websockets", "WebSocket support")
    ]
    
    all_installed = True
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package} - {description}")
        except ImportError:
            print(f"   ❌ {package} - {description} - Not installed")
            print(f"      Install with: pip install {package}")
            all_installed = False
    
    return all_installed

def suggest_fixes():
    """Suggest fixes for common dashboard issues."""
    print("\n💡 SUGGESTED FIXES")
    print("=" * 50)
    
    print("1. Install missing dependencies:")
    print("   pip install fastapi uvicorn jinja2 websockets aiohttp")
    print()
    
    print("2. Create minimal dashboard if missing:")
    print("   python -c \"from api.dashboard_server import app; print('Dashboard available')\"")
    print()
    
    print("3. Test port availability:")
    print("   netstat -an | grep :8000")
    print("   # Or use different port in config")
    print()
    
    print("4. Run system without dashboard:")
    print("   python main_production.py --no-dashboard")
    print()
    
    print("5. Check logs for detailed errors:")
    print("   tail -f logs/dex_sniping.log")

async def main():
    """Main debug function."""
    print("🔧 DASHBOARD DEBUG UTILITY")
    print("=" * 60)
    
    # Check file structure
    files_ok = check_file_structure()
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Test imports
    imports_ok = await test_dashboard_imports()
    
    # Test minimal server
    server_ok = await test_minimal_server() if imports_ok else False
    
    print("\n📊 SUMMARY")
    print("=" * 50)
    print(f"File Structure: {'✅ OK' if files_ok else '❌ Issues'}")
    print(f"Dependencies: {'✅ OK' if deps_ok else '❌ Missing'}")
    print(f"Imports: {'✅ OK' if imports_ok else '❌ Failed'}")
    print(f"Server Test: {'✅ OK' if server_ok else '❌ Failed'}")
    
    if all([files_ok, deps_ok, imports_ok, server_ok]):
        print("\n🎉 Dashboard should work! Try running the main system.")
    else:
        print("\n⚠️ Issues found. See suggested fixes below.")
        suggest_fixes()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDebug interrupted by user")
    except Exception as e:
        print(f"\nDebug script error: {e}")
        traceback.print_exc()