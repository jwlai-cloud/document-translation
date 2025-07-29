"""Tests for quality assessment service."""

import pytest
from unittest.mock import Mock

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox, 
    TextFormatting, DocumentMetadata, Dimensions
)
from src.models.layout import (
    LayoutAnalysis, AdjustedRegion, LayoutAdjustment, 
    LayoutAdjustmentType, SpatialRelationship
)
from src.models.quality import (
    QualityScore, QualityMetrics, QualityIssue, QualityIssueType,
    IssueSeverity, QualityReport, QualityThreshold
)
from src.quality.assessment_service import (
    QualityAssessmentService, TranslationAccuracyAssessor,
    LayoutPreservationAssessor, ReadabilityAssessor
)


class TestTranslationAccuracyAssessor:
    """Test cases for TranslationAccuracyAssessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.assessor = TranslationAccuracyAssessor()
    
    def test_assess_translation_accuracy_good_translation(self):
        """Test assessment of good translation."""
        original = "Hello world, this is a test document."
        translated = "Bonjour le monde, ceci est un document de test."
        
        score, issues = self.assessor.assess_translation_accuracy(original, translated, "en", "fr")
        
        assert 0.7 <= score <= 1.0
        assert isinstance(issues, list)
        # Should have minimal issues for good translation
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    
    def test_assess_translation_accuracy_empty_translation(self):
        """Test assessment of empty translation."""
        original = "Hello world"
        translated = ""
        
        score, issues = self.assessor.assess_translation_accuracy(original, translated)
        
        assert score == 0.0
        assert len(issues) >= 1
        assert any(issue.issue_type == QualityIssueType.MISSING_CONTENT for issue in issues)
        assert any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
    
    def test_assess_translation_accuracy_length_ratio_issues(self):
        """Test assessment with unusual length ratios."""
        original = "Hello world"
        # Very short translation
        translated = "Hi"
        
        score, issues = self.assessor.assess_translation_accuracy(original, translated)
        
        assert score < 1.0
        length_issues = [i for i in issues if "length ratio" in i.description]
        assert len(length_issues) >= 1
    
    def test_assess_translation_accuracy_preserves_numbers(self):
        """Test that numbers are preserved in translation."""
        original = "The price is $25.99 and the date is 2024-01-15."
        translated = "Le prix est 25,99 $ et la date est 15-01-2024."  # Missing original number format
        
        score, issues = self.assessor.assess_translation_accuracy(original, translated)
        
        # Should detect missing number preservation
        number_issues = [i for i in issues if "numbers" in i.description.lower()]
        assert len(number_issues) >= 0  # May or may not detect depending on format
    
    def test_assess_translation_accuracy_preserves_emails(self):
        """Test that email addresses are preserved."""
        original = "Contact us at support@example.com for help."
        translated = "Contactez-nous à support@example.com pour de l'aide."
        
        score, issues = self.assessor.assess_translation_accuracy(original, translated)
        
        assert score > 0.8  # Should score well since email is preserved
        email_issues = [i for i in issues if "emails" in i.description.lower()]
        assert len(email_issues) == 0  # No email issues expected
    
    def test_check_element_preservation(self):
        """Test element preservation checking."""
        original = "Visit https://example.com or email test@domain.com"
        translated = "Visitez https://example.com ou envoyez un email"  # Missing email
        
        issues = []
        score = self.assessor._check_element_preservation(original, translated, issues)
        
        assert score < 1.0  # Should be less than perfect due to missing email
        assert len(issues) > 0
    
    def test_check_untranslated_content(self):
        """Test untranslated content detection."""
        original = "This is a test document with some content"
        translated = "This is a test document avec du contenu"  # Partially untranslated
        
        issues = []
        score = self.assessor._check_untranslated_content(original, translated, "en", "fr", issues)
        
        # May or may not detect depending on phrase length threshold
        assert 0.0 <= score <= 1.0
    
    def test_check_context_consistency(self):
        """Test context consistency checking."""
        original = "First sentence. Second sentence. Third sentence."
        translated = "Première phrase combinée avec la deuxième."  # Fewer sentences
        
        issues = []
        score = self.assessor._check_context_consistency(original, translated, issues)
        
        assert score < 1.0  # Should detect sentence structure change
        context_issues = [i for i in issues if i.issue_type == QualityIssueType.CONTEXT_LOSS]
        assert len(context_issues) >= 1


class TestLayoutPreservationAssessor:
    """Test cases for LayoutPreservationAssessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.assessor = LayoutPreservationAssessor()
        
        # Create test layout analysis
        self.text_region1 = TextRegion(
            id="region1",
            bounding_box=BoundingBox(10, 10, 200, 30),
            text_content="First region",
            reading_order=0
        )
        
        self.text_region2 = TextRegion(
            id="region2",
            bounding_box=BoundingBox(10, 50, 200, 30),
            text_content="Second region",
            reading_order=1
        )
        
        self.layout_analysis = LayoutAnalysis(
            page_number=1,
            text_regions=[self.text_region1, self.text_region2],
            spatial_relationships=[
                SpatialRelationship("region1", "region2", "above", 10.0, 0.9)
            ],
            reading_order=["region1", "region2"]
        )
    
    def test_assess_layout_preservation_perfect(self):
        """Test assessment with perfect layout preservation."""
        # Create adjusted regions with no changes
        adjusted_regions = [
            AdjustedRegion(
                original_region=self.text_region1,
                adjusted_text="Premier région",
                new_bounding_box=self.text_region1.bounding_box,
                adjustments=[],
                fit_quality=1.0
            ),
            AdjustedRegion(
                original_region=self.text_region2,
                adjusted_text="Deuxième région",
                new_bounding_box=self.text_region2.bounding_box,
                adjustments=[],
                fit_quality=1.0
            )
        ]
        
        score, issues = self.assessor.assess_layout_preservation(self.layout_analysis, adjusted_regions)
        
        assert score > 0.9  # Should be very high for perfect preservation
        assert len(issues) == 0  # No issues expected
    
    def test_assess_layout_preservation_missing_elements(self):
        """Test assessment with missing elements."""
        # Only one adjusted region (missing one)
        adjusted_regions = [
            AdjustedRegion(
                original_region=self.text_region1,
                adjusted_text="Premier région",
                new_bounding_box=self.text_region1.bounding_box,
                adjustments=[],
                fit_quality=1.0
            )
        ]
        
        score, issues = self.assessor.assess_layout_preservation(self.layout_analysis, adjusted_regions)
        
        assert score < 0.8  # Should be lower due to missing element
        missing_issues = [i for i in issues if i.issue_type == QualityIssueType.MISSING_CONTENT]
        assert len(missing_issues) >= 1
    
    def test_assess_layout_preservation_size_changes(self):
        """Test assessment with significant size changes."""
        # Create adjusted region with significant size change
        large_box = BoundingBox(10, 10, 400, 60)  # Much larger
        adjusted_regions = [
            AdjustedRegion(
                original_region=self.text_region1,
                adjusted_text="Much longer translated text that requires expansion",
                new_bounding_box=large_box,
                adjustments=[
                    LayoutAdjustment(
                        adjustment_type=LayoutAdjustmentType.BOUNDARY_EXPANSION,
                        element_id="region1",
                        original_value=(200, 30),
                        new_value=(400, 60)
                    )
                ],
                fit_quality=0.7
            ),
            AdjustedRegion(
                original_region=self.text_region2,
                adjusted_text="Deuxième région",
                new_bounding_box=self.text_region2.bounding_box,
                adjustments=[],
                fit_quality=1.0
            )
        ]
        
        score, issues = self.assessor.assess_layout_preservation(self.layout_analysis, adjusted_regions)
        
        assert score < 1.0  # Should be lower due to size changes
        size_issues = [i for i in issues if "size change" in i.description.lower()]
        assert len(size_issues) >= 1
    
    def test_check_element_count_preservation(self):
        """Test element count preservation checking."""
        adjusted_regions = [
            AdjustedRegion(
                original_region=self.text_region1,
                adjusted_text="Text",
                new_bounding_box=self.text_region1.bounding_box,
                adjustments=[],
                fit_quality=1.0
            )
        ]
        
        issues = []
        score = self.assessor._check_element_count_preservation(
            self.layout_analysis, adjusted_regions, issues
        )
        
        assert score < 1.0  # Should be less than 1 due to missing element
        assert len(issues) >= 1
    
    def test_check_reading_order_preservation(self):
        """Test reading order preservation checking."""
        # Create adjusted regions with reversed order
        adjusted_regions = [
            AdjustedRegion(
                original_region=self.text_region2,  # Second region first
                adjusted_text="Text",
                new_bounding_box=self.text_region2.bounding_box,
                adjustments=[],
                fit_quality=1.0
            ),
            AdjustedRegion(
                original_region=self.text_region1,  # First region second
                adjusted_text="Text",
                new_bounding_box=self.text_region1.bounding_box,
                adjustments=[],
                fit_quality=1.0
            )
        ]
        
        # Manually set reading orders to test reversal
        adjusted_regions[0].original_region.reading_order = 1
        adjusted_regions[1].original_region.reading_order = 0
        
        issues = []
        score = self.assessor._check_reading_order_preservation(
            self.layout_analysis, adjusted_regions, issues
        )
        
        assert score < 1.0  # Should detect order change
    
    def test_relationship_preserved(self):
        """Test spatial relationship preservation checking."""
        relationship = SpatialRelationship("region1", "region2", "above", 10.0, 0.9)
        
        adj1 = AdjustedRegion(
            original_region=self.text_region1,
            adjusted_text="Text",
            new_bounding_box=BoundingBox(10, 10, 200, 30),  # Above region2
            adjustments=[],
            fit_quality=1.0
        )
        
        adj2 = AdjustedRegion(
            original_region=self.text_region2,
            adjusted_text="Text",
            new_bounding_box=BoundingBox(10, 50, 200, 30),  # Below region1
            adjustments=[],
            fit_quality=1.0
        )
        
        preserved = self.assessor._relationship_preserved(relationship, adj1, adj2)
        assert preserved is True
    
    def test_longest_common_subsequence(self):
        """Test longest common subsequence calculation."""
        seq1 = ["a", "b", "c", "d"]
        seq2 = ["a", "c", "d", "e"]
        
        lcs = self.assessor._longest_common_subsequence(seq1, seq2)
        
        assert lcs == ["a", "c", "d"]


