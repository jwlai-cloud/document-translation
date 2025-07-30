"""Performance monitoring and alerting system."""

import time
import threading
import psutil
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json
import statistics


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    timestamp: float = field(default_factory=time.time)
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_usage_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_io_sent_mb: float = 0.0
    network_io_recv_mb: float = 0.0
    active_threads: int = 0
    processing_jobs: int = 0
    queue_length: int = 0
    response_time_ms: float = 0.0
    throughput_per_sec: float = 0.0
    error_rate_percent: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'timestamp': self.timestamp,
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mb': self.memory_usage_mb,
            'memory_usage_percent': self.memory_usage_percent,
            'disk_io_read_mb': self.disk_io_read_mb,
            'disk_io_write_mb': self.disk_io_write_mb,
            'network_io_sent_mb': self.network_io_sent_mb,
            'network_io_recv_mb': self.network_io_recv_mb,
            'active_threads': self.active_threads,
            'processing_jobs': self.processing_jobs,
            'queue_length': self.queue_length,
            'response_time_ms': self.response_time_ms,
            'throughput_per_sec': self.throughput_per_sec,
            'error_rate_percent': self.error_rate_percent
        }


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    duration_seconds: int = 60  # How long threshold must be exceeded
    enabled: bool = True


@dataclass
class Alert:
    """Performance alert."""
    alert_id: str
    metric_name: str
    level: str  # 'warning' or 'critical'
    current_value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False
    resolved: bool = False


