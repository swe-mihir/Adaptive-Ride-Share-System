"""
Startup script for the Adaptive Ride-Sharing webapp.
Runs WebSocket server and opens browser.
"""

import sys
import webbrowser
import time
from pathlib import Path

def main():
    print("=" * 60)
    print("🚗 Adaptive Ride-Sharing System")
    print("=" * 60)
    
    # Check if frontend files exist
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("\n⚠️  Frontend directory not found!")
        print("Creating frontend structure...")
        frontend_dir.mkdir(exist_ok=True)
        
        # Create index.html
        index_path = frontend_dir / "index.html"
        if not index_path.exists():
            print("❌ Please create frontend/index.html from the artifact!")
            return
        
        # Create app.jsx
        app_path = frontend_dir / "app.jsx"
        if not app_path.exists():
            print("❌ Please create frontend/app.jsx from the artifact!")
            return
    
    print("\n✓ Frontend files found")
    
    # Start WebSocket server
    print("\n🚀 Starting WebSocket server on port 5001...")
    print("   Backend API: http://localhost:5001/api/")
    print("   WebSocket: ws://localhost:5001")
    
    # Import and start server
    try:
        from server import start_server
        
        print("\n✓ Server starting...")
        print("\n📊 Open your browser to:")
        print("   http://localhost:8000")
        print("\n💡 You'll need to serve the frontend files.")
        print("   Run in another terminal:")
        print("   cd frontend && python -m http.server 8000")
        print("\n⏹️  Press Ctrl+C to stop\n")
        
        # Open browser after delay
        time.sleep(2)
        webbrowser.open('http://localhost:8000')
        
        # Start server (blocking)
        start_server(port=5001)
        
    except ImportError as e:
        print(f"\n❌ Error importing server: {e}")
        print("   Make sure server.py exists!")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped")
        sys.exit(0)

if __name__ == "__main__":
    main()
