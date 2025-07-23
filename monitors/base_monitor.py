# monitors/base_monitor.py
"""
Base class for all monitoring components.
Provides common functionality and error handling patterns.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Callable, Any
import traceback

class BaseMonitor(ABC):
    """
    Abstract base class for all monitoring components.
    Provides common functionality like error handling, retry logic, and logging.
    """
    
    def __init__(self, name: str, check_interval: float = 1.0):
        """
        Initialize the base monitor.
        
        Args:
            name: Name of the monitor for logging
            check_interval: Seconds between checks
        """
        self.name = name
        self.check_interval = check_interval
        self.logger = logging.getLogger(f"monitor.{name}")
        self.is_running = False
        self.error_count = 0
        self.max_errors = 10
        self.last_check: Optional[datetime] = None
        self.callbacks: list[Callable] = []
        
    def add_callback(self, callback: Callable) -> None:
        """Add a callback function to be called when opportunities are found."""
        self.callbacks.append(callback)
        self.logger.info(f"Added callback: {callback.__name__}")
        
    async def start(self) -> None:
        """Start the monitoring process."""
        if self.is_running:
            self.logger.warning(f"{self.name} monitor is already running")
            return
            
        self.logger.info(f"Starting {self.name} monitor")
        self.is_running = True
        self.error_count = 0
        
        try:
            await self._initialize()
            await self._run_monitoring_loop()
        except Exception as e:
            self.logger.error(f"Fatal error in {self.name} monitor: {e}")
            self.logger.debug(traceback.format_exc())
        finally:
            self.is_running = False
            await self._cleanup()
            self.logger.info(f"{self.name} monitor stopped")
    
    def stop(self) -> None:
        """Stop the monitoring process."""
        self.logger.info(f"Stopping {self.name} monitor")
        self.is_running = False
        
    async def _run_monitoring_loop(self) -> None:
        """Main monitoring loop with error handling."""
        while self.is_running:
            try:
                start_time = datetime.now()
                
                # Perform the actual monitoring check
                await self._check()
                
                self.last_check = datetime.now()
                self.error_count = 0  # Reset error count on successful check
                
                # Calculate how long to sleep
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, self.check_interval - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
            except asyncio.CancelledError:
                self.logger.info(f"{self.name} monitor cancelled")
                break
            except Exception as e:
                await self._handle_error(e)
                
    async def _handle_error(self, error: Exception) -> None:
        """Handle errors during monitoring."""
        self.error_count += 1
        self.logger.error(
            f"Error in {self.name} monitor (#{self.error_count}): {error}"
        )
        self.logger.debug(traceback.format_exc())
        
        if self.error_count >= self.max_errors:
            self.logger.critical(
                f"{self.name} monitor exceeded max errors ({self.max_errors}). Stopping."
            )
            self.is_running = False
            return
            
        # Exponential backoff for retries
        sleep_time = min(60, 2 ** self.error_count)
        self.logger.info(f"Retrying in {sleep_time} seconds...")
        await asyncio.sleep(sleep_time)
        
    async def _notify_callbacks(self, data: Any) -> None:
        """Notify all registered callbacks with new data."""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in callback {callback.__name__}: {e}")
                
    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize the monitor. Override in subclasses."""
        pass
        
    @abstractmethod
    async def _check(self) -> None:
        """Perform monitoring check. Override in subclasses."""
        pass
        
    @abstractmethod
    async def _cleanup(self) -> None:
        """Cleanup resources. Override in subclasses."""
        pass
        
    def get_status(self) -> dict:
        """Get current status of the monitor."""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'error_count': self.error_count,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'check_interval': self.check_interval
        }
