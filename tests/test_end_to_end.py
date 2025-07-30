"""End-to-end tests for document translation system."""

import pytest
import asyncio
import tempfile
import os
import json
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from src.web.gradio_interface import TranslationWebInterface
from src.services.orchestrator_service import TranslationOrchestrator
from src.services.upload_service import FileUploadService, UploadConfig
from src.models.document import DocumentStructure
from src.models.quality import QualityScore, QualityReport


class TestEndToEndWorkflows:
    """End-to-end tests simulating complete user workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.web_interface = TranslationWebInterface()
        self.test_files = self._create_test_documents()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.web_interface.shutdown()
        # Clean up test files
        for file_path in self.test_files.values():
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def _create_test_documents(self) -> Dict[str, str]:
        """Create realistic test documents."""
        test_files = {}
        
        # Create a more realistic PDF structure
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(pdf_content)
            test_files['pdf'] = f.name
        
        # Create a basic DOCX structure (ZIP format)
        docx_content = b'PK\x03\x04\x14\x00\x00\x00\x08\x00Mock DOCX with text content'
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            f.write(docx_content)
            test_files['docx'] = f.name
        
        # Create a basic EPUB structure (ZIP format)
        epub_content = b'PK\x03\x04\x14\x00\x00\x00\x08\x00Mock EPUB with chapters'
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            f.write(epub_content)
            test_files['epub'] = f.name
        
        return test_files
    
    @pytest.mark.asyncio
    async def test_complete_pdf_translation_workflow(self):
        """Test complete PDF translation from upload to download."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality, \
             patch('src.layout.reconstruction_engine.DefaultLayoutReconstructionEngine') as mock_reconstruction:
            
            # Setup comprehensive mocks
            self._setup_comprehensive_mocks(
                mock_factory, mock_translation, mock_layout, 
                mock_quality, mock_reconstruction
            )
            
            # Step 1: Upload file
            with open(self.test_files['pdf'], 'rb') as f:
                file_data = f.read()
            
            upload_result = self.web_interface._handle_translation_submit(
                file_data=file_data,
                format_type='pdf',
                source_lang='en',
                target_lang='fr',
                preserve_layout=True,
                quality_assessment=True,
                quality_threshold=0.8
            )
            
            # Verify upload success
            assert "successfully" in upload_result[0].lower()
            
            # Step 2: Monitor progress
            # Extract job ID from the response (simplified)
            job_id = None
            for job_id_key in self.web_interface.active_jobs.keys():
                job_id = job_id_key
                break
            
            assert job_id is not None
            
            # Wait for job completion
            await self._wait_for_job_completion(job_id)
            
            # Step 3: Check job status
            jobs_data, job_choices = self.web_interface._refresh_jobs_table()
            assert len(jobs_data) > 0
            
            completed_jobs = [job for job in jobs_data if job[1] == 'completed']
            assert len(completed_jobs) > 0
            
            # Step 4: Generate preview
            preview_html, preview_stats, page_slider, prev_btn, next_btn, export_btn = \
                self.web_interface._generate_preview(
                    job_id=job_id,
                    show_original=True,
                    show_translated=True,
                    view_mode='side_by_side',
                    zoom_level=1.0,
                    highlight_mode='changes',
                    page_number=1
                )
            
            # Verify preview generation
            assert "Document Preview" in preview_html
            assert preview_stats.visible
            
            # Step 5: Download translated document
            download_info, file_details, download_status = \
                self.web_interface._get_download_info(job_id)
            
            assert download_info.visible
            assert "ready for download" in download_status.lower()
            
            download_status_result, download_files, download_history = \
                self.web_interface._handle_download(
                    job_id=job_id,
                    download_format='original',
                    include_quality_report=True,
                    include_metadata=False
                )
            
            # Verify download
            assert "download ready" in download_status_result.lower()
            assert download_files.visible
    
    @pytest.mark.asyncio
    async def test_complete_docx_translation_workflow(self):
        """Test complete DOCX translation workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality, \
             patch('src.layout.reconstruction_engine.DefaultLayoutReconstructionEngine') as mock_reconstruction:
            
            self._setup_comprehensive_mocks(
                mock_factory, mock_translation, mock_layout, 
                mock_quality, mock_reconstruction, format_type='docx'
            )
            
            # Upload and process DOCX
            with open(self.test_files['docx'], 'rb') as f:
                file_data = f.read()
            
            upload_result = self.web_interface._handle_translation_submit(
                file_data=file_data,
                format_type='docx',
                source_lang='en',
                target_lang='es',
                preserve_layout=True,
                quality_assessment=True,
                quality_threshold=0.7
            )
            
            assert "successfully" in upload_result[0].lower()
            
            # Get job ID and wait for completion
            job_id = list(self.web_interface.active_jobs.keys())[0]
            await self._wait_for_job_completion(job_id)
            
            # Verify completion
            final_status = self.web_interface.orchestrator.get_job_status(job_id)
            assert final_status['status'] == 'completed'
            assert final_status['format_type'] == 'docx'
    
    @pytest.mark.asyncio
    async def test_complete_epub_translation_workflow(self):
        """Test complete EPUB translation workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality, \
             patch('src.layout.reconstruction_engine.DefaultLayoutReconstructionEngine') as mock_reconstruction:
            
            self._setup_comprehensive_mocks(
                mock_factory, mock_translation, mock_layout, 
                mock_quality, mock_reconstruction, format_type='epub'
            )
            
            # Upload and process EPUB
            with open(self.test_files['epub'], 'rb') as f:
                file_data = f.read()
            
            upload_result = self.web_interface._handle_translation_submit(
                file_data=file_data,
                format_type='epub',
                source_lang='fr',
                target_lang='en',
                preserve_layout=True,
                quality_assessment=True,
                quality_threshold=0.8
            )
            
            assert "successfully" in upload_result[0].lower()
            
            # Get job ID and wait for completion
            job_id = list(self.web_interface.active_jobs.keys())[0]
            await self._wait_for_job_completion(job_id)
            
            # Verify completion
            final_status = self.web_interface.orchestrator.get_job_status(job_id)
            assert final_status['status'] == 'completed'
            assert final_status['format_type'] == 'epub'
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test error recovery in end-to-end workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory:
            # Setup mock to fail initially, then succeed
            mock_parser = Mock()
            call_count = 0
            
            def parse_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Temporary parsing failure")
                return self._create_mock_document_structure()
            
            mock_parser.parse.side_effect = parse_side_effect
            mock_parser.reconstruct.return_value = b'Mock reconstructed content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            # Upload file
            with open(self.test_files['pdf'], 'rb') as f:
                file_data = f.read()
            
            upload_result = self.web_interface._handle_translation_submit(
                file_data=file_data,
                format_type='pdf',
                source_lang='en',
                target_lang='fr',
                preserve_layout=True,
                quality_assessment=True,
                quality_threshold=0.8
            )
            
            # Should still succeed due to error handling
            job_id = list(self.web_interface.active_jobs.keys())[0]
            
            # Wait for job to complete or fail
            await self._wait_for_job_completion(job_id, allow_failure=True)
            
            # Check if error handling worked
            final_status = self.web_interface.orchestrator.get_job_status(job_id)
            assert final_status is not None
            
            # Should have error information
            if final_status['status'] == 'failed':
                assert len(final_status.get('errors', [])) > 0
    
    @pytest.mark.asyncio
    async def test_quality_validation_workflow(self):
        """Test quality validation in workflow."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality, \
             patch('src.layout.reconstruction_engine.DefaultLayoutReconstructionEngine') as mock_reconstruction:
            
            # Setup mocks with varying quality scores
            self._setup_comprehensive_mocks(
                mock_factory, mock_translation, mock_layout, 
                mock_quality, mock_reconstruction
            )
            
            # Override quality mock to return low quality
            low_quality_report = QualityReport(
                overall_score=QualityScore(0.6),  # Below typical threshold
                translation_accuracy=QualityScore(0.65),
                layout_preservation=QualityScore(0.55),
                readability=QualityScore(0.6),
                issues=["Low translation confidence", "Layout adjustments needed"],
                recommendations=["Review translation manually", "Adjust quality threshold"]
            )
            mock_quality.return_value.assess_translation.return_value = low_quality_report
            
            # Upload with high quality threshold
            with open(self.test_files['pdf'], 'rb') as f:
                file_data = f.read()
            
            upload_result = self.web_interface._handle_translation_submit(
                file_data=file_data,
                format_type='pdf',
                source_lang='en',
                target_lang='fr',
                preserve_layout=True,
                quality_assessment=True,
                quality_threshold=0.8  # Higher than mock quality
            )
            
            job_id = list(self.web_interface.active_jobs.keys())[0]
            await self._wait_for_job_completion(job_id, allow_failure=True)
            
            # Check quality handling
            final_status = self.web_interface.orchestrator.get_job_status(job_id)
            
            # Job should complete but with quality warnings
            if 'quality_report' in final_status:
                quality_score = final_status['quality_report'].get('overall_score', 0)
                assert quality_score < 0.8
    
    @pytest.mark.asyncio
    async def test_batch_processing_workflow(self):
        """Test batch processing of multiple documents."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality, \
             patch('src.layout.reconstruction_engine.DefaultLayoutReconstructionEngine') as mock_reconstruction:
            
            self._setup_comprehensive_mocks(
                mock_factory, mock_translation, mock_layout, 
                mock_quality, mock_reconstruction
            )
            
            # Submit multiple jobs
            job_ids = []
            
            for format_type, file_path in self.test_files.items():
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                upload_result = self.web_interface._handle_translation_submit(
                    file_data=file_data,
                    format_type=format_type,
                    source_lang='en',
                    target_lang='fr',
                    preserve_layout=True,
                    quality_assessment=True,
                    quality_threshold=0.7
                )
                
                # Get the latest job ID
                current_jobs = list(self.web_interface.active_jobs.keys())
                new_job_id = [jid for jid in current_jobs if jid not in job_ids]
                if new_job_id:
                    job_ids.append(new_job_id[0])
            
            # Wait for all jobs to complete
            for job_id in job_ids:
                await self._wait_for_job_completion(job_id)
            
            # Verify all jobs completed
            jobs_data, _ = self.web_interface._refresh_jobs_table()
            completed_jobs = [job for job in jobs_data if job[1] == 'completed']
            assert len(completed_jobs) >= len(job_ids)
            
            # Test batch download
            batch_result = self.web_interface._handle_batch_download(
                selected_jobs=job_ids,
                download_format='original'
            )
            
            assert "batch download" in batch_result[0].lower()
    
    def _setup_comprehensive_mocks(self, mock_factory, mock_translation, 
                                 mock_layout, mock_quality, mock_reconstruction,
                                 format_type: str = 'pdf'):
        """Setup comprehensive mocks for testing."""
        
        # Parser mock
        mock_parser = Mock()
        mock_parser.parse.return_value = self._create_mock_document_structure(format_type)
        mock_parser.reconstruct.return_value = f'Mock reconstructed {format_type}'.encode()
        mock_factory.return_value.create_parser.return_value = mock_parser
        
        # Translation mock
        mock_translation.return_value.translate_regions.return_value = self._create_mock_translated_regions()
        
        # Layout analysis mock
        mock_layout.return_value.analyze_layout.return_value = self._create_mock_layout_analysis()
        
        # Quality assessment mock
        mock_quality.return_value.assess_translation.return_value = self._create_mock_quality_report()
        
        # Reconstruction mock
        mock_reconstruction.return_value.reconstruct_document.return_value = f'Mock final {format_type}'.encode()
    
    def _create_mock_document_structure(self, format_type: str = 'pdf'):
        """Create mock document structure."""
        from src.models.document import DocumentStructure, PageStructure, TextRegion
        from src.models.layout import BoundingBox
        
        text_regions = [
            TextRegion(
                region_id="region_1",
                text_content="This is a sample document for testing.",
                bounding_box=BoundingBox(x=50, y=100, width=300, height=40),
                language="en",
                confidence=0.95
            ),
            TextRegion(
                region_id="region_2",
                text_content="It contains multiple paragraphs and text regions.",
                bounding_box=BoundingBox(x=50, y=200, width=350, height=40),
                language="en",
                confidence=0.93
            )
        ]
        
        page = PageStructure(
            page_number=1,
            width=612 if format_type == 'pdf' else 800,
            height=792 if format_type == 'pdf' else 600,
            text_regions=text_regions,
            visual_elements=[]
        )
        
        return DocumentStructure(
            format_type=format_type,
            pages=[page],
            metadata={
                'title': f'Test {format_type.upper()} Document',
                'author': 'Test Suite',
                'language': 'en'
            }
        )
    
    def _create_mock_translated_regions(self):
        """Create mock translated regions."""
        from src.models.layout import AdjustedRegion, BoundingBox
        
        return [
            AdjustedRegion(
                region_id="region_1",
                original_text="This is a sample document for testing.",
                translated_text="Ceci est un document d'exemple pour les tests.",
                original_bbox=BoundingBox(x=50, y=100, width=300, height=40),
                adjusted_bbox=BoundingBox(x=50, y=100, width=320, height=40),
                confidence=0.92
            ),
            AdjustedRegion(
                region_id="region_2",
                original_text="It contains multiple paragraphs and text regions.",
                translated_text="Il contient plusieurs paragraphes et régions de texte.",
                original_bbox=BoundingBox(x=50, y=200, width=350, height=40),
                adjusted_bbox=BoundingBox(x=50, y=200, width=370, height=40),
                confidence=0.90
            )
        ]
    
    def _create_mock_layout_analysis(self):
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
                    relationship_type="above",
                    confidence=0.95
                )
            ],
            reading_order=["region_1", "region_2"]
        )
    
    def _create_mock_quality_report(self):
        """Create mock quality report."""
        return QualityReport(
            overall_score=QualityScore(0.87),
            translation_accuracy=QualityScore(0.89),
            layout_preservation=QualityScore(0.85),
            readability=QualityScore(0.87),
            issues=[],
            recommendations=["Translation quality is excellent", "Layout preserved well"]
        )
    
    async def _wait_for_job_completion(self, job_id: str, timeout: int = 30, 
                                     allow_failure: bool = False):
        """Wait for job completion."""
        import time
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.web_interface.orchestrator.get_job_status(job_id)
            if status and status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(0.5)
        
        # Verify completion
        final_status = self.web_interface.orchestrator.get_job_status(job_id)
        assert final_status is not None
        
        if not allow_failure:
            assert final_status['status'] == 'completed', \
                f"Job failed: {final_status.get('errors', [])}"


