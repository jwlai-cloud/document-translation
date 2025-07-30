"""Integration tests for complete document translation workflows."""

import pytest
import asyncio
import tempfile
import os
import time
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

from src.services.orchestrator_service import (
    TranslationOrchestrator, 
    OrchestrationConfig,
    TranslationStatus
)
from src.services.upload_service import FileUploadService, UploadConfig
from src.services.download_service import DownloadService
from src.services.preview_service import PreviewService
from src.models.document import DocumentStructure
from src.models.quality import QualityScore, QualityReport
from src.errors import DocumentTranslationError, ErrorContext


class TestDocumentWorkflows:
    """Test complete document translation workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = OrchestrationConfig(
            max_concurrent_jobs=2,
            job_timeout_minutes=5,
            enable_quality_assessment=True,
            quality_threshold=0.7
        )
        self.orchestrator = TranslationOrchestrator(self.config)
        self.upload_service = FileUploadService(UploadConfig())
        self.download_service = DownloadService()
        self.preview_service = PreviewService()
        
        # Create test files
        self.test_files = self._create_test_files()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.orchestrator.shutdown()
        # Clean up test files
        for file_path in self.test_files.values():
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def _create_test_files(self) -> Dict[str, str]:
        """Create test files for different formats."""
        test_files = {}
        
        # Create test PDF content (mock)
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4\n%Mock PDF content for testing\n')
            test_files['pdf'] = f.name
        
        # Create test DOCX content (mock)
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            f.write(b'PK\x03\x04Mock DOCX content for testing')
            test_files['docx'] = f.name
        
        # Create test EPUB content (mock)
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            f.write(b'PK\x03\x04Mock EPUB content for testing')
            test_files['epub'] = f.name
        
        return test_files
    
    @pytest.mark.asyncio
    async def test_pdf_translation_workflow(self):
        """Test complete PDF translation workflow."""
        
        # Mock the parser and services to avoid actual file processing
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks
            mock_parser = Mock()
            mock_parser.parse.return_value = self._create_mock_document_structure()
            mock_parser.reconstruct.return_value = b'Mock reconstructed PDF'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = self._create_mock_translated_regions()
            mock_layout.return_value.analyze_layout.return_value = self._create_mock_layout_analysis()
            mock_quality.return_value.assess_translation.return_value = self._create_mock_quality_report()
            
            # Submit translation job
            job_id = self.orchestrator.submit_translation_job(
                file_path=self.test_files['pdf'],
                source_language='en',
                target_language='fr',
                format_type='pdf'
            )
            
            # Wait for job completion
            max_wait = 30  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status = self.orchestrator.get_job_status(job_id)
                if status and status['status'] in ['completed', 'failed']:
                    break
                await asyncio.sleep(0.5)
            
            # Verify job completion
            final_status = self.orchestrator.get_job_status(job_id)
            assert final_status is not None
            assert final_status['status'] == 'completed'
            assert final_status['overall_progress'] == 100.0
            assert 'download_link_id' in final_status
            
            # Verify all stages completed
            stages = final_status['stages']
            expected_stages = [
                'parsing', 'analyzing_layout', 'translating',
                'fitting_text', 'reconstructing', 'assessing_quality',
                'preparing_download'
            ]
            
            for stage in expected_stages:
                assert stage in stages
                assert stages[stage]['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_docx_translation_workflow(self):
        """Test complete DOCX translation workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks for DOCX
            mock_parser = Mock()
            mock_parser.parse.return_value = self._create_mock_document_structure('docx')
            mock_parser.reconstruct.return_value = b'Mock reconstructed DOCX'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = self._create_mock_translated_regions()
            mock_layout.return_value.analyze_layout.return_value = self._create_mock_layout_analysis()
            mock_quality.return_value.assess_translation.return_value = self._create_mock_quality_report()
            
            # Submit and process job
            job_id = self.orchestrator.submit_translation_job(
                file_path=self.test_files['docx'],
                source_language='en',
                target_language='es',
                format_type='docx'
            )
            
            # Wait for completion
            await self._wait_for_job_completion(job_id)
            
            # Verify results
            final_status = self.orchestrator.get_job_status(job_id)
            assert final_status['status'] == 'completed'
            assert final_status['format_type'] == 'docx'
            assert final_status['target_language'] == 'es'
    
    @pytest.mark.asyncio
    async def test_epub_translation_workflow(self):
        """Test complete EPUB translation workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks for EPUB
            mock_parser = Mock()
            mock_parser.parse.return_value = self._create_mock_document_structure('epub')
            mock_parser.reconstruct.return_value = b'Mock reconstructed EPUB'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = self._create_mock_translated_regions()
            mock_layout.return_value.analyze_layout.return_value = self._create_mock_layout_analysis()
            mock_quality.return_value.assess_translation.return_value = self._create_mock_quality_report()
            
            # Submit and process job
            job_id = self.orchestrator.submit_translation_job(
                file_path=self.test_files['epub'],
                source_language='fr',
                target_language='en',
                format_type='epub'
            )
            
            # Wait for completion
            await self._wait_for_job_completion(job_id)
            
            # Verify results
            final_status = self.orchestrator.get_job_status(job_id)
            assert final_status['status'] == 'completed'
            assert final_status['format_type'] == 'epub'
    
    @pytest.mark.asyncio
    async def test_concurrent_translation_jobs(self):
        """Test multiple concurrent translation jobs."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks
            mock_parser = Mock()
            mock_parser.parse.return_value = self._create_mock_document_structure()
            mock_parser.reconstruct.return_value = b'Mock reconstructed content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = self._create_mock_translated_regions()
            mock_layout.return_value.analyze_layout.return_value = self._create_mock_layout_analysis()
            mock_quality.return_value.assess_translation.return_value = self._create_mock_quality_report()
            
            # Submit multiple jobs
            job_ids = []
            for i, (format_type, file_path) in enumerate(self.test_files.items()):
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type=format_type
                )
                job_ids.append(job_id)
            
            # Wait for all jobs to complete
            for job_id in job_ids:
                await self._wait_for_job_completion(job_id)
            
            # Verify all jobs completed successfully
            for job_id in job_ids:
                status = self.orchestrator.get_job_status(job_id)
                assert status['status'] == 'completed'
            
            # Verify orchestrator stats
            stats = self.orchestrator.get_orchestrator_stats()
            assert stats['completed_jobs'] >= len(job_ids)
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in translation workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory:
            # Setup mock to raise an error
            mock_parser = Mock()
            mock_parser.parse.side_effect = Exception("Mock parsing error")
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            # Submit job that will fail
            job_id = self.orchestrator.submit_translation_job(
                file_path=self.test_files['pdf'],
                source_language='en',
                target_language='fr',
                format_type='pdf'
            )
            
            # Wait for job to fail
            await self._wait_for_job_completion(job_id, expected_status='failed')
            
            # Verify error handling
            final_status = self.orchestrator.get_job_status(job_id)
            assert final_status['status'] == 'failed'
            assert len(final_status.get('errors', [])) > 0
            
            # Verify error details
            error = final_status['errors'][0]
            assert 'parsing' in error.get('stage', '')
            assert error.get('recoverable') is not None
    
    @pytest.mark.asyncio
    async def test_quality_threshold_workflow(self):
        """Test workflow with quality threshold enforcement."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks with low quality score
            mock_parser = Mock()
            mock_parser.parse.return_value = self._create_mock_document_structure()
            mock_parser.reconstruct.return_value = b'Mock reconstructed content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = self._create_mock_translated_regions()
            mock_layout.return_value.analyze_layout.return_value = self._create_mock_layout_analysis()
            
            # Mock low quality score
            low_quality_report = self._create_mock_quality_report()
            low_quality_report.overall_score = QualityScore(0.5)  # Below threshold
            mock_quality.return_value.assess_translation.return_value = low_quality_report
            
            # Submit job with high quality threshold
            job_id = self.orchestrator.submit_translation_job(
                file_path=self.test_files['pdf'],
                source_language='en',
                target_language='fr',
                format_type='pdf'
            )
            
            # Wait for completion
            await self._wait_for_job_completion(job_id)
            
            # Verify quality handling
            final_status = self.orchestrator.get_job_status(job_id)
            # Job should complete but with quality warnings
            assert final_status['status'] in ['completed', 'failed']
            
            if 'quality_report' in final_status:
                assert final_status['quality_report']['overall_score'] < 0.7
    
    async def _wait_for_job_completion(self, job_id: str, 
                                     expected_status: str = 'completed',
                                     timeout: int = 30):
        """Wait for job to reach expected status."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.orchestrator.get_job_status(job_id)
            if status and status['status'] in [expected_status, 'failed', 'completed']:
                break
            await asyncio.sleep(0.5)
        
        # Verify we didn't timeout
        final_status = self.orchestrator.get_job_status(job_id)
        assert final_status is not None, f"Job {job_id} not found"
        
        if expected_status != 'failed':
            assert final_status['status'] != 'failed', f"Job failed unexpectedly: {final_status.get('errors', [])}"
    
    def _create_mock_document_structure(self, format_type: str = 'pdf') -> DocumentStructure:
        """Create mock document structure."""
        from src.models.document import DocumentStructure, PageStructure, TextRegion
        from src.models.layout import BoundingBox
        
        # Create mock text regions
        text_regions = [
            TextRegion(
                region_id="region_1",
                text_content="This is a test document.",
                bounding_box=BoundingBox(x=100, y=100, width=200, height=50),
                language="en",
                confidence=0.95
            ),
            TextRegion(
                region_id="region_2", 
                text_content="It contains multiple text regions.",
                bounding_box=BoundingBox(x=100, y=200, width=250, height=50),
                language="en",
                confidence=0.92
            )
        ]
        
        # Create mock page
        page = PageStructure(
            page_number=1,
            width=612,
            height=792,
            text_regions=text_regions,
            visual_elements=[]
        )
        
        # Create mock document
        return DocumentStructure(
            format_type=format_type,
            pages=[page],
            metadata={'title': 'Test Document', 'author': 'Test Author'}
        )
    
    def _create_mock_translated_regions(self) -> List[Any]:
        """Create mock translated regions."""
        from src.models.layout import AdjustedRegion, BoundingBox
        
        return [
            AdjustedRegion(
                region_id="region_1",
                original_text="This is a test document.",
                translated_text="Ceci est un document de test.",
                original_bbox=BoundingBox(x=100, y=100, width=200, height=50),
                adjusted_bbox=BoundingBox(x=100, y=100, width=220, height=50),
                confidence=0.93
            ),
            AdjustedRegion(
                region_id="region_2",
                original_text="It contains multiple text regions.",
                translated_text="Il contient plusieurs régions de texte.",
                original_bbox=BoundingBox(x=100, y=200, width=250, height=50),
                adjusted_bbox=BoundingBox(x=100, y=200, width=280, height=50),
                confidence=0.91
            )
        ]
    
    def _create_mock_layout_analysis(self) -> Any:
        """Create mock layout analysis."""
        from src.models.layout import LayoutAnalysis, SpatialRelationship
        
        return LayoutAnalysis(
            page_number=1,
            text_regions_count=2,
            visual_elements_count=0,
            spatial_relationships=[
                SpatialRelationship(
                    source_id="region_1",
                    target_id="region_2",
                    relationship_type="below",
                    confidence=0.95
                )
            ],
            reading_order=["region_1", "region_2"]
        )
    
    def _create_mock_quality_report(self) -> QualityReport:
        """Create mock quality report."""
        return QualityReport(
            overall_score=QualityScore(0.85),
            translation_accuracy=QualityScore(0.88),
            layout_preservation=QualityScore(0.82),
            readability=QualityScore(0.85),
            issues=[],
            recommendations=["Translation quality is good"]
        )


