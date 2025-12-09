#!/usr/bin/env python3
"""
Quick fix script to restart the application with better WebSocket handling
"""
import os
import signal
import subprocess
import time

def kill_existing():
    """Kill existing uvicorn processes"""
    try:
        subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
        print("✅ Killed existing uvicorn processes")
    except:
        pass
    time.sleep(2)

def restart_app():
    """Restart the application"""
    print("🔄 Restarting application with improved WebSocket handling...")
    
    # Set environment variables for better WebSocket handling
    env = os.environ.copy()
    env.update({
        "PYTHONUNBUFFERED": "1",
        "XRPL_WSS": "wss://s1.ripple.com",  # Use main server
        "WEBSOCKET_PING_INTERVAL": "30",
        "WEBSOCKET_PING_TIMEOUT": "10",
        "WEBSOCKET_CLOSE_TIMEOUT": "5",
    })
    
    # Start the application
    process = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    print("✅ Application restarted")
    print("📊 Monitoring output...\n")
    
    try:
        # Stream output
        for line in process.stdout:
            print(line, end='')
            
            # Check for critical errors
            if "CRITICAL: Ledger drift" in line:
                print("\n⚠️ Ledger drift detected - WebSocket may be unstable")
            elif "Websocket is not open" in line:
                print("\n🔴 WebSocket connection lost - consider restarting")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping application...")
        process.send_signal(signal.SIGTERM)
        process.wait()
        print("✅ Application stopped")

if __name__ == "__main__":
    kill_existing()
    restart_app()
