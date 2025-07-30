# Comprehensive Error Handling System

This module provides a comprehensive error handling system for the multimodal document translation application. It includes structured exception hierarchies, automatic recovery mechanisms, monitoring, and user-friendly error reporting.

## Features

### 1. Structured Exception Hierarchy
- **DocumentTranslationError**: Base exception for all translation-related errors
- **FileProcessingError**: Errors related to file operations
- **TranslationError**: Errors during translation processes
- **LayoutProcessingError**: Errors in layout analysis and reconstruction
- **ValidationError**: Input validation errors
- **ServiceError**: Service-level errors
- **ConfigurationError**: Configuration-related errors
- **ResourceError**: Resource limitation errors

### 2. Error Context and Metadata
Each error includes:
- Error code for programmatic handling
- Severity level (LOW, MEDIUM, HIGH, CRITICAL)
- Category classification
- Context information (job ID, file path, stage, component)
- Recovery suggestions
- Detailed metadata

### 3. Automatic Recovery System
- **RetryStrategy**: Exponential backoff retry mechanism
- **FallbackServiceStrategy**: Switch to backup services
- **ResourceOptimizationStrategy**: Optimize resource usage
- **LayoutAdjustmentStrategy**: Adjust layout processing parameters
- **QualityAdjustmentStrategy**: Adjust quality thresholds

### 4. Monitoring and Alerting
- Real-time error monitoring
- Alert generation based on error patterns
- Dashboard for error visualization
- Statistics and metrics collection

## Usage Examples

### Basic Error Handling

```python
from src.errors import DocumentTranslationError, ErrorHandler, ErrorContext

# Create error handler
error_handler = ErrorHandler()

# Handle an error
try:
    # Some operation that might fail
    pass
except Exception as e:
    context = ErrorContext(job_id="123", stage="parsing")
    response = error_handler.handle_error(e, context)
    print(f"Error: {response.message}")
    print(f"Suggestions: {response.suggestions}")
```

### Automatic Recovery

```python
from src.errors import AutoRecoveryHandler, RecoveryManager

# Setup recovery system
recovery_manager = RecoveryManager()
auto_recovery = AutoRecoveryHandler(error_handler, recovery_manager)

# Handle error with recovery
result = await auto_recovery.handle_error_with_recovery(
    error, context, job_context
)

if result['recovery_successful']:
    print("Error recovered successfully")
else:
    print("Recovery failed, manual intervention required")
```

### Monitoring Setup

```python
from src.errors.monitoring import ErrorMonitor, ErrorDashboard

# Setup monitoring
monitor = ErrorMonitor(error_handler, recovery_manager)
dashboard = ErrorDashboard(monitor)

# Check for alerts
alerts = monitor.check_error_patterns()
for alert in alerts:
    print(f"ALERT: {alert.title} - {alert.message}")

# Get dashboard data
data = dashboard.get_dashboard_data()
print(f"System health: {data['system_health']['status']}")
```

## Error Codes

### File Processing Errors (FILE_xxx)
- `FILE_001`: Invalid file format
- `FILE_002`: File size exceeded
- `FILE_003`: File corruption
- `FILE_004`: Parsing error

### Translation Errors (TRANS_xxx)
- `TRANS_001`: Unsupported language pair
- `TRANS_002`: Translation service error
- `TRANS_003`: Context preservation error
- `TRANS_004`: Quality threshold violation
- `TRANS_005`: Language validation error

### Layout Processing Errors (LAYOUT_xxx)
- `LAYOUT_001`: Layout analysis error
- `LAYOUT_002`: Text fitting error
- `LAYOUT_003`: Reconstruction error

### Resource Errors (RESOURCE_xxx)
- `RESOURCE_001`: Memory exceeded
- `RESOURCE_002`: Timeout error

## Configuration

### Error Handler Configuration
```python
# Custom recovery actions
error_handler.error_patterns["CUSTOM_001"] = [
    RecoveryAction(
        action_type="custom_recovery",
        description="Custom recovery action",
        automatic=True,
        priority=1
    )
]
```

### Monitoring Configuration
```python
# Alert thresholds
monitor.alert_thresholds = {
    'error_rate_per_minute': 5.0,
    'critical_error_count': 3,
    'recovery_failure_rate': 0.3
}
```

## Integration with Services

The error handling system is integrated with:
- **TranslationOrchestrator**: Handles job-level errors with recovery
- **Upload Service**: File validation and processing errors
- **Translation Service**: Service failures and quality issues
- **Layout Services**: Layout analysis and reconstruction errors
- **Web Interface**: User-friendly error display

## Best Practices

1. **Always provide context**: Include job ID, stage, and component information
2. **Use appropriate severity levels**: Critical for system failures, Medium for recoverable errors
3. **Provide actionable suggestions**: Help users understand how to resolve issues
4. **Log errors comprehensively**: Include full context for debugging
5. **Monitor error patterns**: Set up alerts for unusual error rates
6. **Test recovery mechanisms**: Ensure recovery strategies work as expected

## Testing

Run the comprehensive test suite:
```bash
pytest tests/test_error_handling.py -v
```

The tests cover:
- Exception creation and serialization
- Error handling workflows
- Recovery strategy execution
- Monitoring and alerting
- Integration scenarios

## Dependencies

- `asyncio`: For asynchronous recovery operations
- `logging`: For error logging and monitoring
- `dataclasses`: For structured error data
- `enum`: For error categorization
- `typing`: For type hints
- `datetime`: For timestamps and duration tracking