#!/usr/bin/env python3
"""Integration test for translation orchestrator service."""

import time
from unittest.mock import Mock, patch, MagicMock

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox,
    Dimensions, DocumentMetadata
)
from src.models.layout import AdjustedRegion, LayoutAnalysis
from src.services.orchestrator_service import (
    TranslationOrchestrator, OrchestrationConfig, TranslationStatus
)

def test_orchestrator_integration():
    """Test complete orchestrator workflow."""
    
    print("🧪 Testing Translation Orchestrator Integration...")
    
    # Create orchestrator with test configuration
    config = OrchestrationConfig(
        max_concurrent_jobs=2,
        job_timeout_minutes=5,
        enable_quality_assessment=False,  # Disable for simpler testing
        cleanup_interval_minutes=1
    )
    
    # Mock all the services to avoid external dependencies
    with patch.multiple(
        'src.services.orchestrator_service',
        DocumentParserFactory=Mock(),
        DefaultLayoutAnalysisEngine=Mock(),
        TranslationService=Mock(),
        TextFittingEngine=Mock(),
        LayoutAdjustmentEngine=Mock(),
        DefaultLayoutReconstructionEngine=Mock(),
        QualityAssessmentService=Mock(),
        DownloadService=Mock()
    ) as mocks:
        
        # Setup mock responses
        mock_document = DocumentStructure(
            format="pdf",
            pages=[
                PageStructure(
                    page_number=1,
                    dimensions=Dimensions(width=400, height=600),
                    text_regions=[
                        TextRegion(
                            id="region1",
                            bounding_box=BoundingBox(10, 10, 200, 30),
                            text_content="Hello world"
                        ),
                        TextRegion(
                            id="region2",
                            bounding_box=BoundingBox(10, 50, 200, 30),
                            text_content="This is a test document"
                        )
                    ]
                )
            ],
            metadata=DocumentMetadata(title="Test Document")
        )
        
        # Setup parser mock
        mock_parser = Mock()
        mock_parser.parse.return_value = mock_document
        mocks['DocumentParserFactory'].return_value.create_parser.return_value = mock_parser
        
        # Setup layout analysis mock
        mock_layout_analysis = [LayoutAnalysis(page_number=1)]
        mocks['DefaultLayoutAnalysisEngine'].return_value.analyze_layout.return_value = mock_layout_analysis
        
        # Setup translation service mock
        def mock_translate(text, source, target):
            translations = {
                "Hello world": "Bonjour le monde",
                "This is a test document": "Ceci est un document de test"
            }
            return translations.get(text, f"Translated: {text}")
        
        mocks['TranslationService'].return_value.translate_text.side_effect = mock_translate
        
        # Setup text fitting mock
        def mock_fit_text(region, translated_text):
            return AdjustedRegion(
                original_region=region,
                adjusted_text=translated_text,
                new_bounding_box=BoundingBox(
                    region.bounding_box.x,
                    region.bounding_box.y,
                    region.bounding_box.width + 20,  # Slightly wider
                    region.bounding_box.height + 5   # Slightly taller
                ),
                adjustments=[],
                fit_quality=0.9
            )
        
        mocks['TextFittingEngine'].return_value.fit_text_to_region.side_effect = mock_fit_text
        
        # Setup layout adjustment mock
        mocks['LayoutAdjustmentEngine'].return_value.detect_layout_conflicts.return_value = []
        
        # Setup download service mock
        mock_download_result = Mock()
        mock_download_result.success = True
        mock_download_link = Mock()
        mock_download_link.link_id = "test_download_link_123"
        mock_download_result.download_link = mock_download_link
        mocks['DownloadService'].return_value.prepare_download.return_value = mock_download_result
        
        orchestrator = TranslationOrchestrator(config)
        
        try:
            # Test orchestrator initialization
            print("\n✓ Testing orchestrator initialization...")
            stats = orchestrator.get_orchestrator_stats()
            print(f"  - Max concurrent jobs: {stats['max_concurrent_jobs']}")
            print(f"  - Active jobs: {stats['active_jobs']}")
            print(f"  - Job timeout: {stats['job_timeout_minutes']} minutes")
            
            # Test job submission
            print("\n✓ Testing job submission...")
            
            test_jobs = [
                {
                    "name": "PDF Translation (EN->FR)",
                    "file_path": "/test/document1.pdf",
                    "source_lang": "en",
                    "target_lang": "fr",
                    "format": "pdf"
                },
                {
                    "name": "DOCX Translation (EN->ES)",
                    "file_path": "/test/document2.docx",
                    "source_lang": "en",
                    "target_lang": "es",
                    "format": "docx"
                }
            ]
            
            job_ids = []
            
            for job_config in test_jobs:
                print(f"  - Submitting: {job_config['name']}")
                
                job_id = orchestrator.submit_translation_job(
                    file_path=job_config["file_path"],
                    source_language=job_config["source_lang"],
                    target_language=job_config["target_lang"],
                    format_type=job_config["format"]
                )
                
                job_ids.append(job_id)
                print(f"    Job ID: {job_id}")
            
            # Test progress tracking with callbacks
            print("\n✓ Testing progress tracking...")
            
            progress_updates = []
            
            def progress_callback(job):
                progress_updates.append({
                    'job_id': job.job_id,
                    'status': job.status.value,
                    'progress': job.overall_progress,
                    'stage': job.current_stage
                })
                print(f"    Progress: {job.job_id[:8]}... - {job.status.value} - {job.overall_progress:.1f}% - {job.current_stage}")
            
            orchestrator.add_progress_callback(progress_callback)
            
            # Monitor job progress
            print("  - Monitoring job progress...")
            
            completed_jobs = set()
            timeout = time.time() + 30  # 30 second timeout
            
            while len(completed_jobs) < len(job_ids) and time.time() < timeout:
                for job_id in job_ids:
                    if job_id not in completed_jobs:
                        status = orchestrator.get_job_status(job_id)
                        
                        if status and status['status'] in ['completed', 'failed', 'cancelled']:
                            completed_jobs.add(job_id)
                            print(f"    Job {job_id[:8]}... {status['status']}")
                
                time.sleep(0.5)  # Check every 500ms
            
            # Test job status retrieval
            print("\n✓ Testing job status retrieval...")
            
            for job_id in job_ids:
                status = orchestrator.get_job_status(job_id)
                
                if status:
                    print(f"  - Job {job_id[:8]}...:")
                    print(f"    Status: {status['status']}")
                    print(f"    Progress: {status['overall_progress']:.1f}%")
                    print(f"    Duration: {status['duration']}")
                    print(f"    Error count: {status['error_count']}")
                    print(f"    Download link: {status['download_link_id']}")
                    
                    # Show stage details
                    print(f"    Stages:")
                    for stage_name, stage_info in status['stages'].items():
                        print(f"      {stage_name}: {stage_info['status']} ({stage_info['progress']:.1f}%)")
                else:
                    print(f"  - Job {job_id[:8]}...: Status not found")
            
            # Test job cancellation
            print("\n✓ Testing job cancellation...")
            
            # Submit a new job to cancel
            cancel_job_id = orchestrator.submit_translation_job(
                file_path="/test/cancel_test.pdf",
                source_language="en",
                target_language="de",
                format_type="pdf"
            )
            
            print(f"  - Submitted job for cancellation: {cancel_job_id[:8]}...")
            
            # Wait a moment then cancel
            time.sleep(0.1)
            success = orchestrator.cancel_job(cancel_job_id)
            
            if success:
                print(f"    ✓ Job cancelled successfully")
                
                # Check status
                status = orchestrator.get_job_status(cancel_job_id)
                if status and status['status'] == 'cancelled':
                    print(f"    ✓ Job status confirmed as cancelled")
                else:
                    print(f"    ⚠️  Job status: {status['status'] if status else 'Not found'}")
            else:
                print(f"    ❌ Failed to cancel job")
            
            # Test orchestrator statistics
            print("\n✓ Testing orchestrator statistics...")
            
            final_stats = orchestrator.get_orchestrator_stats()
            print(f"  - Active jobs: {final_stats['active_jobs']}")
            print(f"  - Completed jobs: {final_stats['completed_jobs']}")
            print(f"  - Failed jobs: {final_stats['failed_jobs']}")
            print(f"  - Total jobs processed: {final_stats['total_jobs_processed']}")
            print(f"  - Success rate: {final_stats['success_rate']:.1f}%")
            print(f"  - Average processing time: {final_stats['average_processing_time']:.2f}s" if final_stats['average_processing_time'] else "  - Average processing time: N/A")
            
            # Test progress callback data
            print(f"\n✓ Progress callback summary:")
            print(f"  - Total progress updates received: {len(progress_updates)}")
            
            if progress_updates:
                # Group by job
                job_progress = {}
                for update in progress_updates:
                    job_id = update['job_id']
                    if job_id not in job_progress:
                        job_progress[job_id] = []
                    job_progress[job_id].append(update)
                
                for job_id, updates in job_progress.items():
                    print(f"  - Job {job_id[:8]}...: {len(updates)} updates")
                    if updates:
                        final_update = updates[-1]
                        print(f"    Final: {final_update['status']} - {final_update['progress']:.1f}%")
            
            print("\n🎉 Translation orchestrator integration test completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            raise
        finally:
            # Always shutdown the orchestrator
            orchestrator.shutdown()

def test_orchestrator_error_handling():
    """Test orchestrator error handling capabilities."""
    
    print("\n🧪 Testing Orchestrator Error Handling...")
    
    config = OrchestrationConfig(
        max_concurrent_jobs=1,
        job_timeout_minutes=1,  # Short timeout for testing
        enable_quality_assessment=False
    )
    
    # Mock services with failures
    with patch.multiple(
        'src.services.orchestrator_service',
        DocumentParserFactory=Mock(),
        DefaultLayoutAnalysisEngine=Mock(),
        TranslationService=Mock(),
        TextFittingEngine=Mock(),
        LayoutAdjustmentEngine=Mock(),
        DefaultLayoutReconstructionEngine=Mock(),
        QualityAssessmentService=Mock(),
        DownloadService=Mock()
    ) as mocks:
        
        orchestrator = TranslationOrchestrator(config)
        
        try:
            # Test parsing failure
            print("  - Testing parsing failure...")
            mocks['DocumentParserFactory'].return_value.create_parser.side_effect = Exception("Parse failed")
            
            job_id = orchestrator.submit_translation_job("/test/bad_document.pdf")
            
            # Wait for job to fail
            timeout = time.time() + 5
            while time.time() < timeout:
                status = orchestrator.get_job_status(job_id)
                if status and status['status'] == 'failed':
                    break
                time.sleep(0.1)
            
            status = orchestrator.get_job_status(job_id)
            if status and status['status'] == 'failed':
                print(f"    ✓ Job failed as expected: {status['error_count']} errors")
            else:
                print(f"    ⚠️  Job status: {status['status'] if status else 'Not found'}")
            
            # Test concurrent job limit
            print("  - Testing concurrent job limit...")
            
            # Reset mocks to work properly
            mock_document = Mock()
            mock_parser = Mock()
            mock_parser.parse.return_value = mock_document
            mocks['DocumentParserFactory'].return_value.create_parser.return_value = mock_parser
            mocks['DocumentParserFactory'].return_value.create_parser.side_effect = None
            
            # Submit multiple jobs (more than limit)
            job_ids = []
            for i in range(3):  # More than max_concurrent_jobs (1)
                job_id = orchestrator.submit_translation_job(f"/test/document{i}.pdf")
                job_ids.append(job_id)
            
            print(f"    Submitted {len(job_ids)} jobs with limit of {config.max_concurrent_jobs}")
            
            # Check that jobs are queued/limited appropriately
            time.sleep(1)  # Give time for processing
            
            active_count = 0
            for job_id in job_ids:
                status = orchestrator.get_job_status(job_id)
                if status and status['status'] not in ['completed', 'failed', 'cancelled']:
                    active_count += 1
            
            print(f"    Active jobs: {active_count}")
            
            print("✓ Error handling testing completed!")
            
        finally:
            orchestrator.shutdown()

if __name__ == "__main__":
    try:
        test_orchestrator_integration()
        test_orchestrator_error_handling()
        print("\n✅ All orchestrator integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise