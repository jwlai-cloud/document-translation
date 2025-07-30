"""Test runner for integration tests with reporting and validation."""

import pytest
import sys
import time
import json
import os
from pathlib import Path
from typing import Dict, Any, List
import subprocess


class IntegrationTestRunner:
    """Comprehensive integration test runner."""
    
    def __init__(self):
        """Initialize test runner."""
        self.test_results = {
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'test_suites': {},
            'performance_metrics': {},
            'coverage_report': {},
            'errors': []
        }
        
        self.test_suites = {
            'integration_workflows': 'tests/test_integration_workflows.py',
            'end_to_end': 'tests/test_end_to_end.py',
            'performance': 'tests/test_performance.py',
            'error_handling': 'tests/test_error_handling.py'
        }
    
    def run_all_tests(self, generate_report: bool = True) -> Dict[str, Any]:
        """Run all integration tests."""
        
        print("🚀 Starting Integration Test Suite")
        print("=" * 50)
        
        self.test_results['start_time'] = time.time()
        
        # Run each test suite
        for suite_name, test_file in self.test_suites.items():
            print(f"\n📋 Running {suite_name} tests...")
            suite_result = self._run_test_suite(suite_name, test_file)
            self.test_results['test_suites'][suite_name] = suite_result
        
        self.test_results['end_time'] = time.time()
        self.test_results['duration'] = self.test_results['end_time'] - self.test_results['start_time']
        
        # Calculate totals
        self._calculate_totals()
        
        # Generate reports
        if generate_report:
            self._generate_reports()
        
        # Print summary
        self._print_summary()
        
        return self.test_results
    
    def run_specific_suite(self, suite_name: str) -> Dict[str, Any]:
        """Run a specific test suite."""
        
        if suite_name not in self.test_suites:
            raise ValueError(f"Unknown test suite: {suite_name}")
        
        print(f"🎯 Running {suite_name} test suite")
        print("=" * 40)
        
        test_file = self.test_suites[suite_name]
        result = self._run_test_suite(suite_name, test_file)
        
        return result
    
    def _run_test_suite(self, suite_name: str, test_file: str) -> Dict[str, Any]:
        """Run a single test suite."""
        
        suite_result = {
            'name': suite_name,
            'file': test_file,
            'start_time': time.time(),
            'end_time': None,
            'duration': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'output': '',
            'exit_code': 0
        }
        
        try:
            # Check if test file exists
            if not os.path.exists(test_file):
                suite_result['errors'].append(f"Test file not found: {test_file}")
                suite_result['exit_code'] = 1
                return suite_result
            
            # Run pytest with detailed output
            cmd = [
                sys.executable, '-m', 'pytest',
                test_file,
                '-v',
                '--tb=short',
                '--durations=10',
                '--json-report',
                f'--json-report-file=test_results_{suite_name}.json'
            ]
            
            # Add coverage for specific suites
            if suite_name in ['integration_workflows', 'end_to_end']:
                cmd.extend(['--cov=src', '--cov-report=term-missing'])
            
            # Run the tests
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per suite
            )
            
            suite_result['output'] = result.stdout + result.stderr
            suite_result['exit_code'] = result.returncode
            
            # Parse JSON report if available
            json_report_file = f'test_results_{suite_name}.json'
            if os.path.exists(json_report_file):
                try:
                    with open(json_report_file, 'r') as f:
                        json_data = json.load(f)
                    
                    suite_result['passed'] = json_data.get('summary', {}).get('passed', 0)
                    suite_result['failed'] = json_data.get('summary', {}).get('failed', 0)
                    suite_result['skipped'] = json_data.get('summary', {}).get('skipped', 0)
                    
                    # Extract test details
                    suite_result['test_details'] = []
                    for test in json_data.get('tests', []):
                        suite_result['test_details'].append({
                            'name': test.get('nodeid', ''),
                            'outcome': test.get('outcome', ''),
                            'duration': test.get('duration', 0)
                        })
                    
                    # Clean up JSON file
                    os.unlink(json_report_file)
                    
                except Exception as e:
                    suite_result['errors'].append(f"Failed to parse JSON report: {str(e)}")
            
            # Parse output for basic stats if JSON parsing failed
            if suite_result['passed'] == 0 and suite_result['failed'] == 0:
                self._parse_pytest_output(suite_result)
        
        except subprocess.TimeoutExpired:
            suite_result['errors'].append(f"Test suite timed out after 5 minutes")
            suite_result['exit_code'] = 124
        
        except Exception as e:
            suite_result['errors'].append(f"Failed to run test suite: {str(e)}")
            suite_result['exit_code'] = 1
        
        suite_result['end_time'] = time.time()
        suite_result['duration'] = suite_result['end_time'] - suite_result['start_time']
        
        # Print suite results
        self._print_suite_results(suite_result)
        
        return suite_result
    
    def _parse_pytest_output(self, suite_result: Dict[str, Any]):
        """Parse pytest output for basic statistics."""
        
        output = suite_result['output']
        
        # Look for summary line like "5 passed, 2 failed, 1 skipped"
        import re
        
        # Pattern for pytest summary
        pattern = r'(\d+)\s+(passed|failed|skipped|error)'
        matches = re.findall(pattern, output, re.IGNORECASE)
        
        for count, status in matches:
            count = int(count)
            status = status.lower()
            
            if status == 'passed':
                suite_result['passed'] = count
            elif status == 'failed':
                suite_result['failed'] = count
            elif status == 'skipped':
                suite_result['skipped'] = count
    
    def _calculate_totals(self):
        """Calculate total statistics across all suites."""
        
        for suite_result in self.test_results['test_suites'].values():
            self.test_results['passed_tests'] += suite_result['passed']
            self.test_results['failed_tests'] += suite_result['failed']
            self.test_results['skipped_tests'] += suite_result['skipped']
            self.test_results['errors'].extend(suite_result['errors'])
        
        self.test_results['total_tests'] = (
            self.test_results['passed_tests'] + 
            self.test_results['failed_tests'] + 
            self.test_results['skipped_tests']
        )
    
    def _generate_reports(self):
        """Generate comprehensive test reports."""
        
        # Generate HTML report
        self._generate_html_report()
        
        # Generate JSON report
        self._generate_json_report()
        
        # Generate performance report
        self._generate_performance_report()
    
    def _generate_html_report(self):
        """Generate HTML test report."""
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Integration Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .suite {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; }}
                .suite-header {{ background: #e9e9e9; padding: 10px; font-weight: bold; }}
                .suite-content {{ padding: 15px; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .skipped {{ color: orange; }}
                .error {{ color: red; background: #ffe6e6; padding: 5px; margin: 5px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧪 Integration Test Report</h1>
                <p><strong>Generated:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Duration:</strong> {self.test_results['duration']:.2f} seconds</p>
            </div>
            
            <div class="summary">
                <h2>📊 Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Count</th></tr>
                    <tr><td>Total Tests</td><td>{self.test_results['total_tests']}</td></tr>
                    <tr><td class="passed">Passed</td><td>{self.test_results['passed_tests']}</td></tr>
                    <tr><td class="failed">Failed</td><td>{self.test_results['failed_tests']}</td></tr>
                    <tr><td class="skipped">Skipped</td><td>{self.test_results['skipped_tests']}</td></tr>
                </table>
            </div>
        """
        
        # Add suite details
        for suite_name, suite_result in self.test_results['test_suites'].items():
            html_content += f"""
            <div class="suite">
                <div class="suite-header">{suite_name.replace('_', ' ').title()}</div>
                <div class="suite-content">
                    <p><strong>Duration:</strong> {suite_result['duration']:.2f}s</p>
                    <p><strong>Results:</strong> 
                       <span class="passed">{suite_result['passed']} passed</span>, 
                       <span class="failed">{suite_result['failed']} failed</span>, 
                       <span class="skipped">{suite_result['skipped']} skipped</span>
                    </p>
                    
                    {self._format_errors_html(suite_result['errors'])}
                </div>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # Write HTML report
        with open('integration_test_report.html', 'w') as f:
            f.write(html_content)
        
        print("📄 HTML report generated: integration_test_report.html")
    
    def _format_errors_html(self, errors: List[str]) -> str:
        """Format errors for HTML display."""
        
        if not errors:
            return ""
        
        html = "<h4>Errors:</h4>"
        for error in errors:
            html += f'<div class="error">{error}</div>'
        
        return html
    
    def _generate_json_report(self):
        """Generate JSON test report."""
        
        with open('integration_test_report.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print("📄 JSON report generated: integration_test_report.json")
    
    def _generate_performance_report(self):
        """Generate performance-specific report."""
        
        performance_data = {}
        
        # Extract performance metrics from performance test suite
        perf_suite = self.test_results['test_suites'].get('performance', {})
        if perf_suite:
            performance_data['performance_suite'] = {
                'duration': perf_suite['duration'],
                'passed': perf_suite['passed'],
                'failed': perf_suite['failed']
            }
        
        # Add overall performance metrics
        performance_data['overall'] = {
            'total_test_duration': self.test_results['duration'],
            'average_suite_duration': self.test_results['duration'] / len(self.test_suites),
            'test_throughput': self.test_results['total_tests'] / self.test_results['duration']
        }
        
        with open('performance_report.json', 'w') as f:
            json.dump(performance_data, f, indent=2)
        
        print("📄 Performance report generated: performance_report.json")
    
    def _print_suite_results(self, suite_result: Dict[str, Any]):
        """Print results for a single test suite."""
        
        name = suite_result['name']
        duration = suite_result['duration']
        passed = suite_result['passed']
        failed = suite_result['failed']
        skipped = suite_result['skipped']
        
        status_icon = "✅" if failed == 0 else "❌"
        
        print(f"{status_icon} {name}: {passed} passed, {failed} failed, {skipped} skipped ({duration:.2f}s)")
        
        if suite_result['errors']:
            for error in suite_result['errors']:
                print(f"   ⚠️  {error}")
    
    def _print_summary(self):
        """Print overall test summary."""
        
        print("\n" + "=" * 50)
        print("📊 INTEGRATION TEST SUMMARY")
        print("=" * 50)
        
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        failed = self.test_results['failed_tests']
        skipped = self.test_results['skipped_tests']
        duration = self.test_results['duration']
        
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['errors']:
            print(f"\n⚠️  Total Errors: {len(self.test_results['errors'])}")
        
        # Overall status
        if failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print(f"\n💥 {failed} TESTS FAILED")
        
        print("=" * 50)


def main():
    """Main entry point for test runner."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Run integration tests')
    parser.add_argument(
        '--suite', 
        choices=['integration_workflows', 'end_to_end', 'performance', 'error_handling'],
        help='Run specific test suite'
    )
    parser.add_argument(
        '--no-report', 
        action='store_true',
        help='Skip report generation'
    )
    
    args = parser.parse_args()
    
    runner = IntegrationTestRunner()
    
    try:
        if args.suite:
            # Run specific suite
            result = runner.run_specific_suite(args.suite)
            exit_code = 1 if result['failed'] > 0 else 0
        else:
            # Run all tests
            results = runner.run_all_tests(generate_report=not args.no_report)
            exit_code = 1 if results['failed_tests'] > 0 else 0
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n⚠️  Test run interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        print(f"\n💥 Test runner failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()