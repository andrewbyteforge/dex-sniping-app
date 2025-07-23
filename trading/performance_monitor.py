"""
Performance monitoring and optimization for trading execution.
Tracks latencies, identifies bottlenecks, and provides optimization recommendations.
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, median, stdev
import json

from utils.logger import logger_manager


@dataclass
class PerformanceMetric:
    """
    Performance metric for a specific operation.
    
    Attributes:
        operation: Name of the operation
        start_time: Start timestamp
        end_time: End timestamp
        duration_ms: Duration in milliseconds
        success: Whether operation succeeded
        metadata: Additional metric data
    """
    operation: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    """
    Performance analysis report.
    
    Attributes:
        period_start: Report period start
        period_end: Report period end
        total_operations: Total operations tracked
        average_latency: Average operation latency
        p50_latency: 50th percentile latency
        p95_latency: 95th percentile latency
        p99_latency: 99th percentile latency
        bottlenecks: Identified bottlenecks
        recommendations: Performance recommendations
    """
    period_start: datetime
    period_end: datetime
    total_operations: int
    average_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    bottlenecks: List[str]
    recommendations: List[str]
    operation_breakdown: Dict[str, Dict[str, float]]


class PerformanceMonitor:
    """
    Monitors and optimizes trading system performance.
    """
    
    # Target latencies in milliseconds
    TARGET_LATENCIES = {
        'token_detection': 1000,      # 1 second
        'contract_analysis': 3000,    # 3 seconds
        'risk_assessment': 500,       # 0.5 seconds
        'trade_execution': 2000,      # 2 seconds
        'gas_estimation': 200,        # 0.2 seconds
        'dex_quote': 300,            # 0.3 seconds
        'total_pipeline': 5000        # 5 seconds total
    }
    
    def __init__(self):
        """Initialize the performance monitor."""
        self.logger = logger_manager.get_logger("PerformanceMonitor")
        
        # Metric storage
        self.metrics: List[PerformanceMetric] = []
        self.operation_timers: Dict[str, float] = {}
        
        # Performance tracking
        self.operation_counts: Dict[str, int] = {}
        self.operation_times: Dict[str, List[float]] = {}
        self.operation_errors: Dict[str, int] = {}
        
        # Optimization tracking
        self.optimization_enabled = True
        self.parallel_operations = set()
        self.cached_operations = set()
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.report_interval = 300  # 5 minutes
        
    async def initialize(self) -> None:
        """Initialize the performance monitor."""
        try:
            self.logger.info("Initializing Performance Monitor...")
            
            # Start monitoring task
            self.monitoring_task = asyncio.create_task(
                self._monitor_performance()
            )
            
            self.logger.info("✅ Performance Monitor initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise
    
    def start_operation(self, operation: str, metadata: Dict[str, Any] = None) -> str:
        """
        Start tracking an operation.
        
        Args:
            operation: Operation name
            metadata: Additional metadata
            
        Returns:
            Operation ID for tracking
        """
        operation_id = f"{operation}_{time.time()}"
        self.operation_timers[operation_id] = time.time()
        
        return operation_id
    
    def end_operation(
        self,
        operation_id: str,
        success: bool = True,
        metadata: Dict[str, Any] = None
    ) -> float:
        """
        End tracking an operation.
        
        Args:
            operation_id: Operation ID from start_operation
            success: Whether operation succeeded
            metadata: Additional metadata
            
        Returns:
            Operation duration in milliseconds
        """
        if operation_id not in self.operation_timers:
            return 0.0
        
        start_time = self.operation_timers[operation_id]
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Extract operation name
        operation = operation_id.split('_')[0]
        
        # Create metric
        metric = PerformanceMetric(
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {}
        )
        
        self.metrics.append(metric)
        
        # Update tracking
        if operation not in self.operation_counts:
            self.operation_counts[operation] = 0
            self.operation_times[operation] = []
            self.operation_errors[operation] = 0
        
        self.operation_counts[operation] += 1
        self.operation_times[operation].append(duration_ms)
        
        if not success:
            self.operation_errors[operation] += 1
        
        # Clean up timer
        del self.operation_timers[operation_id]
        
        # Check if exceeds target
        if operation in self.TARGET_LATENCIES:
            if duration_ms > self.TARGET_LATENCIES[operation]:
                self.logger.warning(
                    f"⚠️ {operation} exceeded target latency: "
                    f"{duration_ms:.1f}ms > {self.TARGET_LATENCIES[operation]}ms"
                )
        
        return duration_ms
    
    async def measure_async(
        self,
        operation: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, float]:
        """
        Measure async function performance.
        
        Args:
            operation: Operation name
            func: Async function to measure
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Tuple of (result, duration_ms)
        """
        op_id = self.start_operation(operation)
        
        try:
            result = await func(*args, **kwargs)
            duration = self.end_operation(op_id, success=True)
            return result, duration
            
        except Exception as e:
            duration = self.end_operation(op_id, success=False)
            raise e
    
    def get_operation_stats(self, operation: str) -> Dict[str, float]:
        """
        Get statistics for a specific operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Dictionary of statistics
        """
        if operation not in self.operation_times:
            return {}
        
        times = self.operation_times[operation]
        if not times:
            return {}
        
        return {
            'count': self.operation_counts[operation],
            'errors': self.operation_errors[operation],
            'error_rate': self.operation_errors[operation] / self.operation_counts[operation],
            'min': min(times),
            'max': max(times),
            'mean': mean(times),
            'median': median(times),
            'stdev': stdev(times) if len(times) > 1 else 0,
            'p95': self._percentile(times, 95),
            'p99': self._percentile(times, 99)
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def generate_report(
        self,
        period_minutes: int = 60
    ) -> PerformanceReport:
        """
        Generate performance report.
        
        Args:
            period_minutes: Report period in minutes
            
        Returns:
            Performance report
        """
        now = datetime.now()
        period_start = now - timedelta(minutes=period_minutes)
        
        # Filter metrics for period
        period_metrics = [
            m for m in self.metrics
            if m.start_time >= period_start.timestamp()
        ]
        
        if not period_metrics:
            return PerformanceReport(
                period_start=period_start,
                period_end=now,
                total_operations=0,
                average_latency=0,
                p50_latency=0,
                p95_latency=0,
                p99_latency=0,
                bottlenecks=[],
                recommendations=[],
                operation_breakdown={}
            )
        
        # Calculate overall latencies
        all_latencies = [m.duration_ms for m in period_metrics]
        
        # Operation breakdown
        operation_breakdown = {}
        for op in self.operation_counts:
            stats = self.get_operation_stats(op)
            if stats:
                operation_breakdown[op] = stats
        
        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(operation_breakdown)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            operation_breakdown, bottlenecks
        )
        
        return PerformanceReport(
            period_start=period_start,
            period_end=now,
            total_operations=len(period_metrics),
            average_latency=mean(all_latencies),
            p50_latency=self._percentile(all_latencies, 50),
            p95_latency=self._percentile(all_latencies, 95),
            p99_latency=self._percentile(all_latencies, 99),
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            operation_breakdown=operation_breakdown
        )
    
    def _identify_bottlenecks(
        self,
        operation_breakdown: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """Identify performance bottlenecks."""
        bottlenecks = []
        
        for operation, stats in operation_breakdown.items():
            # Check against targets
            if operation in self.TARGET_LATENCIES:
                if stats['mean'] > self.TARGET_LATENCIES[operation]:
                    bottlenecks.append(
                        f"{operation}: {stats['mean']:.1f}ms average "
                        f"(target: {self.TARGET_LATENCIES[operation]}ms)"
                    )
            
            # High error rate
            if stats['error_rate'] > 0.1:
                bottlenecks.append(
                    f"{operation}: {stats['error_rate']*100:.1f}% error rate"
                )
            
            # High variance
            if stats['stdev'] > stats['mean'] * 0.5:
                bottlenecks.append(
                    f"{operation}: High variance (stdev: {stats['stdev']:.1f}ms)"
                )
        
        return bottlenecks
    
    def _generate_recommendations(
        self,
        operation_breakdown: Dict[str, Dict[str, float]],
        bottlenecks: List[str]
    ) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        # Check specific operations
        if 'token_detection' in operation_breakdown:
            stats = operation_breakdown['token_detection']
            if stats['mean'] > 2000:
                recommendations.append(
                    "Token detection is slow - consider using WebSocket connections"
                )
        
        if 'contract_analysis' in operation_breakdown:
            stats = operation_breakdown['contract_analysis']
            if stats['mean'] > 5000:
                recommendations.append(
                    "Contract analysis is slow - implement caching for known contracts"
                )
        
        if 'trade_execution' in operation_breakdown:
            stats = operation_breakdown['trade_execution']
            if stats['p99'] > 5000:
                recommendations.append(
                    "Trade execution has high tail latency - use direct nodes"
                )
        
        # General recommendations
        if len(bottlenecks) > 3:
            recommendations.append(
                "Multiple bottlenecks detected - consider horizontal scaling"
            )
        
        # Check for operations that could be parallelized
        sequential_ops = self._find_sequential_operations()
        if sequential_ops:
            recommendations.append(
                f"Parallelize operations: {', '.join(sequential_ops)}"
            )
        
        return recommendations
    
    def _find_sequential_operations(self) -> List[str]:
        """Find operations that could be parallelized."""
        # Analyze metric sequences to find operations that always run sequentially
        # but could potentially run in parallel
        
        parallelizable = []
        
        # Known parallelizable operations
        if ('contract_analysis' in self.operation_counts and
            'social_analysis' in self.operation_counts):
            parallelizable.append("contract_analysis + social_analysis")
        
        return parallelizable
    
    async def _monitor_performance(self) -> None:
        """Background performance monitoring task."""
        while True:
            try:
                # Generate periodic report
                report = self.generate_report(period_minutes=5)
                
                if report.total_operations > 0:
                    self.logger.info(
                        f"📊 Performance Report: "
                        f"Ops: {report.total_operations}, "
                        f"Avg: {report.average_latency:.1f}ms, "
                        f"P95: {report.p95_latency:.1f}ms"
                    )
                    
                    if report.bottlenecks:
                        self.logger.warning(
                            f"🚨 Bottlenecks: {'; '.join(report.bottlenecks)}"
                        )
                    
                    if report.recommendations:
                        self.logger.info(
                            f"💡 Recommendations: {'; '.join(report.recommendations)}"
                        )
                
                # Clean old metrics
                self._clean_old_metrics()
                
                await asyncio.sleep(self.report_interval)
                
            except Exception as e:
                self.logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(60)
    
    def _clean_old_metrics(self) -> None:
        """Remove old metrics to prevent memory growth."""
        cutoff_time = time.time() - 3600  # Keep 1 hour
        
        self.metrics = [
            m for m in self.metrics
            if m.start_time > cutoff_time
        ]
    
    def enable_optimization(self, operation: str, optimization_type: str) -> None:
        """
        Enable optimization for an operation.
        
        Args:
            operation: Operation to optimize
            optimization_type: Type of optimization ('parallel', 'cache')
        """
        if optimization_type == 'parallel':
            self.parallel_operations.add(operation)
            self.logger.info(f"Enabled parallel execution for {operation}")
        elif optimization_type == 'cache':
            self.cached_operations.add(operation)
            self.logger.info(f"Enabled caching for {operation}")
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """
        Get current optimization status.
        
        Returns:
            Dictionary of optimization settings
        """
        return {
            'optimization_enabled': self.optimization_enabled,
            'parallel_operations': list(self.parallel_operations),
            'cached_operations': list(self.cached_operations),
            'active_timers': len(self.operation_timers),
            'metrics_collected': len(self.metrics)
        }
    
    async def shutdown(self) -> None:
        """Shutdown the performance monitor."""
        self.logger.info("Shutting down Performance Monitor...")
        
        # Final report
        report = self.generate_report()
        self.logger.info(
            f"Final report: {report.total_operations} operations, "
            f"avg latency: {report.average_latency:.1f}ms"
        )
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        self.logger.info("Performance Monitor shutdown complete")