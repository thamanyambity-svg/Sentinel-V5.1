#!/usr/bin/env python3
"""
SENTINEL V11 — Start API Server (Cross-Platform)
Usage: python start_api.py [--debug] [--port 5000]
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Start Sentinel V11 API Server")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on (default: 5000)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip validation tests")
    args = parser.parse_args()
    
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    print("\n" + "="*60)
    print("  SENTINEL V11 - API SERVER LAUNCHER")
    print("="*60 + "\n")
    
    # Check virtual environment
    venv_dir = project_dir / ".venv"
    if not venv_dir.exists():
        print("❌ Virtual environment not found!")
        print("   Create it with: python3 -m venv .venv")
        sys.exit(1)
    
    print("✓ Virtual environment found")
    
    # Run tests unless skipped
    if not args.skip_tests:
        print("\n✓ Running installation tests...\n")
        result = subprocess.run(
            [sys.executable, "test_install.py", "--api"],
            cwd=project_dir
        )
        if result.returncode != 0:
            print("\n❌ Tests failed! Please fix issues before continuing.")
            sys.exit(1)
    
    # Start the server
    print("\n" + "="*60)
    print("  🚀 STARTING API SERVER")
    print("="*60)
    print(f"\n  🌐 API Server:  http://localhost:{args.port}")
    print(f"  📊 Dashboard:   http://localhost:{args.port}/")
    print(f"  📡 Health:      http://localhost:{args.port}/api/v1/health")
    print("\n  Press Ctrl+C to stop\n")
    print("="*60 + "\n")
    
    # Set environment variables
    os.environ["FLASK_APP"] = "api_server.py"
    if args.debug:
        os.environ["FLASK_ENV"] = "development"
    else:
        os.environ["FLASK_ENV"] = "production"
    
    # Import and run Flask app
    try:
        from api_server import app
        app.run(
            host="0.0.0.0",
            port=args.port,
            debug=args.debug,
            use_reloader=args.debug
        )
    except ImportError as e:
        print(f"❌ Failed to import api_server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
