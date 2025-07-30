"""Translation orchestrator service for coordinating the entire translation pipeline."""

import asyncio
import threading
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

from src.models.document import DocumentStructure
from src.models.layout import AdjustedRegion, LayoutAnalysis
from src.models.quality import QualityScore, QualityReport
from src.parsers.factory import DocumentParserFactory
from src.layout.analysis_engine import DefaultLayoutAnalysisEngine
from src.translation.translation_service import TranslationService
from src.layout.text_fitting import TextFittingEngine, LayoutAdjustmentEngine
from src.layout.reconstruction_engine import DefaultLayoutReconstructionEngine
from src.quality.assessment_service import QualityAssessmentService
from src.services.download_service import DownloadService, DownloadRequest

# Import comprehensive error handling system
from src.errors import (
    DocumentTranslationError,
    FileProcessingError,
    TranslationError,
    LayoutProcessingError,
    ErrorContext,
    ErrorHandler,
    RecoveryManager,
    AutoRecoveryHandler
)


class TranslationStatus(Enum):
    """Status of translation job."""
    PENDING = "pending"
    PARSING = "parsing"
    ANALYZING_LAYOUT = "analyzing_layout"
    TRANSLATING = "translating"
    FITTING_TEXT = "fitting_text"
    RECONSTRUCTING = "reconstructing"
    ASSESSING_QUALITY = "assessing_quality"
    PREPARING_DOWNLOAD = "preparing_download"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TranslationJobError:
    """Represents an error during translation job processing."""
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stage: str = ""
    error_type: str = ""
    message: str = ""
    severity: str = "medium"  # Use string instead of enum for compatibility
    recoverable: bool = True
    recovery_suggestion: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_document_translation_error(cls, error: DocumentTranslationError, stage: str = ""):
        """Create TranslationJobError from DocumentTranslationError."""
        return cls(
            stage=stage or error.context.stage or "",
            error_type=error.category.value,
            message=error.message,
            severity=error.severity.value,
            recoverable=error.recoverable,
            recovery_suggestion="; ".join(error.suggestions),
            details=error.to_dict()
        )


@dataclass
class StageProgress:
    """Progress information for a translation stage."""
    stage_name: str
    status: TranslationStatus
    progress_percentage: float = 0.0
    items_processed: int = 0
    total_items: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[TranslationError] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get stage duration if completed."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if stage is completed."""
        return self.end_time is not None


@dataclass
class TranslationJob:
    """Represents a complete translation job."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    source_language: str = "auto"
    target_language: str = "en"
    format_type: str = ""
    
    # Job state
    status: TranslationStatus = TranslationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Progress tracking
    overall_progress: float = 0.0
    current_stage: str = ""
    stages: Dict[str, StageProgress] = field(default_factory=dict)
    
    # Results
    original_document: Optional[DocumentStructure] = None
    layout_analysis: Optional[List[LayoutAnalysis]] = None
    translated_regions: Dict[str, List[AdjustedRegion]] = field(default_factory=dict)
    quality_report: Optional[QualityReport] = None
    download_link_id: Optional[str] = None
    
    # Error handling
    errors: List[TranslationJobError] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get total job duration if completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if job is completed (successfully or failed)."""
        return self.status in [TranslationStatus.COMPLETED, TranslationStatus.FAILED, TranslationStatus.CANCELLED]
    
    @property
    def has_critical_errors(self) -> bool:
        """Check if job has critical errors."""
        return any(error.severity == "critical" for error in self.errors)


@dataclass
class OrchestrationConfig:
    """Configuration for translation orchestrator."""
    max_concurrent_jobs: int = 3
    job_timeout_minutes: int = 30
    retry_delays: List[int] = field(default_factory=lambda: [5, 15, 30])  # seconds
    cleanup_interval_minutes: int = 60
    max_job_history: int = 100
    enable_quality_assessment: bool = True
    quality_threshold: float = 0.7
    progress_callback_interval: float = 1.0  # seconds


class TranslationOrchestrator:
    """Main orchestrator for coordinating the entire translation pipeline."""
    
    def __init__(self, config: Optional[OrchestrationConfig] = None):
        """Initialize the translation orchestrator.
        
        Args:
            config: Orchestration configuration
        """
        self.config = config or OrchestrationConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize comprehensive error handling system
        self.error_handler = ErrorHandler()
        self.recovery_manager = RecoveryManager()
        self.auto_recovery = AutoRecoveryHandler(self.error_handler, self.recovery_manager)
        
        # Initialize services
        self.parser_factory = DocumentParserFactory()
        self.layout_engine = DefaultLayoutAnalysisEngine()
        self.translation_service = TranslationService()
        self.text_fitting_engine = TextFittingEngine()
        self.layout_adjustment_engine = LayoutAdjustmentEngine()
        self.reconstruction_engine = DefaultLayoutReconstructionEngine()
        self.quality_service = QualityAssessmentService()
        self.download_service = DownloadService()
        
        # Job management
        self.active_jobs: Dict[str, TranslationJob] = {}
        self.job_history: List[TranslationJob] = []
        self.job_semaphore = threading.Semaphore(self.config.max_concurrent_jobs)
        
        # Progress callbacks
        self.progress_callbacks: List[Callable[[TranslationJob], None]] = []
        
        # Background tasks
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        
        # Start background tasks
        self._start_cleanup_thread()
    
    def submit_translation_job(self, file_path: str, source_language: str = "auto",
                             target_language: str = "en", format_type: str = "") -> str:
        """Submit a new translation job.
        
        Args:
            file_path: Path to the document file
            source_language: Source language code
            target_language: Target language code
            format_type: Document format type
            
        Returns:
            Job ID for tracking
        """
        job = TranslationJob(
            file_path=file_path,
            source_language=source_language,
            target_language=target_language,
            format_type=format_type
        )
        
        # Initialize stages
        self._initialize_job_stages(job)
        
        # Store job
        self.active_jobs[job.job_id] = job
        
        # Start processing in background
        threading.Thread(
            target=self._process_job,
            args=(job,),
            daemon=True
        ).start()
        
        self.logger.info(f"Submitted translation job {job.job_id}")
        return job.job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a translation job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status information or None if not found
        """
        job = self.active_jobs.get(job_id)
        if not job:
            # Check job history
            for historical_job in self.job_history:
                if historical_job.job_id == job_id:
                    job = historical_job
                    break
        
        if not job:
            return None
        
        return {
            'job_id': job.job_id,
            'status': job.status.value,
            'overall_progress': job.overall_progress,
            'current_stage': job.current_stage,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'duration': str(job.duration) if job.duration else None,
            'source_language': job.source_language,
            'target_language': job.target_language,
            'format_type': job.format_type,
            'error_count': len(job.errors),
            'critical_errors': job.has_critical_errors,
            'retry_count': job.retry_count,
            'download_link_id': job.download_link_id,
            'stages': {
                name: {
                    'status': stage.status.value,
                    'progress': stage.progress_percentage,
                    'items_processed': stage.items_processed,
                    'total_items': stage.total_items,
                    'duration': str(stage.duration) if stage.duration else None,
                    'error_count': len(stage.errors)
                }
                for name, stage in job.stages.items()
            }
        }
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a translation job.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if job was cancelled successfully
        """
        job = self.active_jobs.get(job_id)
        if not job or job.is_completed:
            return False
        
        job.status = TranslationStatus.CANCELLED
        job.completed_at = datetime.now()
        
        self.logger.info(f"Cancelled translation job {job_id}")
        return True
    
    def retry_job(self, job_id: str) -> bool:
        """Retry a failed translation job.
        
        Args:
            job_id: Job ID to retry
            
        Returns:
            True if job was queued for retry
        """
        job = self.active_jobs.get(job_id)
        if not job or job.status != TranslationStatus.FAILED:
            return False
        
        if job.retry_count >= job.max_retries:
            self.logger.warning(f"Job {job_id} has exceeded maximum retries")
            return False
        
        job.retry_count += 1
        job.status = TranslationStatus.PENDING
        job.errors.clear()
        
        # Reset stages
        for stage in job.stages.values():
            stage.status = TranslationStatus.PENDING
            stage.progress_percentage = 0.0
            stage.start_time = None
            stage.end_time = None
            stage.errors.clear()
        
        # Start processing again
        threading.Thread(
            target=self._process_job,
            args=(job,),
            daemon=True
        ).start()
        
        self.logger.info(f"Retrying translation job {job_id} (attempt {job.retry_count})")
        return True
    
    def add_progress_callback(self, callback: Callable[[TranslationJob], None]):
        """Add a progress callback function.
        
        Args:
            callback: Function to call with job updates
        """
        self.progress_callbacks.append(callback)
    
    async def _handle_job_error(self, job: TranslationJob, error: Exception, 
                               stage: str) -> bool:
        """Handle job error with comprehensive error handling and recovery.
        
        Args:
            job: Translation job
            error: Exception that occurred
            stage: Current processing stage
            
        Returns:
            True if error was recovered, False otherwise
        """
        # Create error context
        context = ErrorContext(
            job_id=job.job_id,
            file_path=job.file_path,
            stage=stage,
            component="orchestrator",
            metadata={
                'source_language': job.source_language,
                'target_language': job.target_language,
                'format_type': job.format_type,
                'retry_count': job.retry_count
            }
        )
        
        # Create job context for recovery
        job_context = {
            'job_id': job.job_id,
            'stage': stage,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'quality_threshold': self.config.quality_threshold,
            'timeout': self.config.job_timeout_minutes * 60
        }
        
        # Handle error with recovery
        result = await self.auto_recovery.handle_error_with_recovery(
            error, context, job_context
        )
        
        # Create job error record
        if isinstance(error, DocumentTranslationError):
            job_error = TranslationJobError.from_document_translation_error(error, stage)
        else:
            job_error = TranslationJobError(
                stage=stage,
                error_type="unknown",
                message=str(error),
                severity="medium",
                recoverable=result['recovery_successful']
            )
        
        # Add error to job
        job.errors.append(job_error)
        
        # Update stage with error
        if stage in job.stages:
            job.stages[stage].errors.append(job_error)
        
        # Log comprehensive error information
        self.logger.error(
            f"Job {job.job_id} error in stage {stage}: {error}. "
            f"Recovery attempted: {result['recovery_attempted']}, "
            f"Recovery successful: {result['recovery_successful']}"
        )
        
        return result['recovery_successful']
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics.
        
        Returns:
            Dictionary with orchestrator statistics
        """
        active_count = len(self.active_jobs)
        completed_count = len([j for j in self.job_history if j.status == TranslationStatus.COMPLETED])
        failed_count = len([j for j in self.job_history if j.status == TranslationStatus.FAILED])
        
        # Get error handling statistics
        error_stats = self.error_handler.get_error_statistics()
        recovery_stats = self.recovery_manager.get_recovery_statistics()
        
        return {
            'active_jobs': active_count,
            'completed_jobs': completed_count,
            'failed_jobs': failed_count,
            'total_jobs_processed': len(self.job_history),
            'max_concurrent_jobs': self.config.max_concurrent_jobs,
            'job_timeout_minutes': self.config.job_timeout_minutes,
            'average_processing_time': self._calculate_average_processing_time(),
            'success_rate': self._calculate_success_rate(),
            'error_handling': error_stats,
            'recovery_system': recovery_stats,
            'queue_length': len([j for j in self.active_jobs.values() 
                               if j.status == TranslationStatus.PENDING])
        }
    
    def _initialize_job_stages(self, job: TranslationJob):
        """Initialize job stages with progress tracking."""
        stage_names = [
            "parsing",
            "analyzing_layout", 
            "translating",
            "fitting_text",
            "reconstructing",
            "assessing_quality",
            "preparing_download"
        ]
        
        for stage_name in stage_names:
            job.stages[stage_name] = StageProgress(
                stage_name=stage_name,
                status=TranslationStatus.PENDING
            )
    
    def _process_job(self, job: TranslationJob):
        """Process a translation job through all stages.
        
        Args:
            job: Translation job to process
        """
        try:
            # Acquire semaphore for concurrent job limiting
            if not self.job_semaphore.acquire(blocking=False):
                self._handle_job_error(job, "orchestration", "concurrency_limit", 
                                     "Too many concurrent jobs", ErrorSeverity.MEDIUM)
                return
            
            try:
                job.started_at = datetime.now()
                job.status = TranslationStatus.PARSING
                
                # Stage 1: Parse document
                if not self._execute_parsing_stage(job):
                    return
                
                # Stage 2: Analyze layout
                if not self._execute_layout_analysis_stage(job):
                    return
                
                # Stage 3: Translate content
                if not self._execute_translation_stage(job):
                    return
                
                # Stage 4: Fit text and adjust layout
                if not self._execute_text_fitting_stage(job):
                    return
                
                # Stage 5: Reconstruct document
                if not self._execute_reconstruction_stage(job):
                    return
                
                # Stage 6: Assess quality (optional)
                if self.config.enable_quality_assessment:
                    if not self._execute_quality_assessment_stage(job):
                        return
                
                # Stage 7: Prepare download
                if not self._execute_download_preparation_stage(job):
                    return
                
                # Job completed successfully
                job.status = TranslationStatus.COMPLETED
                job.completed_at = datetime.now()
                job.overall_progress = 100.0
                
                self.logger.info(f"Translation job {job.job_id} completed successfully")
                
            finally:
                self.job_semaphore.release()
                
        except Exception as e:
            self._handle_job_error(job, "orchestration", "unexpected_error", 
                                 f"Unexpected error: {str(e)}", ErrorSeverity.CRITICAL)
        finally:
            # Move to history and notify callbacks
            self._finalize_job(job)
    
    def _execute_parsing_stage(self, job: TranslationJob) -> bool:
        """Execute document parsing stage."""
        stage = job.stages["parsing"]
        stage.status = TranslationStatus.PARSING
        stage.start_time = datetime.now()
        job.current_stage = "parsing"
        
        try:
            # Detect format if not provided
            if not job.format_type:
                job.format_type = self._detect_document_format(job.file_path)
            
            # Parse document
            parser = self.parser_factory.create_parser(job.format_type)
            job.original_document = parser.parse(job.file_path)
            
            stage.progress_percentage = 100.0
            stage.items_processed = 1
            stage.total_items = 1
            stage.end_time = datetime.now()
            
            job.overall_progress = 15.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "parsing_error", str(e), ErrorSeverity.HIGH)
            return False
    
    def _execute_layout_analysis_stage(self, job: TranslationJob) -> bool:
        """Execute layout analysis stage."""
        stage = job.stages["analyzing_layout"]
        stage.status = TranslationStatus.ANALYZING_LAYOUT
        stage.start_time = datetime.now()
        job.current_stage = "analyzing_layout"
        
        try:
            job.layout_analysis = self.layout_engine.analyze_layout(job.original_document)
            
            stage.progress_percentage = 100.0
            stage.items_processed = len(job.original_document.pages)
            stage.total_items = len(job.original_document.pages)
            stage.end_time = datetime.now()
            
            job.overall_progress = 25.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "layout_analysis_error", str(e), ErrorSeverity.HIGH)
            return False
    
    def _execute_translation_stage(self, job: TranslationJob) -> bool:
        """Execute translation stage."""
        stage = job.stages["translating"]
        stage.status = TranslationStatus.TRANSLATING
        stage.start_time = datetime.now()
        job.current_stage = "translating"
        
        try:
            total_regions = sum(len(page.text_regions) for page in job.original_document.pages)
            stage.total_items = total_regions
            processed_regions = 0
            
            for page_idx, page in enumerate(job.original_document.pages):
                page_key = str(page.page_number)
                page_translated_regions = []
                
                for region in page.text_regions:
                    # Translate text region
                    translated_text = self.translation_service.translate_text(
                        region.text_content,
                        job.source_language,
                        job.target_language
                    )
                    
                    # Fit translated text
                    adjusted_region = self.text_fitting_engine.fit_text_to_region(
                        region, translated_text
                    )
                    
                    page_translated_regions.append(adjusted_region)
                    processed_regions += 1
                    
                    # Update progress
                    stage.progress_percentage = (processed_regions / total_regions) * 100
                    stage.items_processed = processed_regions
                    
                    if processed_regions % 5 == 0:  # Update every 5 regions
                        job.overall_progress = 25.0 + (stage.progress_percentage * 0.4)
                        self._notify_progress_callbacks(job)
                
                job.translated_regions[page_key] = page_translated_regions
            
            stage.end_time = datetime.now()
            job.overall_progress = 65.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "translation_error", str(e), ErrorSeverity.HIGH)
            return False
    
    def _execute_text_fitting_stage(self, job: TranslationJob) -> bool:
        """Execute text fitting and layout adjustment stage."""
        stage = job.stages["fitting_text"]
        stage.status = TranslationStatus.FITTING_TEXT
        stage.start_time = datetime.now()
        job.current_stage = "fitting_text"
        
        try:
            total_pages = len(job.translated_regions)
            stage.total_items = total_pages
            
            for page_idx, (page_key, adjusted_regions) in enumerate(job.translated_regions.items()):
                # Detect and resolve layout conflicts
                conflicts = self.layout_adjustment_engine.detect_layout_conflicts(adjusted_regions)
                
                if conflicts:
                    resolutions = self.layout_adjustment_engine.resolve_conflicts(
                        conflicts, adjusted_regions
                    )
                    # Apply resolutions (simplified for this implementation)
                
                stage.items_processed = page_idx + 1
                stage.progress_percentage = ((page_idx + 1) / total_pages) * 100
                
                job.overall_progress = 65.0 + (stage.progress_percentage * 0.1)
                self._notify_progress_callbacks(job)
            
            stage.end_time = datetime.now()
            job.overall_progress = 75.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "text_fitting_error", str(e), ErrorSeverity.MEDIUM)
            return False
    
    def _execute_reconstruction_stage(self, job: TranslationJob) -> bool:
        """Execute document reconstruction stage."""
        stage = job.stages["reconstructing"]
        stage.status = TranslationStatus.RECONSTRUCTING
        stage.start_time = datetime.now()
        job.current_stage = "reconstructing"
        
        try:
            # This stage is handled in download preparation
            stage.progress_percentage = 100.0
            stage.items_processed = 1
            stage.total_items = 1
            stage.end_time = datetime.now()
            
            job.overall_progress = 85.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "reconstruction_error", str(e), ErrorSeverity.HIGH)
            return False
    
    def _execute_quality_assessment_stage(self, job: TranslationJob) -> bool:
        """Execute quality assessment stage."""
        stage = job.stages["assessing_quality"]
        stage.status = TranslationStatus.ASSESSING_QUALITY
        stage.start_time = datetime.now()
        job.current_stage = "assessing_quality"
        
        try:
            # Assess overall translation quality
            page_assessments = []
            
            for page_analysis in job.layout_analysis:
                page_key = str(page_analysis.page_number)
                adjusted_regions = job.translated_regions.get(page_key, [])
                
                quality_score = self.quality_service.assess_layout_preservation(
                    page_analysis, adjusted_regions
                )
                page_assessments.append(quality_score)
            
            # Generate quality report
            job.quality_report = self.quality_service.generate_quality_report(
                job.original_document, page_assessments, page_assessments[0] if page_assessments else None
            )
            
            stage.progress_percentage = 100.0
            stage.items_processed = len(page_assessments)
            stage.total_items = len(page_assessments)
            stage.end_time = datetime.now()
            
            job.overall_progress = 90.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "quality_assessment_error", str(e), ErrorSeverity.LOW)
            # Quality assessment failure is not critical
            return True
    
    def _execute_download_preparation_stage(self, job: TranslationJob) -> bool:
        """Execute download preparation stage."""
        stage = job.stages["preparing_download"]
        stage.status = TranslationStatus.PREPARING_DOWNLOAD
        stage.start_time = datetime.now()
        job.current_stage = "preparing_download"
        
        try:
            # Prepare download request
            download_request = DownloadRequest(
                request_id=job.job_id,
                document=job.original_document,
                translated_regions=job.translated_regions,
                target_format=job.format_type,
                filename_prefix="translated"
            )
            
            # Prepare download
            download_result = self.download_service.prepare_download(download_request)
            
            if download_result.success:
                job.download_link_id = download_result.download_link.link_id
            else:
                raise Exception(download_result.error_message)
            
            stage.progress_percentage = 100.0
            stage.items_processed = 1
            stage.total_items = 1
            stage.end_time = datetime.now()
            
            job.overall_progress = 100.0
            self._notify_progress_callbacks(job)
            
            return True
            
        except Exception as e:
            self._handle_stage_error(job, stage, "download_preparation_error", str(e), ErrorSeverity.HIGH)
            return False 
   
    def _detect_document_format(self, file_path: str) -> str:
        """Detect document format from file path."""
        extension = file_path.lower().split('.')[-1]
        format_mapping = {
            'pdf': 'pdf',
            'docx': 'docx',
            'doc': 'docx',
            'epub': 'epub'
        }
        return format_mapping.get(extension, 'pdf')
    
    def _handle_job_error(self, job: TranslationJob, stage: str, error_type: str,
                         message: str, severity: ErrorSeverity):
        """Handle job-level error."""
        error = TranslationError(
            stage=stage,
            error_type=error_type,
            message=message,
            severity=severity,
            recoverable=severity != ErrorSeverity.CRITICAL
        )
        
        job.errors.append(error)
        job.status = TranslationStatus.FAILED
        job.completed_at = datetime.now()
        
        self.logger.error(f"Job {job.job_id} failed at stage {stage}: {message}")
    
    def _handle_stage_error(self, job: TranslationJob, stage: StageProgress,
                          error_type: str, message: str, severity: ErrorSeverity):
        """Handle stage-level error."""
        error = TranslationError(
            stage=stage.stage_name,
            error_type=error_type,
            message=message,
            severity=severity
        )
        
        stage.errors.append(error)
        job.errors.append(error)
        
        stage.end_time = datetime.now()
        job.status = TranslationStatus.FAILED
        job.completed_at = datetime.now()
        
        self.logger.error(f"Job {job.job_id} stage {stage.stage_name} failed: {message}")
    
    def _notify_progress_callbacks(self, job: TranslationJob):
        """Notify all progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                callback(job)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    def _finalize_job(self, job: TranslationJob):
        """Finalize job and move to history."""
        # Remove from active jobs
        if job.job_id in self.active_jobs:
            del self.active_jobs[job.job_id]
        
        # Add to history
        self.job_history.append(job)
        
        # Limit history size
        if len(self.job_history) > self.config.max_job_history:
            self.job_history = self.job_history[-self.config.max_job_history:]
        
        # Final progress notification
        self._notify_progress_callbacks(job)
    
    def _calculate_average_processing_time(self) -> Optional[float]:
        """Calculate average processing time for completed jobs."""
        completed_jobs = [j for j in self.job_history if j.duration]
        if not completed_jobs:
            return None
        
        total_seconds = sum(job.duration.total_seconds() for job in completed_jobs)
        return total_seconds / len(completed_jobs)
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate for processed jobs."""
        if not self.job_history:
            return 0.0
        
        successful_jobs = len([j for j in self.job_history if j.status == TranslationStatus.COMPLETED])
        return (successful_jobs / len(self.job_history)) * 100.0
    
    def _start_cleanup_thread(self):
        """Start the cleanup thread."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
    
    def _cleanup_worker(self):
        """Worker thread for periodic cleanup."""
        while not self.shutdown_event.wait(self.config.cleanup_interval_minutes * 60):
            try:
                self._cleanup_expired_jobs()
            except Exception as e:
                self.logger.error(f"Cleanup worker error: {e}")
    
    def _cleanup_expired_jobs(self):
        """Clean up expired and old jobs."""
        current_time = datetime.now()
        timeout_threshold = timedelta(minutes=self.config.job_timeout_minutes)
        
        # Find expired active jobs
        expired_job_ids = []
        for job_id, job in self.active_jobs.items():
            if job.started_at and (current_time - job.started_at) > timeout_threshold:
                expired_job_ids.append(job_id)
        
        # Cancel expired jobs
        for job_id in expired_job_ids:
            job = self.active_jobs[job_id]
            job.status = TranslationStatus.FAILED
            job.completed_at = current_time
            
            error = TranslationError(
                stage="orchestration",
                error_type="timeout",
                message=f"Job timed out after {self.config.job_timeout_minutes} minutes",
                severity=ErrorSeverity.HIGH
            )
            job.errors.append(error)
            
            self._finalize_job(job)
            self.logger.warning(f"Job {job_id} timed out and was cancelled")
    
    def shutdown(self):
        """Shutdown the orchestrator and cleanup resources."""
        self.logger.info("Shutting down translation orchestrator")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Wait for cleanup thread
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        # Cancel all active jobs
        for job_id in list(self.active_jobs.keys()):
            self.cancel_job(job_id)
        
        # Shutdown services
        self.download_service.shutdown()
        
        self.logger.info("Translation orchestrator shutdown complete")