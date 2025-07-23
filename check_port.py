"""
Check if port 8000 is available.
"""

import socket
import subprocess
import sys

def check_port(port=8000):
    """Check if a port is available."""
    print(f"🔍 Checking port {port}")
    
    try:
        # Try to bind to the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            print(f"❌ Port {port} is in use")
            
            # Try to find what's using it (Windows)
            try:
                result = subprocess.run(
                    ['netstat', '-ano'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        print(f"   Process using port: {line.strip()}")
                        
            except:
                print("   Could not identify process using port")
                
            return False
        else:
            print(f"✅ Port {port} is available")
            return True
            
    except Exception as e:
        print(f"❌ Error checking port: {e}")
        return False

def find_available_port(start_port=8000, end_port=8010):
    """Find an available port in range."""
    for port in range(start_port, end_port):
        if check_port(port):
            return port
    return None

if __name__ == "__main__":
    print("🔧 PORT AVAILABILITY CHECK")
    print("=" * 30)
    
    available_port = find_available_port()
    
    if available_port:
        print(f"\n✅ Recommended port: {available_port}")
    else:
        print(f"\n❌ No available ports found in range 8000-8010")