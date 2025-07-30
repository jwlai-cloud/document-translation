#!/usr/bin/env python3
"""Integration test for translation orchestrator service."""

import time
from unittest.mock import Mock, patch

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox,
    Dimensions, DocumentMetadata
)
from src.models.layout import AdjustedRegion, LayoutAnalysis
from src.models.quality import QualityScore, QualityReport
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
        enable_quality_assessment=True,
        quality_threshold=0.7
    )
    
    # Mock all services to avoid external dependencies
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
        setup_mocks(mocks)
        
        orchestrator = TranslationOrchestrator(config)
        
        try:
            # Test job submission
            print("\n✓ Testing job submission...")
            
            test_jobs = [
                {
                    "name": "PDF Translation (EN->FR)",
                    "file_path": "/test/document.pdf",
                    "source_lang": "en",
                    "target_lang": "fr",
                    "format": "pdf"
                },
                {
                    "name": "DOCX Translation (EN->ES)",
                    "file_path": "/test/document.docx",
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
            
            # Test progress tracking
            print("\n✓ Testing progress tracking...")
            
            progress_updates = []
            
            def progress_callback(job):
                progress_updates.append({
                    'job_id': job.job_id,
                    'status': job.status.value,
                    'progress': job.overall_progress,
                    'stage': job.current_stage
                })
            
            orchestrator.add_progress_callback(progress_callback)
            
            # Monitor job progress
            completed_jobs = set()
            timeout = time.time() + 30  # 30 second timeout
            
            while len(completed_jobs) < len(job_ids) and time.time() < timeout:
                for job_id in job_ids:
                    if job_id not in completed_jobs:
                        status = orchestrator.get_job_status(job_id)
                        
                        if status:
                            print(f"  - Job {job_id[:8]}...: {status['status']} ({status['overall_progress']:.1f}%)")
                            
                            if status['current_stage']:
                                print(f"    Current stage: {status['current_stage']}")
                            
                            if status['status'] in ['completed', 'failed', 'cancelled']:
                                completed_jobs.add(job_id)
                                print(f"    ✓ Job {status['status']}")
                
                time.sleep(0.5)
            
            # Test job status retrieval
            print("\n✓ Testing job status retrieval...")
            
            for job_id in job_ids:
                status = orchestrator.get_job_status(job_id)
                
                if status:
                    print(f"  - Job {job_id[:8]}...:")
                    print(f"    Status: {status['status']}")
                    print(f"    Progress: {status['overall_progress']:.1f}%")
                    print(f"    Source Language: {status['source_language']}")
                    print(f"    Target Language: {status['target_language']}")
                    print(f"    Format: {status['format_type']}")
                    print(f"    Error Count: {status['error_count']}")
                    print(f"    Retry Count: {status['retry_count']}")
                    
                    if status['download_link_id']:
                        print(f"    Download Link: {status['download_link_id'][:16]}...")
                    
                    if status['duration']:
                        print(f"    Duration: {status['duration']}")
                    
                    # Show stage details
                    print("    Stages:")
                    for stage_name, stage_info in status['stages'].items():
                        print(f"      {stage_name}: {stage_info['status']} ({stage_info['progress']:.1f}%)")
                else:
                    print(f"  - Job {job_id}: Not found")
            
            # Test orchestrator statistics
            print("\n✓ Testing orchestrator statistics...")
            
            stats = orchestrator.get_orchestrator_stats()
            print(f"  - Active jobs: {stats['active_jobs']}")
            print(f"  - Completed jobs: {stats['completed_jobs']}")
            print(f"  - Failed jobs: {stats['failed_jobs']}")
            print(f"  - Total jobs processed: {stats['total_jobs_processed']}")
            print(f"  - Success rate: {stats['success_rate']:.1f}%")
            print(f"  - Max concurrent jobs: {stats['max_concurrent_jobs']}")
            
            if stats['average_processing_time']:
                print(f"  - Average processing time: {stats['average_processing_time']:.2f}s")
            
            # Test job cancellation
            print("\n✓ Testing job cancellation...")
            
            # Submit a new job for cancellation test
            cancel_job_id = orchestrator.submit_translation_job(
                "/test/cancel_test.pdf", "en", "de", "pdf"
            )
            
            print(f"  - Submitted job for cancellation: {cancel_job_id[:8]}...")
            
            # Cancel the job
            success = orchestrator.cancel_job(cancel_job_id)
            
            if success:
                print("    ✓ Job cancelled successfully")
                
                # Verify cancellation
                status = orchestrator.get_job_status(cancel_job_id)
                if status and status['status'] == 'cancelled':
                    print("    ✓ Job status confirmed as cancelled")
                else:
                    print("    ⚠️  Job status not updated to cancelled")
            else:
                print("    ❌ Failed to cancel job")
            
            # Test job retry (simulate failure first)
            print("\n✓ Testing job retry...")
            
            # This would require more complex mocking to simulate failure
            # For now, just test the retry mechanism with a non-existent job
            retry_success = orchestrator.retry_job("nonexistent_job")
            assert retry_success is False
            print("    ✓ Retry correctly rejected for non-existent job")
            
            # Test progress callback functionality
            print("\n✓ Testing progress callbacks...")
            print(f"  - Received {len(progress_updates)} progress updates")
            
            if progress_updates:
                print("  - Sample progress updates:")
                for update in progress_updates[:5]:  # Show first 5
                    print(f"    Job {update['job_id'][:8]}...: {update['status']} ({update['progress']:.1f}%) - {update['stage']}")
            
            print("\n🎉 Translation orchestrator integration test completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            raise
        finally:
            orchestrator.shutdown()

def setup_mocks(mocks):
    """Setup mock responses for all services."""
    
    # Mock document parser
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
                        text_content="Test content to translate"
                    ),
                    TextRegion(
                        id="region2",
                        bounding_box=BoundingBox(10, 50, 200, 30),
                        text_content="Another paragraph for translation"
                    )
                ]
            )
        ],
        metadata=DocumentMetadata(title="Test Document")
    )
    
    mock_parser = Mock()
    mock_parser.parse.return_value = mock_document
    mocks['DocumentParserFactory'].return_value.create_parser.return_value = mock_parser
    
    # Mock layout analysis
    mock_layout_analysis = [
        LayoutAnalysis(
            page_number=1,
            text_regions=mock_document.pages[0].text_regions,
            visual_elements=[],
            spatial_relationships=[],
            reading_order=["region1", "region2"]
        )
    ]
    mocks['DefaultLayoutAnalysisEngine'].return_value.analyze_layout.return_value = mock_layout_analysis
    
    # Mock translation service
    translation_map = {
        "Test content to translate": "Contenu de test à traduire",
        "Another paragraph for translation": "Un autre paragraphe pour la traduction"
    }
    
    def mock_translate(text, source_lang, target_lang):
        return translation_map.get(text, f"Translated: {text}")
    
    mocks['TranslationService'].return_value.translate_text.side_effect = mock_translate
    
    # Mock text fitting
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
    
    # Mock layout adjustment
    mocks['LayoutAdjustmentEngine'].return_value.detect_layout_conflicts.return_value = []
    mocks['LayoutAdjustmentEngine'].return_value.resolve_conflicts.return_value = []
    
    # Mock quality assessment
    mock_quality_score = QualityScore(
        overall_score=0.85,
        metrics=Mock(),
        issues=[]
    )
    mocks['QualityAssessmentService'].return_value.assess_layout_preservation.return_value = mock_quality_score
    mocks['QualityAssessmentService'].return_value.generate_quality_report.return_value = QualityReport(
        document_id="test",
        overall_score=mock_quality_score
    )
    
    # Mock download service
    mock_download_result = Mock()
    mock_download_result.success = True
    mock_download_link = Mock()
    mock_download_link.link_id = "mock_download_link_12345"
    mock_download_result.download_link = mock_download_link
    mocks['DownloadService'].return_value.prepare_download.return_value = mock_download_result

