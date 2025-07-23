#!/usr/bin/env python3
"""
Diagnose and fix dashboard issues.
"""

import os
import sys
import socket
import asyncio
import subprocess

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def check_port(port: int) -> bool:
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0  # True if port is in use
    except:
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")
    
    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")
    
    try:
        import websockets
    except ImportError:
        missing.append("websockets")
    
    return missing


def find_dashboard_issues():
    """Diagnose dashboard issues."""
    print("🔍 Diagnosing Dashboard Issues...\n")
    
    issues = []
    
    # 1. Check dependencies
    print("1. Checking dependencies...")
    missing_deps = check_dependencies()
    if missing_deps:
        issues.append(f"Missing dependencies: {', '.join(missing_deps)}")
        print(f"   ❌ Missing: {', '.join(missing_deps)}")
    else:
        print("   ✅ All dependencies installed")
    
    # 2. Check if port 8080 is already in use
    print("\n2. Checking port 8080...")
    if check_port(8080):
        issues.append("Port 8080 is already in use")
        print("   ❌ Port 8080 is already in use")
        
        # Try to find what's using it
        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(['netstat', '-ano', '|', 'findstr', ':8080'], 
                                      capture_output=True, shell=True, text=True)
            else:  # Linux/Mac
                result = subprocess.run(['lsof', '-i', ':8080'], 
                                      capture_output=True, text=True)
            if result.stdout:
                print(f"   Process using port: {result.stdout.strip()}")
        except:
            pass
    else:
        print("   ✅ Port 8080 is available")
    
    # 3. Check if dashboard files exist
    print("\n3. Checking dashboard files...")
    required_files = [
        'api/dashboard_server.py',
        'api/dashboard_core.py',
        'api/dashboard_models.py',
        'api/dashboard_html.py'
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            issues.append(f"Missing file: {file}")
            print(f"   ❌ Missing: {file}")
        else:
            print(f"   ✅ Found: {file}")
    
    # 4. Check WebSocket support
    print("\n4. Checking WebSocket support...")
    try:
        import websockets
        print("   ✅ WebSocket support available")
    except:
        issues.append("WebSocket support not available")
        print("   ❌ WebSocket support not available")
    
    return issues


def fix_issues(issues):
    """Attempt to fix identified issues."""
    print("\n🔧 Attempting to fix issues...\n")
    
    # Fix missing dependencies
    if any("Missing dependencies" in issue for issue in issues):
        print("Installing missing dependencies...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 
                          'fastapi', 'uvicorn[standard]', 'websockets', 
                          'python-multipart'], check=True)
            print("✅ Dependencies installed")
        except:
            print("❌ Failed to install dependencies")
            print("   Please run: pip install fastapi uvicorn[standard] websockets python-multipart")
    
    # Fix port conflict
    if any("Port 8080 is already in use" in issue for issue in issues):
        print("\n⚠️  Port 8080 is in use. Options:")
        print("1. Kill the process using port 8080")
        print("2. Use a different port by setting DASHBOARD_PORT=8081")
        print("3. The dashboard might already be running!")
        
        # Check if it's our dashboard
        try:
            import requests
            response = requests.get('http://localhost:8080/api/stats', timeout=2)
            if response.status_code == 200:
                print("\n✅ Dashboard is already running at http://localhost:8080")
                return True
        except:
            pass


async def test_dashboard():
    """Test dashboard startup."""
    print("\n🧪 Testing dashboard startup...\n")
    
    try:
        from api.dashboard_server import app
        import uvicorn
        
        print("✅ Dashboard modules loaded successfully")
        print("\nTo start the dashboard manually, run:")
        print("  uvicorn api.dashboard_server:app --host 0.0.0.0 --port 8080")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to load dashboard: {e}")
        return False


def main():
    """Main diagnostic function."""
    print("=" * 70)
    print("🏥 DEX Sniping Bot - Dashboard Diagnostic")
    print("=" * 70)
    
    # Find issues
    issues = find_dashboard_issues()
    
    if not issues:
        print("\n✅ No issues found!")
        
        # Test dashboard
        if asyncio.run(test_dashboard()):
            print("\n🎉 Dashboard should be working!")
            print("\nAccess it at: http://localhost:8080")
            print("\nIf it's still not working, try:")
            print("1. Check the main application logs")
            print("2. Run the dashboard separately:")
            print("   python -m uvicorn api.dashboard_server:app --reload")
    else:
        print(f"\n❌ Found {len(issues)} issue(s):")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        
        # Try to fix
        fix_issues(issues)
        
        print("\n📝 Additional troubleshooting:")
        print("1. Check if main_production_enhanced.py is running without errors")
        print("2. Look for error messages in the console")
        print("3. Try running with: python main_production_enhanced.py --no-dashboard")
        print("   Then run dashboard separately: python -m uvicorn api.dashboard_server:app")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()