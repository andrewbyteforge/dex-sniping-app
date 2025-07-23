#!/usr/bin/env python3
"""
Simple starter that runs both bot and dashboard properly.
"""

import subprocess
import sys
import time
import os
import signal


def cleanup_ports():
    """Clean up any processes using our ports."""
    print("Cleaning up old processes...")
    
    # Check port 8080
    result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if ':8080' in line and 'LISTENING' in line:
            parts = line.split()
            if parts:
                pid = parts[-1]
                try:
                    subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
                    print(f"Killed process {pid} on port 8080")
                except:
                    pass
    
    time.sleep(1)


def main():
    print("=" * 70)
    print("DEX Sniping Bot - Complete System Starter")
    print("=" * 70)
    
    # Clean up first
    cleanup_ports()
    
    processes = []
    
    try:
        # Start dashboard first
        print("\nStarting Dashboard...")
        dashboard_cmd = [sys.executable, "run_dashboard_only.py"]
        dashboard_process = subprocess.Popen(
            dashboard_cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        processes.append(dashboard_process)
        
        # Wait for dashboard to start
        print("Waiting for dashboard to initialize...")
        time.sleep(5)
        
        # Start main bot without dashboard
        print("\nStarting Bot (without integrated dashboard)...")
        bot_cmd = [sys.executable, "main_production_enhanced.py", "--no-dashboard"]
        bot_process = subprocess.Popen(
            bot_cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        processes.append(bot_process)
        
        print("\n" + "=" * 70)
        print("SYSTEM STARTED SUCCESSFULLY!")
        print("=" * 70)
        print("\nDashboard: http://localhost:8080")
        print("\nYou should see two console windows:")
        print("1. Dashboard server")
        print("2. Main bot system")
        print("\nPress Ctrl+C here to stop everything")
        print("=" * 70)
        
        # Keep running
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if dashboard_process.poll() is not None:
                print("\nWARNING: Dashboard stopped unexpectedly!")
                break
            if bot_process.poll() is not None:
                print("\nWARNING: Bot stopped unexpectedly!")
                break
                
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        
        # Terminate all processes
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except:
                p.kill()
        
        print("Shutdown complete!")
        
    except Exception as e:
        print(f"\nError: {e}")
        # Clean up on error
        for p in processes:
            try:
                p.kill()
            except:
                pass


if __name__ == "__main__":
    main()