class TestLanguagePairWorkflows:
    """Test workflows with different language pairs."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = TranslationOrchestrator()
        self.test_file = self._create_test_file()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.orchestrator.shutdown()
        if os.path.exists(self.test_file):
            os.unlink(self.test_file)
    
    def _create_test_file(self) -> str:
        """Create a test file."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4\nMock content')
            return f.name
    
    @pytest.mark.parametrize("source_lang,target_lang", [
        ("en", "fr"),
        ("en", "es"), 
        ("en", "de"),
        ("fr", "en"),
        ("es", "en"),
        ("zh", "en"),
        ("ja", "en"),
        ("ko", "en")
    ])
    @pytest.mark.asyncio
    async def test_language_pair_workflow(self, source_lang: str, target_lang: str):
        """Test workflow with different language pairs."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks
            mock_parser = Mock()
            mock_parser.parse.return_value = Mock()
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = []
            mock_layout.return_value.analyze_layout.return_value = Mock()
            mock_quality.return_value.assess_translation.return_value = Mock(overall_score=Mock(value=0.85))
            
            # Submit job
            job_id = self.orchestrator.submit_translation_job(
                file_path=self.test_file,
                source_language=source_lang,
                target_language=target_lang,
                format_type='pdf'
            )
            
            # Wait for completion
            max_wait = 20
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status = self.orchestrator.get_job_status(job_id)
                if status and status['status'] in ['completed', 'failed']:
                    break
                await asyncio.sleep(0.5)
            
            # Verify job handled language pair correctly
            final_status = self.orchestrator.get_job_status(job_id)
            assert final_status is not None
            assert final_status['source_language'] == source_lang
            assert final_status['target_language'] == target_lang


class TestPerformanceWorkflows:
    """Test performance aspects of workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = TranslationOrchestrator()
        self.test_files = self._create_test_files()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.orchestrator.shutdown()
        for file_path in self.test_files:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def _create_test_files(self) -> List[str]:
        """Create multiple test files."""
        files = []
        for i in range(5):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(f'%PDF-1.4\nMock content {i}'.encode())
                files.append(f.name)
        return files
    
    @pytest.mark.asyncio
    async def test_processing_speed_benchmark(self):
        """Test processing speed benchmark."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup fast mocks
            mock_parser = Mock()
            mock_parser.parse.return_value = Mock()
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = []
            mock_layout.return_value.analyze_layout.return_value = Mock()
            mock_quality.return_value.assess_translation.return_value = Mock(overall_score=Mock(value=0.85))
            
            # Measure processing time
            start_time = time.time()
            
            job_ids = []
            for file_path in self.test_files[:3]:  # Process 3 files
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                job_ids.append(job_id)
            
            # Wait for all jobs to complete
            for job_id in job_ids:
                max_wait = 15
                job_start = time.time()
                
                while time.time() - job_start < max_wait:
                    status = self.orchestrator.get_job_status(job_id)
                    if status and status['status'] in ['completed', 'failed']:
                        break
                    await asyncio.sleep(0.1)
            
            total_time = time.time() - start_time
            
            # Verify performance (should complete within reasonable time)
            assert total_time < 30, f"Processing took too long: {total_time}s"
            
            # Verify all jobs completed
            for job_id in job_ids:
                status = self.orchestrator.get_job_status(job_id)
                assert status['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self):
        """Test memory usage during processing."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks
            mock_parser = Mock()
            mock_parser.parse.return_value = Mock()
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = []
            mock_layout.return_value.analyze_layout.return_value = Mock()
            mock_quality.return_value.assess_translation.return_value = Mock(overall_score=Mock(value=0.85))
            
            # Process multiple files
            job_ids = []
            for file_path in self.test_files:
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                job_ids.append(job_id)
            
            # Wait for completion
            for job_id in job_ids:
                max_wait = 10
                job_start = time.time()
                
                while time.time() - job_start < max_wait:
                    status = self.orchestrator.get_job_status(job_id)
                    if status and status['status'] in ['completed', 'failed']:
                        break
                    await asyncio.sleep(0.1)
            
            # Check final memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB for mocked operations)
            assert memory_increase < 100, f"Memory usage increased by {memory_increase}MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])