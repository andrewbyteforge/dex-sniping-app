#!/usr/bin/env python3
"""
Dashboard standalone runner with proper dependency checking.

This module provides functionality to run the dashboard server independently
without the main trading bot components.
"""

import sys
import os
import importlib.util
import subprocess
from typing import Tuple, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Raised when required dependencies are missing."""
    pass


class DashboardLoader:
    """Handles loading and running the dashboard module."""
    
    def __init__(self) -> None:
        """Initialize the dashboard loader."""
        self.required_packages = [
            'fastapi',
            'uvicorn',
            'websockets',
            'aiohttp'
        ]
    
    def check_dependencies(self) -> None:
        """
        Check if all required dependencies are installed.
        
        Raises:
            DependencyError: If any required package is missing.
        """
        missing_packages = []
        
        for package in self.required_packages:
            try:
                __import__(package)
                logger.info(f"✓ {package} is installed")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"✗ {package} is missing")
        
        if missing_packages:
            error_msg = (
                f"Missing required packages: {', '.join(missing_packages)}\n"
                f"Please install them using: pip install {' '.join(missing_packages)}"
            )
            raise DependencyError(error_msg)
    
    def load_dashboard_module(self) -> Tuple[Any, Any]:
        """
        Load the dashboard module dynamically.
        
        Returns:
            Tuple[Any, Any]: The FastAPI app and dashboard server instance.
            
        Raises:
            ImportError: If the dashboard module cannot be loaded.
            FileNotFoundError: If the dashboard file doesn't exist.
        """
        dashboard_path = os.path.join("api", "dashboard_server.py")
        
        if not os.path.exists(dashboard_path):
            raise FileNotFoundError(f"Dashboard file not found: {dashboard_path}")
        
        try:
            # Load the dashboard module
            spec = importlib.util.spec_from_file_location("dashboard_server", dashboard_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec from {dashboard_path}")
            
            dashboard_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dashboard_module)
            
            # Get the app and server instances
            app = getattr(dashboard_module, 'app', None)
            dashboard_server = getattr(dashboard_module, 'dashboard_server', None)
            
            if app is None:
                raise ImportError("No 'app' object found in dashboard module")
            if dashboard_server is None:
                raise ImportError("No 'dashboard_server' object found in dashboard module")
            
            logger.info("Dashboard module loaded successfully")
            return app, dashboard_server
            
        except Exception as e:
            logger.error(f"Failed to load dashboard module: {e}")
            raise ImportError(f"Failed to load dashboard module: {e}")
    
    def install_missing_dependencies(self) -> bool:
        """
        Attempt to install missing dependencies automatically.
        
        Returns:
            bool: True if installation was successful, False otherwise.
        """
        try:
            logger.info("Attempting to install missing dependencies...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "fastapi", "uvicorn[standard]", "websockets", "aiohttp"
            ])
            logger.info("Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False


def main() -> None:
    """
    Main function to run the dashboard in standalone mode.
    
    This function handles dependency checking, module loading, and server startup
    with comprehensive error handling.
    """
    try:
        print("Starting Dashboard Server (Standalone Mode)")
        print("Dashboard will be available at: http://localhost:8000")
        print("Press Ctrl+C to stop")
        
        # Initialize the dashboard loader
        loader = DashboardLoader()
        
        # Check dependencies first
        try:
            loader.check_dependencies()
        except DependencyError as e:
            logger.error(f"Dependency check failed: {e}")
            
            # Ask user if they want to auto-install
            user_input = input("Would you like to install missing dependencies automatically? (y/n): ")
            if user_input.lower() in ['y', 'yes']:
                if loader.install_missing_dependencies():
                    # Re-check dependencies after installation
                    loader.check_dependencies()
                else:
                    logger.error("Failed to install dependencies automatically")
                    sys.exit(1)
            else:
                logger.error("Please install the missing dependencies manually")
                sys.exit(1)
        
        # Load the dashboard module
        app, dashboard_server = loader.load_dashboard_module()
        
        # Import uvicorn here after dependency check
        import uvicorn
        
        # Run the server
        logger.info("Starting dashboard server...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
        print("\nDashboard server stopped")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"Error: {e}")
        sys.exit(1)
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        print(f"Dashboard error: {e}")
        sys.exit(1)
        
    except DependencyError as e:
        logger.error(f"Dependency error: {e}")
        print(f"Dependency error: {e}")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()