class PerformanceMonitor:
    """Comprehensive performance monitoring system."""
    
    def __init__(self, collection_interval: int = 5, history_size: int = 1000):
        """Initialize performance monitor.
        
        Args:
            collection_interval: Metrics collection interval in seconds
            history_size: Number of metrics to keep in history
        """
        self.collection_interval = collection_interval
        self.history_size = history_size
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self.metrics_history: deque[PerformanceMetrics] = deque(maxlen=history_size)
        self.current_metrics = PerformanceMetrics()
        
        # Alert system
        self.alert_thresholds: Dict[str, AlertThreshold] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        
        # Monitoring state
        self._monitoring_thread = None
        self._shutdown_event = threading.Event()
        self._metrics_lock = threading.RLock()
        
        # Performance tracking
        self._request_times: deque[float] = deque(maxlen=1000)
        self._error_count = 0
        self._total_requests = 0
        self._last_io_stats = None
        
        # Setup default thresholds
        self._setup_default_thresholds()
        
        # Start monitoring
        self.start_monitoring()
    
    def _setup_default_thresholds(self):
        """Setup default alert thresholds."""
        self.alert_thresholds = {
            'cpu_usage_percent': AlertThreshold(
                metric_name='cpu_usage_percent',
                warning_threshold=70.0,
                critical_threshold=90.0,
                duration_seconds=60
            ),
            'memory_usage_percent': AlertThreshold(
                metric_name='memory_usage_percent',
                warning_threshold=80.0,
                critical_threshold=95.0,
                duration_seconds=30
            ),
            'response_time_ms': AlertThreshold(
                metric_name='response_time_ms',
                warning_threshold=5000.0,  # 5 seconds
                critical_threshold=10000.0,  # 10 seconds
                duration_seconds=120
            ),
            'error_rate_percent': AlertThreshold(
                metric_name='error_rate_percent',
                warning_threshold=5.0,
                critical_threshold=10.0,
                duration_seconds=300
            ),
            'queue_length': AlertThreshold(
                metric_name='queue_length',
                warning_threshold=50.0,
                critical_threshold=100.0,
                duration_seconds=180
            )
        }
    
    def start_monitoring(self):
        """Start performance monitoring."""
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._shutdown_event.clear()
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="performance_monitor"
            )
            self._monitoring_thread.start()
            self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self._shutdown_event.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10.0)
        self.logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self._shutdown_event.is_set():
            try:
                # Collect metrics
                metrics = self._collect_metrics()
                
                with self._metrics_lock:
                    self.current_metrics = metrics
                    self.metrics_history.append(metrics)
                
                # Check for alerts
                self._check_alerts(metrics)
                
                # Sleep until next collection
                self._shutdown_event.wait(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        metrics = PerformanceMetrics()
        
        try:
            # CPU metrics
            metrics.cpu_usage_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.memory_usage_mb = (memory.total - memory.available) / 1024 / 1024
            metrics.memory_usage_percent = memory.percent
            
            # Disk I/O metrics
            disk_io = psutil.disk_io_counters()
            if disk_io and self._last_io_stats:
                read_diff = disk_io.read_bytes - self._last_io_stats.read_bytes
                write_diff = disk_io.write_bytes - self._last_io_stats.write_bytes
                metrics.disk_io_read_mb = read_diff / 1024 / 1024
                metrics.disk_io_write_mb = write_diff / 1024 / 1024
            
            if disk_io:
                self._last_io_stats = disk_io
            
            # Network I/O metrics
            try:
                network_io = psutil.net_io_counters()
                if network_io:
                    metrics.network_io_sent_mb = network_io.bytes_sent / 1024 / 1024
                    metrics.network_io_recv_mb = network_io.bytes_recv / 1024 / 1024
            except Exception:
                pass  # Network stats might not be available
            
            # Thread metrics
            metrics.active_threads = threading.active_count()
            
            # Application-specific metrics
            metrics.response_time_ms = self._calculate_avg_response_time()
            metrics.throughput_per_sec = self._calculate_throughput()
            metrics.error_rate_percent = self._calculate_error_rate()
            
        except Exception as e:
            self.logger.error(f"Metrics collection error: {e}")
        
        return metrics
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time."""
        if not self._request_times:
            return 0.0
        
        # Calculate average of recent requests
        recent_times = list(self._request_times)[-100:]  # Last 100 requests
        return statistics.mean(recent_times) * 1000  # Convert to milliseconds
    
    def _calculate_throughput(self) -> float:
        """Calculate requests per second throughput."""
        if len(self.metrics_history) < 2:
            return 0.0
        
        # Calculate throughput over last minute
        current_time = time.time()
        minute_ago = current_time - 60
        
        recent_metrics = [m for m in self.metrics_history if m.timestamp > minute_ago]
        if len(recent_metrics) < 2:
            return 0.0
        
        time_span = recent_metrics[-1].timestamp - recent_metrics[0].timestamp
        if time_span <= 0:
            return 0.0
        
        # Estimate requests based on response times recorded
        request_count = len([t for t in self._request_times if current_time - 60 <= t <= current_time])
        return request_count / time_span if time_span > 0 else 0.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self._total_requests == 0:
            return 0.0
        
        return (self._error_count / self._total_requests) * 100
    
    def record_request(self, response_time: float, success: bool = True):
        """Record a request for performance tracking.
        
        Args:
            response_time: Request response time in seconds
            success: Whether the request was successful
        """
        current_time = time.time()
        self._request_times.append(current_time)
        self._total_requests += 1
        
        if not success:
            self._error_count += 1
    
    def update_job_metrics(self, processing_jobs: int, queue_length: int):
        """Update job-related metrics.
        
        Args:
            processing_jobs: Number of currently processing jobs
            queue_length: Length of job queue
        """
        with self._metrics_lock:
            self.current_metrics.processing_jobs = processing_jobs
            self.current_metrics.queue_length = queue_length
    
    def _check_alerts(self, metrics: PerformanceMetrics):
        """Check metrics against alert thresholds."""
        current_time = time.time()
        
        for threshold_name, threshold in self.alert_thresholds.items():
            if not threshold.enabled:
                continue
            
            # Get metric value
            metric_value = getattr(metrics, threshold_name, 0.0)
            
            # Check thresholds
            alert_level = None
            alert_threshold = None
            
            if metric_value >= threshold.critical_threshold:
                alert_level = 'critical'
                alert_threshold = threshold.critical_threshold
            elif metric_value >= threshold.warning_threshold:
                alert_level = 'warning'
                alert_threshold = threshold.warning_threshold
            
            if alert_level:
                # Check if we need to create or update alert
                alert_key = f"{threshold_name}_{alert_level}"
                
                if alert_key not in self.active_alerts:
                    # Create new alert
                    alert = Alert(
                        alert_id=f"{alert_key}_{int(current_time)}",
                        metric_name=threshold_name,
                        level=alert_level,
                        current_value=metric_value,
                        threshold=alert_threshold,
                        message=f"{threshold_name} is {metric_value:.2f}, exceeding {alert_level} threshold of {alert_threshold:.2f}",
                        timestamp=current_time
                    )
                    
                    self.active_alerts[alert_key] = alert
                    self.alert_history.append(alert)
                    
                    # Notify callbacks
                    self._notify_alert_callbacks(alert)
                    
                    self.logger.warning(f"Performance alert: {alert.message}")
                
                else:
                    # Update existing alert
                    existing_alert = self.active_alerts[alert_key]
                    existing_alert.current_value = metric_value
                    existing_alert.timestamp = current_time
            
            else:
                # Check if we can resolve existing alerts
                for level in ['warning', 'critical']:
                    alert_key = f"{threshold_name}_{level}"
                    if alert_key in self.active_alerts:
                        alert = self.active_alerts[alert_key]
                        if not alert.resolved:
                            alert.resolved = True
                            self.logger.info(f"Performance alert resolved: {alert.message}")
                        
                        # Remove from active alerts after some time
                        if current_time - alert.timestamp > 300:  # 5 minutes
                            del self.active_alerts[alert_key]
    
    def _notify_alert_callbacks(self, alert: Alert):
        """Notify alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """Add alert notification callback.
        
        Args:
            callback: Function to call when alert is triggered
        """
        self.alert_callbacks.append(callback)
    
    def set_alert_threshold(self, metric_name: str, warning: float, critical: float, duration: int = 60):
        """Set alert threshold for a metric.
        
        Args:
            metric_name: Name of the metric
            warning: Warning threshold value
            critical: Critical threshold value
            duration: Duration in seconds threshold must be exceeded
        """
        self.alert_thresholds[metric_name] = AlertThreshold(
            metric_name=metric_name,
            warning_threshold=warning,
            critical_threshold=critical,
            duration_seconds=duration
        )
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert.
        
        Args:
            alert_id: ID of alert to acknowledge
            
        Returns:
            True if alert was found and acknowledged
        """
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self.logger.info(f"Alert acknowledged: {alert_id}")
                return True
        
        return False
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        with self._metrics_lock:
            return self.current_metrics
    
    def get_metrics_history(self, duration_minutes: int = 60) -> List[PerformanceMetrics]:
        """Get metrics history for specified duration.
        
        Args:
            duration_minutes: Duration in minutes
            
        Returns:
            List of metrics within the time range
        """
        cutoff_time = time.time() - (duration_minutes * 60)
        
        with self._metrics_lock:
            return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_active_alerts(self) -> List[Alert]:
        """Get list of active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        return self.alert_history[-limit:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        with self._metrics_lock:
            if not self.metrics_history:
                return {}
            
            # Calculate statistics over last hour
            hour_ago = time.time() - 3600
            recent_metrics = [m for m in self.metrics_history if m.timestamp >= hour_ago]
            
            if not recent_metrics:
                recent_metrics = list(self.metrics_history)[-10:]  # Last 10 if no recent data
            
            if not recent_metrics:
                return {}
            
            # Calculate averages and peaks
            cpu_values = [m.cpu_usage_percent for m in recent_metrics]
            memory_values = [m.memory_usage_mb for m in recent_metrics]
            response_times = [m.response_time_ms for m in recent_metrics if m.response_time_ms > 0]
            
            summary = {
                'current_metrics': self.current_metrics.to_dict(),
                'averages': {
                    'cpu_usage_percent': statistics.mean(cpu_values) if cpu_values else 0,
                    'memory_usage_mb': statistics.mean(memory_values) if memory_values else 0,
                    'response_time_ms': statistics.mean(response_times) if response_times else 0
                },
                'peaks': {
                    'cpu_usage_percent': max(cpu_values) if cpu_values else 0,
                    'memory_usage_mb': max(memory_values) if memory_values else 0,
                    'response_time_ms': max(response_times) if response_times else 0
                },
                'active_alerts_count': len(self.active_alerts),
                'total_requests': self._total_requests,
                'error_count': self._error_count,
                'monitoring_duration_hours': (time.time() - recent_metrics[0].timestamp) / 3600 if recent_metrics else 0
            }
            
            return summary
    
    def export_metrics(self, filename: str, duration_hours: int = 24):
        """Export metrics to JSON file.
        
        Args:
            filename: Output filename
            duration_hours: Duration of metrics to export
        """
        cutoff_time = time.time() - (duration_hours * 3600)
        
        with self._metrics_lock:
            export_data = {
                'export_timestamp': time.time(),
                'duration_hours': duration_hours,
                'metrics': [
                    m.to_dict() for m in self.metrics_history 
                    if m.timestamp >= cutoff_time
                ],
                'alert_history': [
                    {
                        'alert_id': alert.alert_id,
                        'metric_name': alert.metric_name,
                        'level': alert.level,
                        'current_value': alert.current_value,
                        'threshold': alert.threshold,
                        'message': alert.message,
                        'timestamp': alert.timestamp,
                        'acknowledged': alert.acknowledged,
                        'resolved': alert.resolved
                    }
                    for alert in self.alert_history
                    if alert.timestamp >= cutoff_time
                ],
                'summary': self.get_performance_summary()
            }
        
        try:
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Metrics exported to {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
    
    def reset_counters(self):
        """Reset performance counters."""
        self._error_count = 0
        self._total_requests = 0
        self._request_times.clear()
        self.logger.info("Performance counters reset")
    
    def shutdown(self):
        """Shutdown performance monitor."""
        self.stop_monitoring()
        self.logger.info("Performance monitor shutdown complete")


# Example usage and integration
class PerformanceAlerter:
    """Performance alerting system with multiple notification channels."""
    
    def __init__(self, monitor: PerformanceMonitor):
        """Initialize performance alerter.
        
        Args:
            monitor: Performance monitor instance
        """
        self.monitor = monitor
        self.logger = logging.getLogger(__name__)
        
        # Register alert callback
        self.monitor.add_alert_callback(self._handle_alert)
        
        # Notification channels
        self.notification_channels: List[Callable[[Alert], None]] = []
    
    def add_notification_channel(self, channel: Callable[[Alert], None]):
        """Add notification channel.
        
        Args:
            channel: Function to handle alert notifications
        """
        self.notification_channels.append(channel)
    
    def _handle_alert(self, alert: Alert):
        """Handle performance alert."""
        self.logger.warning(f"Performance Alert: {alert.message}")
        
        # Send to all notification channels
        for channel in self.notification_channels:
            try:
                channel(alert)
            except Exception as e:
                self.logger.error(f"Notification channel error: {e}")
    
    def email_notification_channel(self, alert: Alert):
        """Email notification channel (placeholder)."""
        # In a real implementation, this would send an email
        self.logger.info(f"EMAIL ALERT: {alert.level.upper()} - {alert.message}")
    
    def slack_notification_channel(self, alert: Alert):
        """Slack notification channel (placeholder)."""
        # In a real implementation, this would send to Slack
        self.logger.info(f"SLACK ALERT: {alert.level.upper()} - {alert.message}")
    
    def webhook_notification_channel(self, alert: Alert):
        """Webhook notification channel (placeholder)."""
        # In a real implementation, this would call a webhook
        self.logger.info(f"WEBHOOK ALERT: {alert.level.upper()} - {alert.message}")


# Context manager for performance monitoring
class PerformanceContext:
    """Context manager for performance monitoring."""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        """Initialize performance context.
        
        Args:
            monitor: Performance monitor instance
            operation_name: Name of operation being monitored
        """
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        """Enter performance monitoring context."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit performance monitoring context."""
        if self.start_time:
            duration = time.time() - self.start_time
            success = exc_type is None
            
            self.monitor.record_request(duration, success)
            
            if not success:
                self.monitor.logger.warning(f"Operation {self.operation_name} failed after {duration:.2f}s")
            else:
                self.monitor.logger.debug(f"Operation {self.operation_name} completed in {duration:.2f}s")