class TestUserExperienceWorkflows:
    """Test user experience aspects of workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.web_interface = TranslationWebInterface()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.web_interface.shutdown()
    
    def test_error_message_clarity(self):
        """Test that error messages are clear and helpful."""
        
        # Test invalid file format
        result = self.web_interface._handle_translation_submit(
            file_data=None,
            format_type='pdf',
            source_lang='en',
            target_lang='fr',
            preserve_layout=True,
            quality_assessment=True,
            quality_threshold=0.8
        )
        
        # Should have clear error message
        assert "select a file" in result[0].lower()
        assert result[4].visible  # Error display should be visible
    
    def test_language_validation(self):
        """Test language pair validation."""
        
        # Test same source and target language
        result = self.web_interface._handle_translation_submit(
            file_data=b'mock file data',
            format_type='pdf',
            source_lang='en',
            target_lang='en',
            preserve_layout=True,
            quality_assessment=True,
            quality_threshold=0.8
        )
        
        # Should have validation error
        assert "cannot be the same" in result[0].lower()
    
    def test_progress_feedback(self):
        """Test that progress feedback is provided."""
        
        with patch('src.services.upload_service.FileUploadService') as mock_upload:
            # Mock successful upload
            mock_upload.return_value.upload_file.return_value = (True, Mock(file_id='test_123'), [])
            mock_upload.return_value.get_file_path.return_value.__enter__.return_value = '/tmp/test.pdf'
            
            with patch('src.services.orchestrator_service.TranslationOrchestrator') as mock_orchestrator:
                mock_orchestrator.return_value.submit_translation_job.return_value = 'job_123'
                mock_orchestrator.return_value.get_job_status.return_value = {
                    'status': 'parsing',
                    'overall_progress': 25.0,
                    'current_stage': 'parsing'
                }
                
                result = self.web_interface._handle_translation_submit(
                    file_data=b'mock pdf data',
                    format_type='pdf',
                    source_lang='en',
                    target_lang='fr',
                    preserve_layout=True,
                    quality_assessment=True,
                    quality_threshold=0.8
                )
                
                # Should provide progress feedback
                assert "successfully" in result[0].lower()
                assert result[1].visible  # Progress display should be visible
                assert result[2].visible  # Job info should be visible


if __name__ == "__main__":
    pytest.main([__file__, "-v"])