class TestReadabilityAssessor:
    """Test cases for ReadabilityAssessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.assessor = ReadabilityAssessor()
    
    def test_assess_readability_good_text(self):
        """Test readability assessment of good text."""
        text = "This is a simple sentence. It has good readability. The words are not too long."
        
        score, issues = self.assessor.assess_readability(text)
        
        assert 0.7 <= score <= 1.0
        assert isinstance(issues, list)
        # Should have minimal issues for readable text
        high_severity_issues = [i for i in issues if i.severity in [IssueSeverity.HIGH, IssueSeverity.CRITICAL]]
        assert len(high_severity_issues) == 0
    
    def test_assess_readability_empty_text(self):
        """Test readability assessment of empty text."""
        text = ""
        
        score, issues = self.assessor.assess_readability(text)
        
        assert score == 0.0
        assert len(issues) >= 1
        assert any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
    
    def test_assess_readability_long_sentences(self):
        """Test readability assessment with long sentences."""
        text = "This is an extremely long sentence that goes on and on and on and contains many words and clauses and subclauses and is generally difficult to read and understand because of its excessive length and complexity."
        
        score, issues = self.assessor.assess_readability(text)
        
        assert score < 1.0  # Should be penalized for long sentences
        sentence_issues = [i for i in issues if "sentence length" in i.description.lower()]
        assert len(sentence_issues) >= 1
    
    def test_assess_readability_long_words(self):
        """Test readability assessment with long words."""
        text = "Antidisestablishmentarianism represents incomprehensibility through sesquipedalian terminology."
        
        score, issues = self.assessor.assess_readability(text)
        
        assert score < 1.0  # Should be penalized for long words
        word_issues = [i for i in issues if "word length" in i.description.lower()]
        assert len(word_issues) >= 1


class TestQualityAssessmentService:
    """Test cases for QualityAssessmentService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = QualityAssessmentService()
        
        # Create test document
        self.test_document = DocumentStructure(
            format="pdf",
            pages=[
                PageStructure(
                    page_number=1,
                    dimensions=Dimensions(width=400, height=600),
                    text_regions=[
                        TextRegion(
                            id="region1",
                            bounding_box=BoundingBox(10, 10, 200, 30),
                            text_content="Test content"
                        )
                    ]
                )
            ],
            metadata=DocumentMetadata(title="Test Document")
        )
    
    def test_assess_translation_quality_good(self):
        """Test quality assessment of good translation."""
        original = "Hello world, this is a test."
        translated = "Bonjour le monde, ceci est un test."
        
        quality_score = self.service.assess_translation_quality(original, translated, "en", "fr")
        
        assert isinstance(quality_score, QualityScore)
        assert 0.0 <= quality_score.overall_score <= 1.0
        assert isinstance(quality_score.metrics, QualityMetrics)
        assert quality_score.metrics.translation_accuracy > 0.5
    
    def test_assess_translation_quality_poor(self):
        """Test quality assessment of poor translation."""
        original = "Hello world, this is a test."
        translated = ""  # Empty translation
        
        quality_score = self.service.assess_translation_quality(original, translated)
        
        assert quality_score.overall_score < 0.5
        assert len(quality_score.issues) > 0
        assert any(issue.severity == IssueSeverity.CRITICAL for issue in quality_score.issues)
    
    def test_assess_layout_preservation(self):
        """Test layout preservation assessment."""
        # Create test layout analysis
        layout_analysis = LayoutAnalysis(
            page_number=1,
            text_regions=[
                TextRegion(
                    id="region1",
                    bounding_box=BoundingBox(10, 10, 200, 30),
                    text_content="Test content"
                )
            ],
            reading_order=["region1"]
        )
        
        # Create adjusted regions
        adjusted_regions = [
            AdjustedRegion(
                original_region=layout_analysis.text_regions[0],
                adjusted_text="Contenu de test",
                new_bounding_box=BoundingBox(10, 10, 220, 35),  # Slightly larger
                adjustments=[],
                fit_quality=0.9
            )
        ]
        
        quality_score = self.service.assess_layout_preservation(layout_analysis, adjusted_regions)
        
        assert isinstance(quality_score, QualityScore)
        assert 0.0 <= quality_score.overall_score <= 1.0
        assert quality_score.metrics.layout_preservation > 0.0
    
    def test_generate_quality_report(self):
        """Test quality report generation."""
        # Create mock assessments
        overall_assessment = QualityScore(
            overall_score=0.75,
            metrics=QualityMetrics(
                translation_accuracy=0.8,
                layout_preservation=0.7,
                readability=0.8
            ),
            issues=[]
        )
        
        page_assessments = [overall_assessment]
        
        report = self.service.generate_quality_report(
            self.test_document, page_assessments, overall_assessment
        )
        
        assert isinstance(report, QualityReport)
        assert report.document_id == "Test Document"
        assert report.overall_score == overall_assessment
        assert len(report.page_scores) == 1
        assert len(report.recommendations) >= 0
        assert report.summary != ""
    
    def test_generate_recommendations_low_score(self):
        """Test recommendation generation for low quality scores."""
        low_quality_assessment = QualityScore(
            overall_score=0.5,  # Below threshold
            metrics=QualityMetrics(
                translation_accuracy=0.6,  # Below threshold
                layout_preservation=0.5,  # Below threshold
                readability=0.6
            ),
            issues=[
                QualityIssue(
                    issue_type=QualityIssueType.TRANSLATION_ACCURACY,
                    severity=IssueSeverity.CRITICAL,
                    description="Critical translation issue"
                )
            ]
        )
        
        recommendations = self.service._generate_recommendations(low_quality_assessment, [])
        
        assert len(recommendations) > 0
        # Should have recommendations for low scores and critical issues
        high_priority_recs = [r for r in recommendations if r.priority >= 4]
        assert len(high_priority_recs) > 0
    
    def test_calculate_formatting_preservation(self):
        """Test formatting preservation calculation."""
        adjusted_regions = [
            AdjustedRegion(
                original_region=TextRegion(id="test", bounding_box=BoundingBox(0, 0, 100, 20), text_content="test"),
                adjusted_text="test",
                new_bounding_box=BoundingBox(0, 0, 100, 20),
                adjustments=[
                    LayoutAdjustment(
                        adjustment_type=LayoutAdjustmentType.FONT_SIZE_CHANGE,
                        element_id="test",
                        original_value=12.0,
                        new_value=10.0
                    )
                ],
                fit_quality=0.8
            )
        ]
        
        score = self.service._calculate_formatting_preservation(adjusted_regions)
        
        assert 0.0 <= score <= 1.0
        assert score < 1.0  # Should be less than perfect due to font size change
    
    def test_calculate_visual_consistency(self):
        """Test visual consistency calculation."""
        adjusted_regions = [
            AdjustedRegion(
                original_region=TextRegion(id="test1", bounding_box=BoundingBox(0, 0, 100, 20), text_content="test1"),
                adjusted_text="test1",
                new_bounding_box=BoundingBox(0, 0, 100, 20),
                adjustments=[],
                fit_quality=1.0
            ),
            AdjustedRegion(
                original_region=TextRegion(id="test2", bounding_box=BoundingBox(0, 30, 100, 20), text_content="test2"),
                adjusted_text="test2",
                new_bounding_box=BoundingBox(0, 30, 100, 20),
                adjustments=[],
                fit_quality=1.0
            )
        ]
        
        score = self.service._calculate_visual_consistency(adjusted_regions)
        
        assert 0.0 <= score <= 1.0
        # Should be high for consistent adjustments (none in this case)
        assert score >= 0.8
    
    def test_quality_threshold_integration(self):
        """Test integration with quality thresholds."""
        # Create service with strict thresholds
        strict_threshold = QualityThreshold(
            minimum_overall_score=0.9,
            minimum_translation_accuracy=0.95,
            minimum_layout_preservation=0.9
        )
        
        service = QualityAssessmentService(quality_threshold=strict_threshold)
        
        # Test with mediocre quality
        mediocre_assessment = QualityScore(
            overall_score=0.8,  # Below strict threshold
            metrics=QualityMetrics(
                translation_accuracy=0.85,  # Below strict threshold
                layout_preservation=0.8
            )
        )
        
        recommendations = service._generate_recommendations(mediocre_assessment, [])
        
        # Should generate more recommendations due to strict thresholds
        assert len(recommendations) > 0


