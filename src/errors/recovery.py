"""Recovery management and automatic error recovery."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from .exceptions import DocumentTranslationError, ErrorContext
from .handlers import RecoveryAction, ErrorHandler


class RecoveryStatus(Enum):
    """Status of recovery attempts."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    action: RecoveryAction
    status: RecoveryStatus
    start_time: float
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Any] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Get duration of recovery attempt."""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None


class RecoveryStrategy(ABC):
    """Abstract base class for recovery strategies."""
    
    @abstractmethod
    def can_handle(self, error: DocumentTranslationError) -> bool:
        """Check if this strategy can handle the error."""
        pass
    
    @abstractmethod
    async def execute(self, error: DocumentTranslationError, 
                     context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Execute the recovery strategy."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Priority of this strategy (lower = higher priority)."""
        pass


class RetryStrategy(RecoveryStrategy):
    """Strategy for retrying failed operations."""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def can_handle(self, error: DocumentTranslationError) -> bool:
        """Check if error is retryable."""
        return error.recoverable and error.error_code in [
            "TRANS_002",  # Translation service error
            "RESOURCE_002",  # Timeout error
            "SERVICE_001"  # General service error
        ]
    
    async def execute(self, error: DocumentTranslationError, 
                     context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Execute retry with exponential backoff."""
        retry_count = context.get('retry_count', 0)
        
        if retry_count >= self.max_retries:
            return False, f"Maximum retries ({self.max_retries}) exceeded"
        
        # Calculate backoff delay
        delay = self.backoff_factor ** retry_count
        await asyncio.sleep(delay)
        
        # Update context for next attempt
        context['retry_count'] = retry_count + 1
        
        return True, f"Retried after {delay:.1f}s delay (attempt {retry_count + 1})"
    
    @property
    def priority(self) -> int:
        return 1


class FallbackServiceStrategy(RecoveryStrategy):
    """Strategy for switching to fallback services."""
    
    def __init__(self, fallback_services: List[str]):
        self.fallback_services = fallback_services
    
    def can_handle(self, error: DocumentTranslationError) -> bool:
        """Check if we can fallback for this error."""
        return error.error_code in ["TRANS_002", "SERVICE_001"]
    
    async def execute(self, error: DocumentTranslationError, 
                     context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Switch to next available fallback service."""
        current_service = context.get('current_service', '')
        used_services = context.get('used_services', [])
        
        # Find next available service
        available_services = [
            service for service in self.fallback_services 
            if service not in used_services and service != current_service
        ]
        
        if not available_services:
            return False, "No more fallback services available"
        
        next_service = available_services[0]
        context['current_service'] = next_service
        context['used_services'] = used_services + [current_service]
        
        return True, f"Switched to fallback service: {next_service}"
    
    @property
    def priority(self) -> int:
        return 2


class ResourceOptimizationStrategy(RecoveryStrategy):
    """Strategy for optimizing resource usage."""
    
    def can_handle(self, error: DocumentTranslationError) -> bool:
        """Check if this is a resource-related error."""
        return error.error_code in ["RESOURCE_001", "RESOURCE_002"]
    
    async def execute(self, error: DocumentTranslationError, 
                     context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Optimize resource usage."""
        optimization_applied = []
        
        # Memory optimization
        if error.error_code == "RESOURCE_001":
            context['low_memory_mode'] = True
            context['batch_size'] = context.get('batch_size', 10) // 2
            optimization_applied.append("enabled low-memory mode")
            optimization_applied.append("reduced batch size")
        
        # Timeout optimization
        if error.error_code == "RESOURCE_002":
            current_timeout = context.get('timeout', 30)
            context['timeout'] = min(current_timeout * 2, 300)  # Max 5 minutes
            optimization_applied.append(f"increased timeout to {context['timeout']}s")
        
        if optimization_applied:
            return True, f"Applied optimizations: {', '.join(optimization_applied)}"
        
        return False, "No applicable optimizations found"
    
    @property
    def priority(self) -> int:
        return 3


class LayoutAdjustmentStrategy(RecoveryStrategy):
    """Strategy for adjusting layout processing parameters."""
    
    def can_handle(self, error: DocumentTranslationError) -> bool:
        """Check if this is a layout-related error."""
        return error.error_code in ["LAYOUT_002", "LAYOUT_003"]
    
    async def execute(self, error: DocumentTranslationError, 
                     context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Adjust layout processing parameters."""
        adjustments = []
        
        if error.error_code == "LAYOUT_002":  # Text fitting error
            # Increase allowed layout adjustment
            current_adjustment = context.get('max_layout_adjustment', 0.1)
            context['max_layout_adjustment'] = min(current_adjustment * 1.5, 0.5)
            adjustments.append(f"increased layout adjustment to {context['max_layout_adjustment']:.2f}")
            
            # Enable font size adjustment
            context['auto_font_adjustment'] = True
            adjustments.append("enabled automatic font size adjustment")
        
        if error.error_code == "LAYOUT_003":  # Reconstruction error
            # Simplify layout processing
            context['simplified_layout'] = True
            adjustments.append("enabled simplified layout processing")
        
        if adjustments:
            return True, f"Applied adjustments: {', '.join(adjustments)}"
        
        return False, "No applicable layout adjustments found"
    
    @property
    def priority(self) -> int:
        return 4


class QualityAdjustmentStrategy(RecoveryStrategy):
    """Strategy for adjusting quality thresholds."""
    
    def can_handle(self, error: DocumentTranslationError) -> bool:
        """Check if this is a quality-related error."""
        return error.error_code == "TRANS_004"
    
    async def execute(self, error: DocumentTranslationError, 
                     context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Adjust quality threshold."""
        current_threshold = context.get('quality_threshold', 0.8)
        min_threshold = 0.5
        
        if current_threshold <= min_threshold:
            return False, f"Quality threshold already at minimum ({min_threshold})"
        
        new_threshold = max(current_threshold - 0.1, min_threshold)
        context['quality_threshold'] = new_threshold
        
        return True, f"Lowered quality threshold to {new_threshold:.1f}"
    
    @property
    def priority(self) -> int:
        return 5


class RecoveryManager:
    """Manages automatic error recovery."""
    
    def __init__(self):
        self.strategies: List[RecoveryStrategy] = []
        self.recovery_history: List[RecoveryAttempt] = []
        self.max_recovery_attempts = 5
        self.recovery_timeout = 300  # 5 minutes
        
        # Register default strategies
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """Register default recovery strategies."""
        self.strategies = [
            RetryStrategy(max_retries=3),
            FallbackServiceStrategy(['google', 'azure', 'aws']),
            ResourceOptimizationStrategy(),
            LayoutAdjustmentStrategy(),
            QualityAdjustmentStrategy()
        ]
        
        # Sort by priority
        self.strategies.sort(key=lambda s: s.priority)
    
    def add_strategy(self, strategy: RecoveryStrategy):
        """Add a custom recovery strategy."""
        self.strategies.append(strategy)
        self.strategies.sort(key=lambda s: s.priority)
    
    async def attempt_recovery(self, error: DocumentTranslationError, 
                             context: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[RecoveryAttempt]]:
        """Attempt to recover from an error."""
        if context is None:
            context = {}
        
        recovery_attempts = []
        recovery_count = context.get('recovery_count', 0)
        
        if recovery_count >= self.max_recovery_attempts:
            return False, recovery_attempts
        
        # Find applicable strategies
        applicable_strategies = [
            strategy for strategy in self.strategies 
            if strategy.can_handle(error)
        ]
        
        if not applicable_strategies:
            return False, recovery_attempts
        
        # Try each strategy
        for strategy in applicable_strategies:
            attempt = RecoveryAttempt(
                action=RecoveryAction(
                    action_type=strategy.__class__.__name__,
                    description=f"Executing {strategy.__class__.__name__}",
                    automatic=True,
                    priority=strategy.priority
                ),
                status=RecoveryStatus.PENDING,
                start_time=time.time()
            )
            
            try:
                attempt.status = RecoveryStatus.IN_PROGRESS
                
                # Execute strategy with timeout
                success, message = await asyncio.wait_for(
                    strategy.execute(error, context),
                    timeout=self.recovery_timeout
                )
                
                attempt.end_time = time.time()
                attempt.result = message
                
                if success:
                    attempt.status = RecoveryStatus.SUCCESS
                    recovery_attempts.append(attempt)
                    self.recovery_history.append(attempt)
                    
                    # Update recovery count
                    context['recovery_count'] = recovery_count + 1
                    
                    return True, recovery_attempts
                else:
                    attempt.status = RecoveryStatus.FAILED
                    attempt.error_message = message
                
            except asyncio.TimeoutError:
                attempt.end_time = time.time()
                attempt.status = RecoveryStatus.FAILED
                attempt.error_message = f"Recovery timed out after {self.recovery_timeout}s"
                
            except Exception as e:
                attempt.end_time = time.time()
                attempt.status = RecoveryStatus.FAILED
                attempt.error_message = str(e)
            
            recovery_attempts.append(attempt)
            self.recovery_history.append(attempt)
        
        return False, recovery_attempts
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        total_attempts = len(self.recovery_history)
        successful_attempts = len([
            attempt for attempt in self.recovery_history 
            if attempt.status == RecoveryStatus.SUCCESS
        ])
        
        strategy_stats = {}
        for attempt in self.recovery_history:
            strategy_name = attempt.action.action_type
            if strategy_name not in strategy_stats:
                strategy_stats[strategy_name] = {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'avg_duration': 0
                }
            
            strategy_stats[strategy_name]['total'] += 1
            if attempt.status == RecoveryStatus.SUCCESS:
                strategy_stats[strategy_name]['successful'] += 1
            else:
                strategy_stats[strategy_name]['failed'] += 1
            
            if attempt.duration:
                current_avg = strategy_stats[strategy_name]['avg_duration']
                total = strategy_stats[strategy_name]['total']
                strategy_stats[strategy_name]['avg_duration'] = (
                    (current_avg * (total - 1) + attempt.duration) / total
                )
        
        return {
            'total_attempts': total_attempts,
            'successful_attempts': successful_attempts,
            'success_rate': successful_attempts / max(total_attempts, 1),
            'registered_strategies': len(self.strategies),
            'strategy_statistics': strategy_stats,
            'recent_attempts': [
                {
                    'action_type': attempt.action.action_type,
                    'status': attempt.status.value,
                    'duration': attempt.duration,
                    'result': attempt.result,
                    'error_message': attempt.error_message
                }
                for attempt in self.recovery_history[-10:]
            ]
        }


class AutoRecoveryHandler:
    """Handles automatic recovery for translation jobs."""
    
    def __init__(self, error_handler: ErrorHandler, recovery_manager: RecoveryManager):
        self.error_handler = error_handler
        self.recovery_manager = recovery_manager
        self.active_recoveries: Dict[str, bool] = {}
    
    async def handle_error_with_recovery(self, error: Exception, 
                                       context: Optional[ErrorContext] = None,
                                       job_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle error with automatic recovery attempts."""
        
        # Handle the error first
        error_response = self.error_handler.handle_error(error, context)
        
        # Convert to DocumentTranslationError if needed
        if isinstance(error, DocumentTranslationError):
            doc_error = error
        else:
            doc_error = DocumentTranslationError(
                message=str(error),
                error_code="UNKNOWN_001",
                category=error_response.details.get('category', 'service'),
                context=context,
                cause=error
            )
        
        # Attempt recovery if error is recoverable
        recovery_successful = False
        recovery_attempts = []
        
        if doc_error.recoverable and job_context:
            job_id = context.job_id if context else "unknown"
            
            # Prevent concurrent recovery for same job
            if job_id not in self.active_recoveries:
                self.active_recoveries[job_id] = True
                
                try:
                    recovery_successful, recovery_attempts = await self.recovery_manager.attempt_recovery(
                        doc_error, job_context
                    )
                finally:
                    self.active_recoveries.pop(job_id, None)
        
        return {
            'error_response': error_response.to_dict(),
            'recovery_attempted': bool(recovery_attempts),
            'recovery_successful': recovery_successful,
            'recovery_attempts': [
                {
                    'action_type': attempt.action.action_type,
                    'status': attempt.status.value,
                    'duration': attempt.duration,
                    'result': attempt.result,
                    'error_message': attempt.error_message
                }
                for attempt in recovery_attempts
            ]
        }
    
    def is_recovery_active(self, job_id: str) -> bool:
        """Check if recovery is active for a job."""
        return self.active_recoveries.get(job_id, False)