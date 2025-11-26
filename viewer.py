"""
Web viewer server for viewing saved game runs.
Run this separately from main.py to view games in the browser.
"""

import argparse
from src.web.viewer_server import ViewerServer


def main():
    """Entry point for the viewer server."""
    parser = argparse.ArgumentParser(
        description="Start web viewer server for viewing saved game runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python viewer.py                    # Start server on default port 5000
  python viewer.py --port 8080       # Start server on port 8080
  python viewer.py --runs-dir custom_runs  # Use custom runs directory
        """
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=5000,
        help="Port for web server (default: 5000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default='127.0.0.1',
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--runs-dir",
        type=str,
        default="runs",
        help="Directory containing game runs (default: runs)"
    )
    
    args = parser.parse_args()
    
    server = ViewerServer(port=args.port, host=args.host, runs_dir=args.runs_dir)
    server.start()


if __name__ == "__main__":
    main()

