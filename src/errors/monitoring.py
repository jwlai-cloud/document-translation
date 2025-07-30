"""Monitoring and alerting for the error handling system."""

import logging
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .exceptions import DocumentTranslationError, ErrorSeverity, ErrorCategory
from .handlers import ErrorHandler
from .recovery import RecoveryManager


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a system alert."""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class ErrorMetrics:
    """Error metrics for monitoring."""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    error_rate_per_minute: float = 0.0
    recovery_success_rate: float = 0.0
    avg_recovery_time: float = 0.0
    critical_error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'total_errors': self.total_errors,
            'errors_by_category': self.errors_by_category,
            'errors_by_severity': self.errors_by_severity,
            'error_rate_per_minute': self.error_rate_per_minute,
            'recovery_success_rate': self.recovery_success_rate,
            'avg_recovery_time': self.avg_recovery_time,
            'critical_error_count': self.critical_error_count
        }


class ErrorMonitor:
    """Monitors error patterns and generates alerts."""
    
    def __init__(self, error_handler: ErrorHandler, recovery_manager: RecoveryManager):
        """Initialize error monitor.
        
        Args:
            error_handler: Error handler instance
            recovery_manager: Recovery manager instance
        """
        self.error_handler = error_handler
        self.recovery_manager = recovery_manager
        self.logger = logging.getLogger(__name__)
        
        # Alert configuration
        self.alert_thresholds = {
            'error_rate_per_minute': 10.0,
            'critical_error_count': 5,
            'recovery_failure_rate': 0.5,  # 50% failure rate
            'consecutive_failures': 3
        }
        
        # Alert handlers
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # Monitoring state
        self.alerts: List[Alert] = []
        self.last_metrics_time = time.time()
        self.consecutive_failures = 0
        
        # Setup default alert handlers
        self._setup_default_alert_handlers()
    
    def _setup_default_alert_handlers(self):
        """Setup default alert handlers."""
        self.alert_handlers.append(self._log_alert)
    
    def _log_alert(self, alert: Alert):
        """Default alert handler that logs alerts."""
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }.get(alert.level, logging.INFO)
        
        self.logger.log(
            log_level,
            f"ALERT [{alert.level.value.upper()}] {alert.title}: {alert.message}"
        )
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add custom alert handler.
        
        Args:
            handler: Function to handle alerts
        """
        self.alert_handlers.append(handler)
    
    def check_error_patterns(self) -> List[Alert]:
        """Check for error patterns and generate alerts."""
        alerts = []
        
        # Get current metrics
        metrics = self.get_current_metrics()
        
        # Check error rate
        if metrics.error_rate_per_minute > self.alert_thresholds['error_rate_per_minute']:
            alert = Alert(
                alert_id=f"high_error_rate_{int(time.time())}",
                level=AlertLevel.WARNING,
                title="High Error Rate",
                message=f"Error rate ({metrics.error_rate_per_minute:.1f}/min) exceeds threshold",
                metadata={'error_rate': metrics.error_rate_per_minute}
            )
            alerts.append(alert)
        
        # Check critical errors
        if metrics.critical_error_count > self.alert_thresholds['critical_error_count']:
            alert = Alert(
                alert_id=f"critical_errors_{int(time.time())}",
                level=AlertLevel.CRITICAL,
                title="Multiple Critical Errors",
                message=f"Critical error count ({metrics.critical_error_count}) exceeds threshold",
                metadata={'critical_count': metrics.critical_error_count}
            )
            alerts.append(alert)
        
        # Check recovery failure rate
        if metrics.recovery_success_rate < (1 - self.alert_thresholds['recovery_failure_rate']):
            alert = Alert(
                alert_id=f"recovery_failures_{int(time.time())}",
                level=AlertLevel.ERROR,
                title="High Recovery Failure Rate",
                message=f"Recovery success rate ({metrics.recovery_success_rate:.1%}) is too low",
                metadata={'success_rate': metrics.recovery_success_rate}
            )
            alerts.append(alert)
        
        # Store and dispatch alerts
        for alert in alerts:
            self.alerts.append(alert)
            self._dispatch_alert(alert)
        
        return alerts
    
    def _dispatch_alert(self, alert: Alert):
        """Dispatch alert to all handlers."""
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")
    
    def get_current_metrics(self) -> ErrorMetrics:
        """Get current error metrics."""
        error_stats = self.error_handler.get_error_statistics()
        recovery_stats = self.recovery_manager.get_recovery_statistics()
        
        # Calculate error rate
        current_time = time.time()
        time_window = current_time - self.last_metrics_time
        error_rate = error_stats['total_errors'] / max(time_window / 60, 1)  # per minute
        
        # Count critical errors
        critical_count = 0
        for error_data in error_stats.get('recent_errors', []):
            if error_data.get('error', {}).get('severity') == 'critical':
                critical_count += 1
        
        # Create metrics
        metrics = ErrorMetrics(
            total_errors=error_stats['total_errors'],
            errors_by_category=self._categorize_errors(error_stats),
            errors_by_severity=self._categorize_by_severity(error_stats),
            error_rate_per_minute=error_rate,
            recovery_success_rate=recovery_stats['success_rate'],
            avg_recovery_time=self._calculate_avg_recovery_time(recovery_stats),
            critical_error_count=critical_count
        )
        
        self.last_metrics_time = current_time
        return metrics
    
    def _categorize_errors(self, error_stats: Dict[str, Any]) -> Dict[str, int]:
        """Categorize errors by type."""
        categories = {}
        for error_data in error_stats.get('recent_errors', []):
            category = error_data.get('error', {}).get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
        return categories
    
    def _categorize_by_severity(self, error_stats: Dict[str, Any]) -> Dict[str, int]:
        """Categorize errors by severity."""
        severities = {}
        for error_data in error_stats.get('recent_errors', []):
            severity = error_data.get('error', {}).get('severity', 'unknown')
            severities[severity] = severities.get(severity, 0) + 1
        return severities
    
    def _calculate_avg_recovery_time(self, recovery_stats: Dict[str, Any]) -> float:
        """Calculate average recovery time."""
        recent_attempts = recovery_stats.get('recent_attempts', [])
        if not recent_attempts:
            return 0.0
        
        total_time = sum(
            attempt.get('duration', 0) or 0 
            for attempt in recent_attempts
        )
        return total_time / len(recent_attempts)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alerts."""
        active_alerts = [alert for alert in self.alerts if not alert.resolved]
        
        return {
            'total_alerts': len(self.alerts),
            'active_alerts': len(active_alerts),
            'alerts_by_level': {
                level.value: len([a for a in active_alerts if a.level == level])
                for level in AlertLevel
            },
            'recent_alerts': [
                {
                    'alert_id': alert.alert_id,
                    'level': alert.level.value,
                    'title': alert.title,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat(),
                    'acknowledged': alert.acknowledged,
                    'resolved': alert.resolved
                }
                for alert in self.alerts[-10:]  # Last 10 alerts
            ]
        }
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self.logger.info(f"Alert {alert_id} acknowledged")
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                self.logger.info(f"Alert {alert_id} resolved")
                return True
        return False


class ErrorDashboard:
    """Dashboard for error monitoring and visualization."""
    
    def __init__(self, monitor: ErrorMonitor):
        """Initialize dashboard.
        
        Args:
            monitor: Error monitor instance
        """
        self.monitor = monitor
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        metrics = self.monitor.get_current_metrics()
        alert_summary = self.monitor.get_alert_summary()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics.to_dict(),
            'alerts': alert_summary,
            'system_health': self._calculate_system_health(metrics),
            'recommendations': self._generate_recommendations(metrics)
        }
    
    def _calculate_system_health(self, metrics: ErrorMetrics) -> Dict[str, Any]:
        """Calculate overall system health score."""
        health_score = 100.0
        
        # Deduct points for high error rate
        if metrics.error_rate_per_minute > 5:
            health_score -= min(metrics.error_rate_per_minute * 2, 30)
        
        # Deduct points for critical errors
        if metrics.critical_error_count > 0:
            health_score -= metrics.critical_error_count * 10
        
        # Deduct points for low recovery rate
        if metrics.recovery_success_rate < 0.8:
            health_score -= (0.8 - metrics.recovery_success_rate) * 50
        
        health_score = max(health_score, 0)
        
        # Determine health status
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 50:
            status = "fair"
        else:
            status = "poor"
        
        return {
            'score': health_score,
            'status': status,
            'factors': {
                'error_rate': metrics.error_rate_per_minute,
                'critical_errors': metrics.critical_error_count,
                'recovery_rate': metrics.recovery_success_rate
            }
        }
    
    def _generate_recommendations(self, metrics: ErrorMetrics) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        if metrics.error_rate_per_minute > 10:
            recommendations.append("High error rate detected. Consider reviewing recent changes.")
        
        if metrics.critical_error_count > 3:
            recommendations.append("Multiple critical errors. Immediate attention required.")
        
        if metrics.recovery_success_rate < 0.7:
            recommendations.append("Low recovery success rate. Review recovery strategies.")
        
        if metrics.avg_recovery_time > 30:
            recommendations.append("High recovery time. Optimize recovery processes.")
        
        # Category-specific recommendations
        file_errors = metrics.errors_by_category.get('file_processing', 0)
        if file_errors > 5:
            recommendations.append("High file processing errors. Check file validation.")
        
        translation_errors = metrics.errors_by_category.get('translation', 0)
        if translation_errors > 5:
            recommendations.append("High translation errors. Check service connectivity.")
        
        if not recommendations:
            recommendations.append("System is operating normally.")
        
        return recommendations
    
    def export_metrics(self, format_type: str = "json") -> str:
        """Export metrics in specified format."""
        data = self.get_dashboard_data()
        
        if format_type.lower() == "json":
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format_type}")


# Example usage and configuration
def setup_error_monitoring(error_handler: ErrorHandler, 
                         recovery_manager: RecoveryManager) -> ErrorMonitor:
    """Setup error monitoring with default configuration."""
    
    monitor = ErrorMonitor(error_handler, recovery_manager)
    
    # Add custom alert handler for email notifications (example)
    def email_alert_handler(alert: Alert):
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            # In a real implementation, this would send an email
            print(f"EMAIL ALERT: {alert.title} - {alert.message}")
    
    monitor.add_alert_handler(email_alert_handler)
    
    return monitor