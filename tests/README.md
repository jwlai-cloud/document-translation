# Integration Tests for Multimodal Document Translator

This directory contains comprehensive integration tests for the multimodal document translation system. The tests validate complete workflows, performance characteristics, and system behavior under various conditions.

## Test Structure

### Test Suites

1. **`test_integration_workflows.py`** - Complete workflow integration tests
   - End-to-end document processing for PDF, DOCX, and EPUB
   - Concurrent job processing
   - Error handling and recovery workflows
   - Quality threshold enforcement
   - Language pair validation

2. **`test_end_to_end.py`** - User experience and web interface tests
   - Complete user workflows from upload to download
   - Web interface functionality
   - Preview generation and navigation
   - Batch processing capabilities
   - Error recovery from user perspective

3. **`test_performance.py`** - Performance and scalability tests
   - Processing speed benchmarks
   - Memory usage monitoring
   - CPU utilization testing
   - Concurrent processing performance
   - Load testing and scalability limits

4. **`test_error_handling.py`** - Comprehensive error handling tests
   - Exception hierarchy validation
   - Recovery mechanism testing
   - Error logging and monitoring
   - Alert generation and handling

### Test Runner

**`run_integration_tests.py`** - Comprehensive test runner with reporting
- Executes all test suites with detailed reporting
- Generates HTML and JSON reports
- Performance metrics collection
- Coverage analysis
- Error aggregation and analysis

## Running Tests

### Prerequisites

Install required dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov pytest-json-report psutil
```

### Run All Tests

```bash
# Run all integration tests
python tests/run_integration_tests.py

# Run with pytest directly
pytest tests/ -v
```

### Run Specific Test Suites

```bash
# Run specific suite
python tests/run_integration_tests.py --suite integration_workflows

# Run with pytest
pytest tests/test_integration_workflows.py -v
```

### Run Performance Tests

```bash
# Performance tests only
python tests/run_integration_tests.py --suite performance

# With detailed output
pytest tests/test_performance.py -v -s
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
```

## Test Categories

### Integration Tests (`@pytest.mark.integration`)

Test complete workflows across multiple components:

- **Document Processing Workflows**: PDF, DOCX, EPUB translation pipelines
- **Service Integration**: Upload → Translation → Preview → Download
- **Error Recovery**: Automatic error handling and recovery mechanisms
- **Quality Validation**: Quality assessment and threshold enforcement

### Performance Tests (`@pytest.mark.performance`)

Validate system performance characteristics:

- **Speed Benchmarks**: Processing time for different document sizes
- **Memory Usage**: Memory consumption and leak detection
- **Concurrency**: Multi-job processing performance
- **Scalability**: System behavior under load

### Async Tests (`@pytest.mark.asyncio`)

Test asynchronous operations:

- **Recovery Strategies**: Async error recovery mechanisms
- **Job Processing**: Concurrent job execution
- **Service Communication**: Async service interactions

## Test Data and Mocking

### Mock Strategy

Tests use comprehensive mocking to:
- Isolate component interactions
- Control test execution speed
- Simulate various error conditions
- Test edge cases safely

### Test Data Generation

- **Dynamic Test Files**: Generated for each test run
- **Realistic Content**: PDF, DOCX, EPUB structures
- **Size Variations**: Small, medium, and large files for performance testing
- **Error Scenarios**: Corrupted files, invalid formats

## Performance Benchmarks

### Target Metrics

- **Processing Speed**: < 30 seconds for typical documents
- **Memory Usage**: < 2GB peak memory per document
- **Concurrency**: Handle 5+ concurrent jobs
- **Success Rate**: > 95% for valid documents

### Monitoring

Tests monitor:
- Processing time per stage
- Memory usage patterns
- CPU utilization
- Error rates and recovery success

## Error Testing

### Error Categories Tested

1. **File Processing Errors**
   - Invalid formats
   - Corrupted files
   - Size limitations
   - Parsing failures

2. **Translation Errors**
   - Service failures
   - Language pair issues
   - Quality threshold violations
   - Context preservation problems

3. **System Errors**
   - Resource limitations
   - Timeout conditions
   - Service unavailability
   - Configuration issues

### Recovery Testing

- **Automatic Recovery**: Retry mechanisms, fallback services
- **Error Reporting**: User-friendly error messages
- **System Stability**: Graceful degradation under errors

## Continuous Integration

### CI/CD Integration

Tests are designed for CI/CD environments:
- Fast execution with mocking
- Comprehensive reporting
- Exit codes for build status
- Artifact generation (reports, logs)

### Test Execution Matrix

- **Python Versions**: 3.8, 3.9, 3.10, 3.11
- **Operating Systems**: Linux, macOS, Windows
- **Load Conditions**: Single job, concurrent jobs, high load

## Reporting

### Generated Reports

1. **HTML Report** (`integration_test_report.html`)
   - Visual test results
   - Suite-by-suite breakdown
   - Error details and stack traces
   - Performance metrics

2. **JSON Report** (`integration_test_report.json`)
   - Machine-readable results
   - Detailed test metadata
   - Performance data
   - Error information

3. **Performance Report** (`performance_report.json`)
   - Benchmark results
   - Resource usage metrics
   - Scalability analysis
   - Trend data

### Metrics Tracked

- **Test Execution**: Pass/fail rates, duration, coverage
- **Performance**: Processing speed, memory usage, throughput
- **Quality**: Error rates, recovery success, user experience
- **System Health**: Resource utilization, stability metrics

## Troubleshooting

### Common Issues

1. **Async Test Warnings**
   ```bash
   # Install pytest-asyncio
   pip install pytest-asyncio
   ```

2. **Import Errors**
   ```bash
   # Ensure PYTHONPATH includes src directory
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   ```

3. **Mock Failures**
   - Check mock setup in test fixtures
   - Verify service dependencies
   - Review error logs for details

4. **Performance Test Failures**
   - Adjust timeout values for slower systems
   - Check system resources during test execution
   - Review performance thresholds

### Debug Mode

Run tests with debug output:
```bash
pytest tests/ -v -s --tb=long --log-cli-level=DEBUG
```

### Test Isolation

Run tests in isolation:
```bash
pytest tests/test_integration_workflows.py::TestDocumentWorkflows::test_pdf_translation_workflow -v
```

## Contributing

### Adding New Tests

1. **Follow Naming Convention**: `test_*.py` files, `test_*` functions
2. **Use Appropriate Markers**: `@pytest.mark.asyncio`, `@pytest.mark.integration`
3. **Mock External Dependencies**: Use comprehensive mocking strategy
4. **Include Documentation**: Document test purpose and expected behavior
5. **Performance Considerations**: Set appropriate timeouts and resource limits

### Test Quality Guidelines

- **Isolation**: Tests should not depend on each other
- **Repeatability**: Tests should produce consistent results
- **Coverage**: Test both success and failure scenarios
- **Performance**: Tests should complete within reasonable time
- **Documentation**: Clear test names and docstrings

## Maintenance

### Regular Tasks

- **Update Test Data**: Refresh test documents and scenarios
- **Review Performance Baselines**: Adjust benchmarks as system evolves
- **Mock Maintenance**: Update mocks to match service changes
- **Report Analysis**: Review test reports for trends and issues

### Monitoring

- **Test Execution Time**: Monitor for performance degradation
- **Failure Rates**: Track test stability over time
- **Coverage Metrics**: Ensure adequate test coverage
- **Resource Usage**: Monitor test resource consumption