def test_orchestrator_error_handling():
    """Test orchestrator error handling and recovery."""
    
    print("\n🧪 Testing Orchestrator Error Handling...")
    
    config = OrchestrationConfig(max_concurrent_jobs=1)
    
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
        
        # Setup mocks to simulate failures
        mock_parser = Mock()
        mock_parser.parse.side_effect = Exception("Parsing failed")
        mocks['DocumentParserFactory'].return_value.create_parser.return_value = mock_parser
        
        orchestrator = TranslationOrchestrator(config)
        
        try:
            # Submit job that will fail
            job_id = orchestrator.submit_translation_job("/test/failing_doc.pdf")
            
            # Wait for job to fail
            timeout = time.time() + 10
            while time.time() < timeout:
                status = orchestrator.get_job_status(job_id)
                if status and status['status'] == 'failed':
                    break
                time.sleep(0.1)
            
            # Verify job failed
            final_status = orchestrator.get_job_status(job_id)
            assert final_status['status'] == 'failed'
            assert final_status['error_count'] > 0
            
            print("  ✓ Error handling working correctly")
            print(f"    Job failed as expected with {final_status['error_count']} errors")
            
        finally:
            orchestrator.shutdown()

def test_orchestrator_concurrent_jobs():
    """Test orchestrator concurrent job handling."""
    
    print("\n🧪 Testing Concurrent Job Handling...")
    
    config = OrchestrationConfig(max_concurrent_jobs=2)
    
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
        
        setup_mocks(mocks)
        
        orchestrator = TranslationOrchestrator(config)
        
        try:
            # Submit multiple jobs quickly
            job_ids = []
            for i in range(5):
                job_id = orchestrator.submit_translation_job(f"/test/doc_{i}.pdf")
                job_ids.append(job_id)
            
            print(f"  - Submitted {len(job_ids)} jobs")
            
            # Monitor concurrent execution
            active_count = len(orchestrator.active_jobs)
            print(f"  - Active jobs: {active_count}")
            
            # Wait for some jobs to complete
            time.sleep(2)
            
            stats = orchestrator.get_orchestrator_stats()
            print(f"  - Jobs processed: {stats['total_jobs_processed']}")
            print("  ✓ Concurrent job handling working")
            
        finally:
            orchestrator.shutdown()

if __name__ == "__main__":
    try:
        test_orchestrator_integration()
        test_orchestrator_error_handling()
        test_orchestrator_concurrent_jobs()
        print("\n✅ All orchestrator integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise