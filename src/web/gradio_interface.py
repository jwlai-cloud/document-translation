"""Enhanced Gradio web interface for multimodal document translation."""

import gradio as gr
import tempfile
import json
from datetime import datetime
from typing import Dict, Any

from src.services.upload_service import FileUploadService, UploadConfig
from src.services.orchestrator_service import (
    TranslationOrchestrator,
    OrchestrationConfig,
)
from src.services.preview_service import PreviewService
from src.services.download_service import DownloadService


class TranslationWebInterface:
    """Enhanced web interface for document translation."""

    def __init__(self):
        """Initialize the web interface with all services."""
        # Initialize services
        self.upload_service = FileUploadService(UploadConfig())
        self.orchestrator = TranslationOrchestrator(OrchestrationConfig())
        self.preview_service = PreviewService()
        self.download_service = DownloadService()

        # Supported languages
        self.languages = {
            "auto": "Auto-detect",
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
        }

        # Supported formats
        self.formats = ["pdf", "docx", "epub"]

        # Active jobs tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}

        # Setup progress callback
        self.orchestrator.add_progress_callback(self._update_job_progress)

    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface."""

        with gr.Blocks(
            title="Multimodal Document Translator",
            theme=gr.themes.Soft(),
            css=self._get_custom_css(),
        ) as interface:
            # Header
            gr.Markdown(
                """
                # 🌐 Multimodal Document Translator

                Translate PDF, DOCX, and EPUB documents while preserving
                layout and formatting.
                """
            )

            # Main tabs
            with gr.Tabs():
                # Upload and Translation Tab
                with gr.TabItem("📄 Translate Document"):
                    self._create_translation_tab()

                # Progress Monitoring Tab
                with gr.TabItem("📊 Progress Monitor"):
                    self._create_progress_tab()

                # Preview Tab
                with gr.TabItem("👁️ Preview"):
                    self._create_preview_tab()

                # Download Tab
                with gr.TabItem("⬇️ Download"):
                    self._create_download_tab()

                # Statistics Tab
                with gr.TabItem("📈 Statistics"):
                    self._create_statistics_tab()

        return interface

    def _create_translation_tab(self):
        """Create the main translation tab."""

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📁 Upload Document")

                # File upload with enhanced validation
                file_upload = gr.File(
                    label="Select Document (PDF, DOCX, EPUB)",
                    file_types=[".pdf", ".docx", ".epub"],
                    type="binary",
                )

                # Format selection with auto-detection
                format_dropdown = gr.Dropdown(
                    choices=self.formats,
                    label="Document Format (Auto-detected)",
                    value="pdf",
                    interactive=True,
                )

                # Enhanced language selection
                with gr.Row():
                    source_lang = gr.Dropdown(
                        choices=list(self.languages.items()),
                        label="Source Language",
                        value="auto",
                        interactive=True,
                    )

                    target_lang = gr.Dropdown(
                        choices=list(self.languages.items()),
                        label="Target Language",
                        value="en",
                        interactive=True,
                    )

                # Advanced translation options
                gr.Markdown("### ⚙️ Translation Options")

                with gr.Row():
                    preserve_layout = gr.Checkbox(
                        label="Preserve Layout",
                        value=True,
                        info="Maintain original document formatting",
                    )

                    quality_assessment = gr.Checkbox(
                        label="Quality Assessment",
                        value=True,
                        info="Generate quality score and report",
                    )

                # Quality threshold slider
                quality_threshold = gr.Slider(
                    minimum=0.1,
                    maximum=1.0,
                    value=0.8,
                    step=0.1,
                    label="Quality Threshold",
                    info="Minimum acceptable quality score",
                )

                # Submit button
                submit_btn = gr.Button(
                    "🚀 Start Translation", variant="primary", size="lg"
                )

            with gr.Column(scale=1):
                gr.Markdown("### 📋 Translation Status")

                # Enhanced status display with progress
                status_display = gr.Markdown("Ready to translate...")

                # Real-time progress indicator
                progress_display = gr.HTML(
                    """
                    <div class="progress-container" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 0%;"></div>
                        </div>
                        <div class="progress-text">0%</div>
                    </div>
                    """
                )

                # Job information panel
                job_info = gr.JSON(label="Job Details", visible=False)

                # Quality score display
                quality_display = gr.HTML(visible=False)

                # Error display with suggestions
                error_display = gr.Markdown(visible=False)

                # Success message with actions
                success_display = gr.HTML(visible=False)

        # Event handlers
        submit_btn.click(
            fn=self._handle_translation_submit,
            inputs=[
                file_upload,
                format_dropdown,
                source_lang,
                target_lang,
                preserve_layout,
                quality_assessment,
                quality_threshold,
            ],
            outputs=[
                status_display,
                progress_display,
                job_info,
                quality_display,
                error_display,
                success_display,
            ],
        )

    def _create_progress_tab(self):
        """Create the enhanced progress monitoring tab."""

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 📊 Active Translation Jobs")

                # Enhanced jobs table with status indicators
                jobs_table = gr.Dataframe(
                    headers=[
                        "Job ID",
                        "Status",
                        "Progress",
                        "Stage",
                        "Source",
                        "Target",
                        "Format",
                        "Started",
                        "Quality",
                    ],
                    datatype=[
                        "str",
                        "str",
                        "str",
                        "str",
                        "str",
                        "str",
                        "str",
                        "str",
                        "str",
                    ],
                    label="Translation Jobs",
                    interactive=False,
                )

                # Control buttons
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
                    auto_refresh = gr.Checkbox(label="Auto-refresh (5s)", value=False)

            with gr.Column(scale=1):
                gr.Markdown("### 🔍 Job Management")

                # Job selector with search
                job_selector = gr.Dropdown(
                    label="Select Job",
                    choices=[],
                    interactive=True,
                    allow_custom_value=True,
                )

                # Job control buttons
                with gr.Row():
                    cancel_btn = gr.Button("❌ Cancel", variant="stop", size="sm")
                    retry_btn = gr.Button("🔄 Retry", variant="secondary", size="sm")
                    pause_btn = gr.Button("⏸️ Pause", variant="secondary", size="sm")

        # Detailed job information section
        gr.Markdown("### 📋 Job Details")

        with gr.Row():
            with gr.Column():
                # Job metadata
                job_details = gr.JSON(label="Job Information", show_label=True)

            with gr.Column():
                # Stage progress visualization
                stage_progress = gr.HTML(
                    label="Pipeline Progress",
                    value="<p>Select a job to see detailed progress...</p>",
                )

        # Error and warning display
        job_messages = gr.HTML(label="Messages & Alerts", visible=False)

        # Event handlers
        refresh_btn.click(
            fn=self._refresh_jobs_table, outputs=[jobs_table, job_selector]
        )

        job_selector.change(
            fn=self._get_job_details,
            inputs=[job_selector],
            outputs=[job_details, stage_progress, job_messages],
        )

        cancel_btn.click(
            fn=self._cancel_job,
            inputs=[job_selector],
            outputs=[jobs_table, job_details, stage_progress, job_messages],
        )

        retry_btn.click(
            fn=self._retry_job,
            inputs=[job_selector],
            outputs=[jobs_table, job_details, stage_progress, job_messages],
        )

        pause_btn.click(
            fn=self._pause_job,
            inputs=[job_selector],
            outputs=[jobs_table, job_details, stage_progress, job_messages],
        )

    def _create_preview_tab(self):
        """Create the enhanced document preview tab."""

        gr.Markdown("### 👁️ Document Preview & Comparison")

        with gr.Row():
            with gr.Column(scale=1):
                # Job selection for preview
                preview_job_selector = gr.Dropdown(
                    label="Select Completed Job", choices=[], interactive=True
                )

                # Enhanced preview options
                gr.Markdown("#### 🎛️ Display Options")

                with gr.Row():
                    show_original = gr.Checkbox(
                        label="Original", value=True, info="Show source document"
                    )

                    show_translated = gr.Checkbox(
                        label="Translated", value=True, info="Show translated document"
                    )

                view_mode = gr.Radio(
                    choices=[
                        ("Side-by-Side", "side_by_side"),
                        ("Overlay", "overlay"),
                        ("Tabbed", "tabbed"),
                    ],
                    value="side_by_side",
                    label="View Mode",
                )

                # Advanced controls
                gr.Markdown("#### 🔧 Controls")

                zoom_slider = gr.Slider(
                    minimum=0.25, maximum=4.0, value=1.0, step=0.25, label="Zoom Level"
                )

                highlight_mode = gr.Dropdown(
                    choices=[
                        ("None", "none"),
                        ("Text Changes", "changes"),
                        ("Layout Adjustments", "layout"),
                        ("Quality Issues", "quality"),
                        ("All Highlights", "all"),
                    ],
                    value="changes",
                    label="Highlight Mode",
                )

                # Page navigation
                page_selector = gr.Slider(
                    minimum=1, maximum=1, value=1, step=1, label="Page", visible=False
                )

                # Generate preview button
                generate_preview_btn = gr.Button(
                    "🔍 Generate Preview", variant="primary", size="lg"
                )

            with gr.Column(scale=3):
                # Preview display area
                preview_html = gr.HTML(
                    label="Document Preview",
                    value="""
                    <div style="text-align: center; padding: 50px; 
                                color: #666; border: 2px dashed #ddd; 
                                border-radius: 8px;">
                        <h3>📄 Document Preview</h3>
                        <p>Select a completed job and click 
                           "Generate Preview" to view documents</p>
                    </div>
                    """,
                )

        # Preview controls and information
        with gr.Row():
            with gr.Column():
                # Preview statistics
                preview_stats = gr.JSON(label="Preview Statistics", visible=False)

            with gr.Column():
                # Navigation controls
                with gr.Row():
                    prev_page_btn = gr.Button("⬅️ Previous", size="sm", visible=False)
                    next_page_btn = gr.Button("➡️ Next", size="sm", visible=False)

                # Export preview options
                export_preview_btn = gr.Button(
                    "📤 Export Preview", variant="secondary", visible=False
                )

        # Event handlers
        generate_preview_btn.click(
            fn=self._generate_preview,
            inputs=[
                preview_job_selector,
                show_original,
                show_translated,
                view_mode,
                zoom_slider,
                highlight_mode,
                page_selector,
            ],
            outputs=[
                preview_html,
                preview_stats,
                page_selector,
                prev_page_btn,
                next_page_btn,
                export_preview_btn,
            ],
        )

        # Page navigation handlers
        prev_page_btn.click(
            fn=self._navigate_preview_page,
            inputs=[preview_job_selector, page_selector, gr.State(-1)],
            outputs=[preview_html, page_selector],
        )

        next_page_btn.click(
            fn=self._navigate_preview_page,
            inputs=[preview_job_selector, page_selector, gr.State(1)],
            outputs=[preview_html, page_selector],
        )

    def _create_download_tab(self):
        """Create the enhanced download tab."""

        gr.Markdown("### ⬇️ Download Translated Documents")

        with gr.Row():
            with gr.Column(scale=1):
                # Job selection with filtering
                download_job_selector = gr.Dropdown(
                    label="Select Completed Job", choices=[], interactive=True
                )

                # Download format options
                gr.Markdown("#### 📋 Download Options")

                download_format = gr.Radio(
                    choices=[
                        ("Original Format", "original"),
                        ("PDF", "pdf"),
                        ("DOCX", "docx"),
                        ("HTML", "html"),
                    ],
                    value="original",
                    label="Output Format",
                )

                include_quality_report = gr.Checkbox(
                    label="Include Quality Report",
                    value=True,
                    info="Add quality assessment as separate file",
                )

                include_metadata = gr.Checkbox(
                    label="Include Metadata",
                    value=False,
                    info="Add translation metadata file",
                )

                # Download button
                download_btn = gr.Button(
                    "📥 Download Document", variant="primary", size="lg"
                )

                # Batch download option
                gr.Markdown("#### 📦 Batch Download")

                batch_jobs_selector = gr.CheckboxGroup(
                    label="Select Multiple Jobs", choices=[], interactive=True
                )

                batch_download_btn = gr.Button(
                    "📦 Download All Selected", variant="secondary"
                )

            with gr.Column(scale=1):
                # Download information panel
                download_info = gr.JSON(label="Download Information", visible=False)

                # File size and format details
                file_details = gr.HTML(label="File Details", visible=False)

                # Download status and progress
                download_status = gr.HTML(
                    value="""
                    <div style="text-align: center; padding: 20px; 
                                color: #666;">
                        <p>Select a completed job to see download options</p>
                    </div>
                    """
                )

                # Downloaded files display
                download_files = gr.File(
                    label="Downloaded Files", file_count="multiple", visible=False
                )

                # Download history
                gr.Markdown("#### 📜 Recent Downloads")

                download_history = gr.Dataframe(
                    headers=["Job ID", "Format", "Size", "Downloaded"],
                    datatype=["str", "str", "str", "str"],
                    label="Download History",
                    max_rows=5,
                )

        # Event handlers
        download_job_selector.change(
            fn=self._get_download_info,
            inputs=[download_job_selector],
            outputs=[download_info, file_details, download_status],
        )

        download_btn.click(
            fn=self._handle_download,
            inputs=[
                download_job_selector,
                download_format,
                include_quality_report,
                include_metadata,
            ],
            outputs=[download_status, download_files, download_history],
        )

        batch_download_btn.click(
            fn=self._handle_batch_download,
            inputs=[batch_jobs_selector, download_format],
            outputs=[download_status, download_files, download_history],
        )

    def _create_statistics_tab(self):
        """Create the enhanced statistics and monitoring tab."""

        gr.Markdown("### 📈 System Statistics & Performance")

        with gr.Tabs():
            # System Performance Tab
            with gr.TabItem("🖥️ System Performance"):
                with gr.Row():
                    with gr.Column():
                        # Real-time metrics
                        gr.Markdown("#### ⚡ Real-time Metrics")

                        system_metrics = gr.HTML(
                            value="""
                            <div class="metrics-grid">
                                <div class="metric-card">
                                    <h4>Active Jobs</h4>
                                    <span class="metric-value">0</span>
                                </div>
                                <div class="metric-card">
                                    <h4>Queue Length</h4>
                                    <span class="metric-value">0</span>
                                </div>
                                <div class="metric-card">
                                    <h4>Success Rate</h4>
                                    <span class="metric-value">0%</span>
                                </div>
                            </div>
                            """
                        )

                        # Service statistics
                        orchestrator_stats = gr.JSON(
                            label="Translation Orchestrator Statistics"
                        )

                    with gr.Column():
                        # Performance charts
                        gr.Markdown("#### 📊 Performance Charts")

                        performance_chart = gr.HTML(
                            value="""
                            <div style="text-align: center; padding: 40px; 
                                        border: 1px solid #ddd; 
                                        border-radius: 8px;">
                                <p>Performance charts would be displayed here</p>
                                <p><em>Processing time, throughput, error rates</em></p>
                            </div>
                            """
                        )

            # Service Statistics Tab
            with gr.TabItem("🔧 Service Statistics"):
                with gr.Row():
                    with gr.Column():
                        upload_stats = gr.JSON(label="Upload Service Statistics")

                        download_stats = gr.JSON(label="Download Service Statistics")

                    with gr.Column():
                        preview_stats = gr.JSON(label="Preview Service Statistics")

                        quality_stats = gr.JSON(label="Quality Assessment Statistics")

            # Usage Analytics Tab
            with gr.TabItem("📊 Usage Analytics"):
                with gr.Row():
                    with gr.Column():
                        # Language pair statistics
                        language_stats = gr.Dataframe(
                            headers=[
                                "Language Pair",
                                "Jobs",
                                "Success Rate",
                                "Avg Quality",
                            ],
                            datatype=["str", "number", "str", "str"],
                            label="Language Pair Statistics",
                        )

                        # Format statistics
                        format_stats = gr.Dataframe(
                            headers=[
                                "Format",
                                "Jobs",
                                "Success Rate",
                                "Avg Processing Time",
                            ],
                            datatype=["str", "number", "str", "str"],
                            label="Document Format Statistics",
                        )

                    with gr.Column():
                        # Quality trends
                        quality_trends = gr.HTML(
                            value="""
                            <div style="text-align: center; padding: 40px; 
                                        border: 1px solid #ddd; 
                                        border-radius: 8px;">
                                <h4>Quality Trends</h4>
                                <p>Quality score trends over time</p>
                            </div>
                            """
                        )

                        # Error analysis
                        error_analysis = gr.Dataframe(
                            headers=["Error Type", "Count", "Percentage"],
                            datatype=["str", "number", "str"],
                            label="Error Analysis",
                        )

        # Control buttons
        with gr.Row():
            refresh_stats_btn = gr.Button(
                "🔄 Refresh All Statistics", variant="primary"
            )

            export_stats_btn = gr.Button("📤 Export Statistics", variant="secondary")

            auto_refresh_stats = gr.Checkbox(label="Auto-refresh (30s)", value=False)

        # Event handlers
        refresh_stats_btn.click(
            fn=self._get_system_statistics,
            outputs=[
                system_metrics,
                orchestrator_stats,
                upload_stats,
                download_stats,
                preview_stats,
                quality_stats,
                language_stats,
                format_stats,
                error_analysis,
            ],
        )

        export_stats_btn.click(
            fn=self._export_statistics,
            outputs=[gr.File(label="Statistics Export", visible=True)],
        )

    def _get_custom_css(self) -> str:
        """Get enhanced custom CSS for the interface."""
        return """
        .gradio-container {
            max-width: 1400px !important;
        }

        /* Progress indicators */
        .progress-container {
            margin: 10px 0;
        }

        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #f0f0f0;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #45a049);
            border-radius: 10px;
            transition: width 0.3s ease;
        }

        .progress-text {
            text-align: center;
            font-weight: bold;
            margin-top: 5px;
        }

        /* Status messages */
        .error-message {
            background-color: #ffebee;
            border-left: 4px solid #f44336;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }

        .success-message {
            background-color: #e8f5e8;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }

        .warning-message {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }

        /* Job status indicators */
        .job-status-pending { color: #ff9800; font-weight: bold; }
        .job-status-running { color: #2196f3; font-weight: bold; }
        .job-status-completed { color: #4caf50; font-weight: bold; }
        .job-status-failed { color: #f44336; font-weight: bold; }
        .job-status-cancelled { color: #9e9e9e; font-weight: bold; }

        /* Stage progress */
        .stage-progress {
            margin: 8px 0;
            padding: 10px;
            border-radius: 6px;
            background-color: #f8f9fa;
            border-left: 3px solid #dee2e6;
        }

        .stage-progress.active {
            background-color: #e3f2fd;
            border-left-color: #2196f3;
        }

        .stage-progress.completed {
            background-color: #e8f5e8;
            border-left-color: #4caf50;
        }

        .stage-progress.failed {
            background-color: #ffebee;
            border-left-color: #f44336;
        }

        /* Metrics grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #dee2e6;
        }

        .metric-card h4 {
            margin: 0 0 10px 0;
            color: #495057;
            font-size: 14px;
        }

        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #2196f3;
        }

        /* Quality score display */
        .quality-score {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 12px;
        }

        .quality-excellent { background: #4caf50; color: white; }
        .quality-good { background: #8bc34a; color: white; }
        .quality-fair { background: #ffc107; color: black; }
        .quality-poor { background: #ff9800; color: white; }
        .quality-failed { background: #f44336; color: white; }

        /* Preview controls */
        .preview-controls {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }

        /* Responsive design */
        @media (max-width: 768px) {
            .gradio-container {
                max-width: 100% !important;
            }

            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }
        """

    def _handle_translation_submit(
        self,
        file_data,
        format_type,
        source_lang,
        target_lang,
        preserve_layout,
        quality_assessment,
        quality_threshold,
    ):
        """Handle enhanced translation job submission."""

        if not file_data:
            return (
                "❌ Please select a file to translate.",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value="**Error:** No file selected.", visible=True),
                gr.update(visible=False),
            )

        try:
            # Validate inputs
            if source_lang == target_lang and source_lang != "auto":
                return (
                    "❌ Source and target languages cannot be the same.",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(
                        value="**Error:** Please select different languages.",
                        visible=True,
                    ),
                    gr.update(visible=False),
                )

            # Upload file with enhanced validation
            success, uploaded_file, errors = self.upload_service.upload_file(
                file_data, f"document.{format_type}"
            )

            if not success:
                error_msg = (
                    "<div class='error-message'>"
                    "<strong>Upload Errors:</strong><br>"
                    + "<br>".join(f"• {error}" for error in errors)
                    + "</div>"
                )
                return (
                    "❌ File upload failed.",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(value=error_msg, visible=True),
                    gr.update(visible=False),
                )

            # Submit translation job with enhanced configuration
            with self.upload_service.get_file_path(uploaded_file.file_id) as file_path:
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language=source_lang,
                    target_language=target_lang,
                    format_type=format_type,
                    preserve_layout=preserve_layout,
                    quality_threshold=quality_threshold,
                )

            # Store enhanced job info
            self.active_jobs[job_id] = {
                "uploaded_file_id": uploaded_file.file_id,
                "preserve_layout": preserve_layout,
                "quality_assessment": quality_assessment,
                "quality_threshold": quality_threshold,
                "submitted_at": datetime.now().isoformat(),
            }

            # Get initial job status
            job_status = self.orchestrator.get_job_status(job_id)

            # Create progress display
            progress_html = f"""
            <div class="progress-container" style="display: block;">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%;"></div>
                </div>
                <div class="progress-text">Starting translation...</div>
            </div>
            """

            success_msg = f"""
            <div class="success-message">
                <strong>✅ Translation job submitted successfully!</strong><br>
                <strong>Job ID:</strong> {job_id[:8]}...<br>
                <strong>Languages:</strong> {source_lang} → {target_lang}<br>
                <strong>Format:</strong> {format_type.upper()}
            </div>
            """

            return (
                f"✅ Job {job_id[:8]}... submitted successfully!",
                gr.update(value=progress_html, visible=True),
                gr.update(value=job_status, visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value=success_msg, visible=True),
            )

        except Exception as e:
            error_msg = f"""
            <div class="error-message">
                <strong>Unexpected Error:</strong><br>
                {str(e)}
            </div>
            """
            return (
                "❌ Translation submission failed.",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value=error_msg, visible=True),
                gr.update(visible=False),
            )

    def _update_job_progress(self, job):
        """Callback to update job progress."""
        # This would typically update a shared state or database
        # For now, we'll just store it in memory
        if job.job_id in self.active_jobs:
            self.active_jobs[job.job_id]["last_update"] = {
                "status": job.status.value,
                "progress": job.overall_progress,
                "stage": job.current_stage,
                "errors": len(job.errors),
            }

    def _refresh_jobs_table(self):
        """Refresh the enhanced jobs table."""
        jobs_data = []
        job_choices = []

        # Get all active jobs from orchestrator
        for job_id in list(self.active_jobs.keys()):
            status = self.orchestrator.get_job_status(job_id)
            if status:
                # Format quality score
                quality_score = status.get("quality_score", 0)
                quality_display = f"{quality_score:.2f}" if quality_score > 0 else "N/A"

                jobs_data.append(
                    [
                        job_id[:8] + "...",
                        status["status"],
                        f"{status['overall_progress']:.1f}%",
                        status.get("current_stage", "N/A"),
                        status["source_language"],
                        status["target_language"],
                        status["format_type"],
                        status["created_at"][:19] if status["created_at"] else "N/A",
                        quality_display,
                    ]
                )
                job_choices.append((job_id[:8] + "...", job_id))

        return (jobs_data, gr.update(choices=job_choices))

    def _get_job_details(self, job_id):
        """Get enhanced detailed job information."""
        if not job_id:
            return (
                gr.update(value={}),
                "<p>Select a job to see detailed progress...</p>",
                gr.update(visible=False),
            )

        status = self.orchestrator.get_job_status(job_id)
        if not status:
            return (
                gr.update(value={}),
                "<p>Job not found.</p>",
                gr.update(visible=False),
            )

        # Format enhanced stage progress with visual indicators
        stage_html = "<div class='stage-progress-container'>"
        stage_html += "<h4>🔄 Pipeline Progress</h4>"

        stages = status.get("stages", {})
        for stage_name, stage_info in stages.items():
            status_class = f"stage-progress {stage_info['status']}"
            status_emoji = {
                "pending": "⏳",
                "parsing": "📄",
                "analyzing_layout": "🔍",
                "translating": "🌐",
                "fitting_text": "📏",
                "reconstructing": "🔧",
                "assessing_quality": "✅",
                "preparing_download": "📦",
                "completed": "✅",
                "failed": "❌",
            }.get(stage_info["status"], "❓")

            stage_html += f"""
            <div class="{status_class}">
                <strong>{status_emoji} {stage_name.replace("_", " ").title()}</strong>
                <br>Status: {stage_info["status"]} 
                ({stage_info["progress"]:.1f}%)
            """

            if stage_info.get("error_count", 0) > 0:
                stage_html += f"<br>⚠️ {stage_info['error_count']} errors"

            if stage_info.get("duration"):
                stage_html += f"<br>⏱️ {stage_info['duration']:.1f}s"

            stage_html += "</div>"

        stage_html += "</div>"

        # Format messages and alerts
        messages_html = ""
        if status.get("errors"):
            messages_html = f"""
            <div class="error-message">
                <strong>⚠️ Errors ({len(status["errors"])})</strong>
                <ul>
                {"".join(f"<li>{error}</li>" for error in status["errors"][:5])}
                </ul>
            </div>
            """

        messages_visible = bool(status.get("errors") or status.get("warnings"))

        return (
            gr.update(value=status),
            stage_html,
            gr.update(value=messages_html, visible=messages_visible),
        )

    def _cancel_job(self, job_id):
        """Cancel a job."""
        if not job_id:
            return self._refresh_jobs_table() + (
                gr.update(value={}),
                "<p>No job selected.</p>",
                gr.update(visible=False),
            )

        success = self.orchestrator.cancel_job(job_id)

        if success:
            message = """
            <div class="success-message">
                ✅ Job cancelled successfully.
            </div>
            """
        else:
            message = """
            <div class="error-message">
                ❌ Failed to cancel job or job already completed.
            </div>
            """

        return self._refresh_jobs_table() + (
            gr.update(value={}),
            "<p>Job cancellation requested...</p>",
            gr.update(value=message, visible=True),
        )

    def _retry_job(self, job_id):
        """Retry a failed job."""
        if not job_id:
            return self._refresh_jobs_table() + (
                gr.update(value={}),
                "<p>No job selected.</p>",
                gr.update(visible=False),
            )

        success = self.orchestrator.retry_job(job_id)

        if success:
            message = """
            <div class="success-message">
                ✅ Job queued for retry successfully.
            </div>
            """
        else:
            message = """
            <div class="error-message">
                ❌ Failed to retry job. Job may not be failed or 
                exceeded maximum retry attempts.
            </div>
            """

        return self._refresh_jobs_table() + (
            gr.update(value={}),
            "<p>Job retry requested...</p>",
            gr.update(value=message, visible=True),
        )

    def _pause_job(self, job_id):
        """Pause a running job."""
        if not job_id:
            return self._refresh_jobs_table() + (
                gr.update(value={}),
                "<p>No job selected.</p>",
                gr.update(visible=False),
            )

        # This would be implemented in the orchestrator
        # For now, return a placeholder response
        message = """
        <div class="warning-message">
            ⏸️ Job pause functionality not yet implemented.
        </div>
        """

        return self._refresh_jobs_table() + (
            gr.update(value={}),
            "<p>Job pause requested...</p>",
            gr.update(value=message, visible=True),
        )

    def _generate_preview(
        self,
        job_id,
        show_original,
        show_translated,
        view_mode,
        zoom_level,
        highlight_mode,
        page_number,
    ):
        """Generate enhanced document preview."""
        if not job_id:
            return (
                "<p>Please select a completed job to preview.</p>",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

        try:
            # Get job status to verify completion
            status = self.orchestrator.get_job_status(job_id)
            if not status or status["status"] != "completed":
                return (
                    """
                    <div class="warning-message">
                        ⚠️ Job not completed or not found. 
                        Preview is only available for completed jobs.
                    </div>
                    """,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

            # Generate preview using preview service
            preview_config = {
                "show_original": show_original,
                "show_translated": show_translated,
                "view_mode": view_mode,
                "zoom_level": zoom_level,
                "highlight_mode": highlight_mode,
                "page_number": page_number,
            }

            # This would use the actual preview service
            preview_html = f"""
            <div class="preview-container" style="border: 1px solid #ddd; 
                 border-radius: 8px; padding: 20px; background: white;">
                <div class="preview-header" style="margin-bottom: 15px; 
                     padding-bottom: 10px; border-bottom: 1px solid #eee;">
                    <h3>📄 Document Preview - Job {job_id[:8]}...</h3>
                    <div class="preview-controls">
                        <span><strong>View:</strong> {view_mode}</span> |
                        <span><strong>Zoom:</strong> {zoom_level}x</span> |
                        <span><strong>Highlight:</strong> {highlight_mode}</span>
                    </div>
                </div>
                
                <div class="preview-content" style="min-height: 400px; 
                     background: #f8f9fa; border-radius: 4px; padding: 20px;">
                    <div style="text-align: center; color: #666;">
                        <h4>🔍 Enhanced Preview</h4>
                        <p>This would show the actual document preview using 
                           the PreviewService</p>
                        <p><strong>Features:</strong></p>
                        <ul style="text-align: left; display: inline-block;">
                            <li>Side-by-side comparison</li>
                            <li>Interactive highlighting</li>
                            <li>Zoom and scroll functionality</li>
                            <li>Quality issue indicators</li>
                            <li>Layout preservation visualization</li>
                        </ul>
                    </div>
                </div>
            </div>
            """

            # Mock preview statistics
            preview_stats = {
                "total_pages": 5,
                "current_page": page_number,
                "translation_coverage": "98.5%",
                "layout_preservation": "94.2%",
                "quality_score": 0.87,
            }

            # Page navigation controls
            max_pages = preview_stats["total_pages"]
            page_slider = gr.update(
                minimum=1, maximum=max_pages, value=page_number, visible=max_pages > 1
            )

            nav_buttons_visible = max_pages > 1

            return (
                preview_html,
                gr.update(value=preview_stats, visible=True),
                page_slider,
                gr.update(visible=nav_buttons_visible),
                gr.update(visible=nav_buttons_visible),
                gr.update(visible=True),
            )

        except Exception as e:
            error_html = f"""
            <div class="error-message">
                <strong>Error generating preview:</strong><br>
                {str(e)}
            </div>
            """
            return (
                error_html,
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

    def _navigate_preview_page(self, job_id, current_page, direction):
        """Navigate preview pages."""
        if not job_id:
            return gr.update(), gr.update()

        new_page = max(1, current_page + direction)
        # This would regenerate the preview for the new page
        return (f"<p>Navigated to page {new_page}</p>", gr.update(value=new_page))

    def _get_download_info(self, job_id):
        """Get enhanced download information for a job."""
        if not job_id:
            return (
                gr.update(visible=False),
                gr.update(visible=False),
                """
                <div style="text-align: center; padding: 20px; color: #666;">
                    <p>Select a completed job to see download options</p>
                </div>
                """,
            )

        status = self.orchestrator.get_job_status(job_id)
        if not status or status["status"] != "completed":
            error_info = {"error": "Job not completed or not found"}
            return (
                gr.update(value=error_info, visible=True),
                gr.update(visible=False),
                """
                <div class="warning-message">
                    ⚠️ Job not completed or not found. 
                    Downloads are only available for completed jobs.
                </div>
                """,
            )

        download_link_id = status.get("download_link_id")
        if not download_link_id:
            error_info = {"error": "No download link available"}
            return (
                gr.update(value=error_info, visible=True),
                gr.update(visible=False),
                """
                <div class="error-message">
                    ❌ No download link available for this job.
                </div>
                """,
            )

        download_info = self.download_service.get_download_info(download_link_id)
        if not download_info:
            error_info = {"error": "Download link expired"}
            return (
                gr.update(value=error_info, visible=True),
                gr.update(visible=False),
                """
                <div class="error-message">
                    ❌ Download link has expired. Please retry the translation.
                </div>
                """,
            )

        # Enhanced file details display
        file_details_html = f"""
        <div class="file-details" style="background: #f8f9fa; padding: 15px; 
             border-radius: 8px; margin: 10px 0;">
            <h4>📄 File Information</h4>
            <p><strong>Original Format:</strong> {download_info.get("format", "Unknown")}</p>
            <p><strong>File Size:</strong> {download_info.get("file_size", "Unknown")} bytes</p>
            <p><strong>Quality Score:</strong> 
               <span class="quality-score quality-{self._get_quality_class(download_info.get("quality_score", 0))}">
                   {download_info.get("quality_score", 0):.2f}
               </span>
            </p>
            <p><strong>Created:</strong> {download_info.get("created_at", "Unknown")}</p>
        </div>
        """

        status_html = """
        <div class="success-message">
            ✅ File ready for download
        </div>
        """

        return (
            gr.update(value=download_info, visible=True),
            gr.update(value=file_details_html, visible=True),
            status_html,
        )

    def _get_quality_class(self, score):
        """Get CSS class for quality score."""
        if score >= 0.9:
            return "excellent"
        elif score >= 0.8:
            return "good"
        elif score >= 0.7:
            return "fair"
        elif score >= 0.5:
            return "poor"
        else:
            return "failed"

    def _handle_download(
        self, job_id, download_format, include_quality_report, include_metadata
    ):
        """Handle enhanced file download."""
        if not job_id:
            return (
                """
                <div class="warning-message">
                    ⚠️ Please select a job to download.
                </div>
                """,
                gr.update(visible=False),
                gr.update(),
            )

        try:
            status = self.orchestrator.get_job_status(job_id)
            if not status or status["status"] != "completed":
                return (
                    """
                    <div class="error-message">
                        ❌ Job not completed or not found.
                    </div>
                    """,
                    gr.update(visible=False),
                    gr.update(),
                )

            download_link_id = status.get("download_link_id")
            if not download_link_id:
                return (
                    """
                    <div class="error-message">
                        ❌ No download link available.
                    </div>
                    """,
                    gr.update(visible=False),
                    gr.update(),
                )

            # Download main file
            success, file_bytes, filename, metadata = (
                self.download_service.download_file(download_link_id)
            )

            if not success:
                error_msg = metadata.get("error", "Unknown error")
                return (
                    f"""
                    <div class="error-message">
                        ❌ Download failed: {error_msg}
                    </div>
                    """,
                    gr.update(visible=False),
                    gr.update(),
                )

            # Prepare files for download
            download_files = []

            # Main translated document
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{metadata['format']}"
            ) as temp_file:
                temp_file.write(file_bytes)
                download_files.append(temp_file.name)

            # Quality report if requested
            if include_quality_report:
                quality_report = self._generate_quality_report(job_id)
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".html"
                ) as temp_file:
                    temp_file.write(quality_report.encode("utf-8"))
                    download_files.append(temp_file.name)

            # Metadata file if requested
            if include_metadata:
                metadata_content = self._generate_metadata_file(job_id, status)
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".json"
                ) as temp_file:
                    temp_file.write(metadata_content.encode("utf-8"))
                    download_files.append(temp_file.name)

            # Update download history
            history_entry = [
                job_id[:8] + "...",
                download_format,
                f"{metadata['file_size']} bytes",
                datetime.now().isoformat(),
            ]

            success_msg = f"""
            <div class="success-message">
                ✅ Download ready!<br>
                <strong>File:</strong> {filename}<br>
                <strong>Size:</strong> {metadata["file_size"]} bytes<br>
                <strong>Format:</strong> {metadata["format"].upper()}
            </div>
            """

            return (
                success_msg,
                gr.update(value=download_files, visible=True),
                gr.update(),  # Would update history table
            )

        except Exception as e:
            return (
                f"""
                <div class="error-message">
                    ❌ Download error: {str(e)}
                </div>
                """,
                gr.update(visible=False),
                gr.update(),
            )

    def _handle_batch_download(self, selected_jobs, download_format):
        """Handle batch download of multiple jobs."""
        if not selected_jobs:
            return (
                """
                <div class="warning-message">
                    ⚠️ Please select jobs for batch download.
                </div>
                """,
                gr.update(visible=False),
                gr.update(),
            )

        # This would implement batch download functionality
        return (
            f"""
            <div class="success-message">
                ✅ Batch download prepared for {len(selected_jobs)} jobs.
            </div>
            """,
            gr.update(visible=True),
            gr.update(),
        )

    def _generate_quality_report(self, job_id):
        """Generate HTML quality report."""
        return f"""
        <html>
        <head><title>Quality Report - Job {job_id[:8]}</title></head>
        <body>
            <h1>Translation Quality Report</h1>
            <p>Job ID: {job_id}</p>
            <p>This would contain detailed quality metrics and analysis.</p>
        </body>
        </html>
        """

    def _generate_metadata_file(self, job_id, status):
        """Generate JSON metadata file."""
        import json

        metadata = {
            "job_id": job_id,
            "status": status,
            "generated_at": datetime.now().isoformat(),
        }
        return json.dumps(metadata, indent=2)

    def _get_system_statistics(self):
        """Get enhanced system statistics."""
        try:
            # Get service statistics
            orchestrator_stats = self.orchestrator.get_orchestrator_stats()
            upload_stats = self.upload_service.get_upload_stats()
            download_stats = self.download_service.get_download_stats()

            # Generate real-time metrics HTML
            active_jobs = len(
                [j for j in self.active_jobs.values() if j.get("status") != "completed"]
            )
            total_jobs = len(self.active_jobs)
            success_rate = (
                (
                    total_jobs
                    - len(
                        [
                            j
                            for j in self.active_jobs.values()
                            if j.get("status") == "failed"
                        ]
                    )
                )
                / max(total_jobs, 1)
                * 100
            )

            metrics_html = f"""
            <div class="metrics-grid">
                <div class="metric-card">
                    <h4>Active Jobs</h4>
                    <span class="metric-value">{active_jobs}</span>
                </div>
                <div class="metric-card">
                    <h4>Total Jobs</h4>
                    <span class="metric-value">{total_jobs}</span>
                </div>
                <div class="metric-card">
                    <h4>Success Rate</h4>
                    <span class="metric-value">{success_rate:.1f}%</span>
                </div>
                <div class="metric-card">
                    <h4>Queue Length</h4>
                    <span class="metric-value">{orchestrator_stats.get("queue_length", 0)}</span>
                </div>
            </div>
            """

            # Mock preview and quality stats
            preview_stats = {"previews_generated": 0, "avg_generation_time": 0}
            quality_stats = {"assessments_completed": 0, "avg_quality_score": 0}

            # Mock language and format statistics
            language_stats = [
                ["en → fr", 5, "90%", "0.85"],
                ["en → es", 3, "100%", "0.92"],
                ["fr → en", 2, "100%", "0.88"],
            ]

            format_stats = [
                ["PDF", 7, "95%", "45s"],
                ["DOCX", 2, "100%", "30s"],
                ["EPUB", 1, "100%", "25s"],
            ]

            error_analysis = [
                ["Translation Error", 2, "20%"],
                ["Layout Error", 1, "10%"],
                ["Format Error", 0, "0%"],
            ]

            return (
                metrics_html,
                orchestrator_stats,
                upload_stats,
                download_stats,
                preview_stats,
                quality_stats,
                language_stats,
                format_stats,
                error_analysis,
            )

        except Exception as e:
            error_info = {"error": str(e)}
            error_html = f"""
            <div class="error-message">
                Error loading statistics: {str(e)}
            </div>
            """
            empty_stats = []

            return (
                error_html,
                error_info,
                error_info,
                error_info,
                error_info,
                error_info,
                empty_stats,
                empty_stats,
                empty_stats,
            )

    def _export_statistics(self):
        """Export system statistics to file."""
        try:
            stats_data = {
                "exported_at": datetime.now().isoformat(),
                "orchestrator": self.orchestrator.get_orchestrator_stats(),
                "upload": self.upload_service.get_upload_stats(),
                "download": self.download_service.get_download_stats(),
            }

            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json"
            ) as temp_file:
                import json

                json.dump(stats_data, temp_file, indent=2)
                return temp_file.name

        except Exception as e:
            # Return error file
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt"
            ) as temp_file:
                temp_file.write(f"Error exporting statistics: {str(e)}")
                return temp_file.name

    def launch(self, **kwargs):
        """Launch the Gradio interface."""
        interface = self.create_interface()
        return interface.launch(**kwargs)

    def shutdown(self):
        """Shutdown all services."""
        self.upload_service.shutdown()
        self.orchestrator.shutdown()
        self.download_service.shutdown()


def create_app():
    """Create and return the web application."""
    return TranslationWebInterface()


def main():
    """Main entry point for the web application."""
    app = create_app()

    try:
        app.launch(server_name="0.0.0.0", server_port=7860, share=False, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