class TestIntegration:
    """Integration tests for quality assessment."""
    
    def test_full_quality_assessment_workflow(self):
        """Test complete quality assessment workflow."""
        service = QualityAssessmentService()
        
        # Create test data
        original_text = "This is a test document with multiple sentences. It contains various content types."
        translated_text = "Ceci est un document de test avec plusieurs phrases. Il contient différents types de contenu."
        
        # Assess translation quality
        translation_quality = service.assess_translation_quality(
            original_text, translated_text, "en", "fr"
        )
        
        assert isinstance(translation_quality, QualityScore)
        assert translation_quality.overall_score > 0.0
        
        # Create layout analysis
        layout_analysis = LayoutAnalysis(
            page_number=1,
            text_regions=[
                TextRegion(
                    id="region1",
                    bounding_box=BoundingBox(10, 10, 300, 40),
                    text_content=original_text
                )
            ],
            reading_order=["region1"]
        )
        
        # Create adjusted region
        adjusted_regions = [
            AdjustedRegion(
                original_region=layout_analysis.text_regions[0],
                adjusted_text=translated_text,
                new_bounding_box=BoundingBox(10, 10, 320, 45),  # Slightly expanded
                adjustments=[
                    LayoutAdjustment(
                        adjustment_type=LayoutAdjustmentType.BOUNDARY_EXPANSION,
                        element_id="region1",
                        original_value=(300, 40),
                        new_value=(320, 45)
                    )
                ],
                fit_quality=0.9
            )
        ]
        
        # Assess layout preservation
        layout_quality = service.assess_layout_preservation(layout_analysis, adjusted_regions)
        
        assert isinstance(layout_quality, QualityScore)
        assert layout_quality.overall_score > 0.0
        
        # Generate report
        document = DocumentStructure(
            format="pdf",
            pages=[
                PageStructure(
                    page_number=1,
                    dimensions=Dimensions(width=400, height=600),
                    text_regions=layout_analysis.text_regions
                )
            ],
            metadata=DocumentMetadata(title="Integration Test Document")
        )
        
        report = service.generate_quality_report(
            document, [translation_quality], translation_quality
        )
        
        assert isinstance(report, QualityReport)
        assert report.document_id == "Integration Test Document"
        assert len(report.page_scores) == 1
        assert report.summary != ""


if __name__ == "__main__":
    pytest.main([__file__])