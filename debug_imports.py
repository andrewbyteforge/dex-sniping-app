"""
Debug script to identify import issues.
"""

import sys
import os
import traceback

def test_imports():
    """Test various import scenarios."""
    print("🔍 DEBUGGING IMPORT ISSUES")
    print("=" * 50)
    
    # Test 1: Basic FastAPI
    try:
        import fastapi
        print("✅ FastAPI imported successfully")
    except Exception as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
    
    # Test 2: Direct dashboard module import
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Try importing the dashboard module directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "dashboard_server", 
            "api/dashboard_server.py"
        )
        dashboard_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dashboard_module)
        print("✅ Dashboard module loaded directly")
        
        # Check what's available
        if hasattr(dashboard_module, 'app'):
            print("✅ FastAPI app found")
        else:
            print("❌ FastAPI app not found in module")
            
        if hasattr(dashboard_module, 'dashboard_server'):
            print("✅ Dashboard server instance found")
        else:
            print("❌ Dashboard server instance not found")
            
    except Exception as e:
        print(f"❌ Direct dashboard import failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 3: API package import
    try:
        from api import dashboard_server
        print("✅ API package import successful")
    except Exception as e:
        print(f"❌ API package import failed: {e}")
        print("This is expected with the current issue")
    
    # Test 4: Check file existence
    files_to_check = [
        "api/__init__.py",
        "api/dashboard_server.py"
    ]
    
    print("\nFile existence check:")
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
            # Show first few lines
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()[:5]
                    print(f"   First lines: {[line.strip() for line in lines]}")
            except:
                pass
        else:
            print(f"❌ {file_path} missing")
    
    return True

if __name__ == "__main__":
    test_imports()