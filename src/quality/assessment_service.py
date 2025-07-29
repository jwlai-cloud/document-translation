"""Quality assessment service implementation."""

import re
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter

from src.models.document import DocumentStructure, PageStructure, TextRegion
from src.models.layout import LayoutAnalysis, AdjustedRegion
from src.models.quality import (
    QualityScore, QualityMetrics, QualityIssue, QualityIssueType,
    IssueSeverity, QualityReport, QualityRecommendation, QualityThreshold
)


class TranslationAccuracyAssessor:
    """Assesses translation accuracy using various metrics."""
    
    def __init__(self):
        """Initialize the translation accuracy assessor."""
        # Common words that should be preserved across languages
        self.preserve_words = {
            'numbers': r'\d+',
            'dates': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            'emails': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'urls': r'https?://[^\s]+',
            'proper_nouns': r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        }
    
    def assess_translation_accuracy(self, original_text: str, 
                                  translated_text: str,
                                  source_lang: str = "en",
                                  target_lang: str = "fr") -> Tuple[float, List[QualityIssue]]:
        """Assess the accuracy of a translation.
        
        Args:
            original_text: Original text
            translated_text: Translated text
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Tuple of (accuracy_score, list_of_issues)
        """
        issues = []
        
        # Check for empty translation
        if not translated_text.strip():
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_CONTENT,
                severity=IssueSeverity.CRITICAL,
                description="Translation is empty",
                confidence=1.0
            ))
            return 0.0, issues
        
        # Check length ratio (translations should be within reasonable bounds)
        length_ratio = len(translated_text) / len(original_text) if original_text else 0
        if length_ratio < 0.3 or length_ratio > 3.0:
            severity = IssueSeverity.HIGH if length_ratio < 0.5 or length_ratio > 2.0 else IssueSeverity.MEDIUM
            issues.append(QualityIssue(
                issue_type=QualityIssueType.TRANSLATION_ACCURACY,
                severity=severity,
                description=f"Translation length ratio unusual: {length_ratio:.2f}",
                suggested_fix="Review translation for completeness",
                confidence=0.8
            ))
        
        # Check preservation of special elements
        preservation_score = self._check_element_preservation(original_text, translated_text, issues)
        
        # Check for untranslated content (same language detection)
        untranslated_score = self._check_untranslated_content(
            original_text, translated_text, source_lang, target_lang, issues
        )
        
        # Check for context consistency
        context_score = self._check_context_consistency(original_text, translated_text, issues)
        
        # Calculate overall accuracy score
        accuracy_score = (preservation_score + untranslated_score + context_score) / 3.0
        
        # Adjust score based on length ratio
        if 0.7 <= length_ratio <= 1.5:
            length_bonus = 0.1
        else:
            length_bonus = max(0, 0.1 - abs(length_ratio - 1.0) * 0.05)
        
        accuracy_score = min(1.0, accuracy_score + length_bonus)
        
        return accuracy_score, issues
    
    def _check_element_preservation(self, original: str, translated: str, 
                                  issues: List[QualityIssue]) -> float:
        """Check if special elements are preserved in translation."""
        preservation_scores = []
        
        for element_type, pattern in self.preserve_words.items():
            original_matches = set(re.findall(pattern, original, re.IGNORECASE))
            translated_matches = set(re.findall(pattern, translated, re.IGNORECASE))
            
            if original_matches:
                preserved_count = len(original_matches.intersection(translated_matches))
                preservation_ratio = preserved_count / len(original_matches)
                preservation_scores.append(preservation_ratio)
                
                if preservation_ratio < 0.8:
                    missing_elements = original_matches - translated_matches
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.TRANSLATION_ACCURACY,
                        severity=IssueSeverity.MEDIUM,
                        description=f"Missing {element_type}: {', '.join(list(missing_elements)[:3])}",
                        suggested_fix=f"Ensure {element_type} are preserved in translation",
                        confidence=0.9
                    ))
        
        return sum(preservation_scores) / len(preservation_scores) if preservation_scores else 1.0
    
    def _check_untranslated_content(self, original: str, translated: str,
                                  source_lang: str, target_lang: str,
                                  issues: List[QualityIssue]) -> float:
        """Check for untranslated content in the translation."""
        # Simple heuristic: check for identical long phrases
        original_words = original.lower().split()
        translated_words = translated.lower().split()
        
        # Find common phrases of 3+ words
        untranslated_phrases = []
        for i in range(len(original_words) - 2):
            phrase = ' '.join(original_words[i:i+3])
            if phrase in translated.lower() and len(phrase) > 10:
                untranslated_phrases.append(phrase)
        
        if untranslated_phrases:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.TRANSLATION_ACCURACY,
                severity=IssueSeverity.MEDIUM,
                description=f"Potentially untranslated content found: {len(untranslated_phrases)} phrases",
                suggested_fix="Review and translate remaining content",
                confidence=0.7
            ))
            return max(0.5, 1.0 - len(untranslated_phrases) * 0.1)
        
        return 1.0
    
    def _check_context_consistency(self, original: str, translated: str,
                                 issues: List[QualityIssue]) -> float:
        """Check for context consistency in translation."""
        # Check sentence count consistency
        original_sentences = len(re.findall(r'[.!?]+', original))
        translated_sentences = len(re.findall(r'[.!?]+', translated))
        
        if original_sentences > 0:
            sentence_ratio = translated_sentences / original_sentences
            if sentence_ratio < 0.5 or sentence_ratio > 2.0:
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.CONTEXT_LOSS,
                    severity=IssueSeverity.MEDIUM,
                    description=f"Sentence structure changed significantly: {sentence_ratio:.2f} ratio",
                    suggested_fix="Review sentence structure preservation",
                    confidence=0.6
                ))
                return max(0.6, 1.0 - abs(sentence_ratio - 1.0) * 0.2)
        
        return 1.0


class LayoutPreservationAssessor:
    """Assesses how well layout is preserved after translation."""
    
    def assess_layout_preservation(self, original_analysis: LayoutAnalysis,
                                 adjusted_regions: List[AdjustedRegion]) -> Tuple[float, List[QualityIssue]]:
        """Assess layout preservation quality.
        
        Args:
            original_analysis: Original layout analysis
            adjusted_regions: Regions after translation and adjustment
            
        Returns:
            Tuple of (preservation_score, list_of_issues)
        """
        issues = []
        
        # Check element count preservation
        element_count_score = self._check_element_count_preservation(
            original_analysis, adjusted_regions, issues
        )
        
        # Check spatial relationship preservation
        spatial_score = self._check_spatial_preservation(
            original_analysis, adjusted_regions, issues
        )
        
        # Check reading order preservation
        reading_order_score = self._check_reading_order_preservation(
            original_analysis, adjusted_regions, issues
        )
        
        # Check bounding box changes
        bbox_score = self._check_bounding_box_changes(adjusted_regions, issues)
        
        # Calculate overall preservation score
        preservation_score = (
            element_count_score * 0.2 +
            spatial_score * 0.3 +
            reading_order_score * 0.3 +
            bbox_score * 0.2
        )
        
        return preservation_score, issues
    
    def _check_element_count_preservation(self, original_analysis: LayoutAnalysis,
                                        adjusted_regions: List[AdjustedRegion],
                                        issues: List[QualityIssue]) -> float:
        """Check if all elements are preserved."""
        original_count = len(original_analysis.text_regions)
        adjusted_count = len(adjusted_regions)
        
        if original_count != adjusted_count:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_CONTENT,
                severity=IssueSeverity.HIGH,
                description=f"Element count changed: {original_count} → {adjusted_count}",
                suggested_fix="Ensure all text regions are preserved",
                confidence=1.0
            ))
            return max(0.5, adjusted_count / original_count if original_count > 0 else 0.0)
        
        return 1.0
    
    def _check_spatial_preservation(self, original_analysis: LayoutAnalysis,
                                  adjusted_regions: List[AdjustedRegion],
                                  issues: List[QualityIssue]) -> float:
        """Check if spatial relationships are preserved."""
        # Create mapping of original to adjusted regions
        region_map = {adj.original_region.id: adj for adj in adjusted_regions}
        
        preserved_relationships = 0
        total_relationships = len(original_analysis.spatial_relationships)
        
        if total_relationships == 0:
            return 1.0
        
        for relationship in original_analysis.spatial_relationships:
            elem1_id = relationship.element1_id
            elem2_id = relationship.element2_id
            
            if elem1_id in region_map and elem2_id in region_map:
                # Check if relationship is still valid
                adj1 = region_map[elem1_id]
                adj2 = region_map[elem2_id]
                
                if self._relationship_preserved(relationship, adj1, adj2):
                    preserved_relationships += 1
                else:
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.LAYOUT_PRESERVATION,
                        severity=IssueSeverity.MEDIUM,
                        description=f"Spatial relationship changed: {elem1_id} {relationship.relationship_type} {elem2_id}",
                        suggested_fix="Review layout adjustments",
                        confidence=0.8
                    ))
        
        return preserved_relationships / total_relationships
    
    def _check_reading_order_preservation(self, original_analysis: LayoutAnalysis,
                                        adjusted_regions: List[AdjustedRegion],
                                        issues: List[QualityIssue]) -> float:
        """Check if reading order is preserved."""
        original_order = original_analysis.reading_order
        adjusted_order = [adj.original_region.id for adj in 
                         sorted(adjusted_regions, key=lambda x: x.original_region.reading_order)]
        
        if len(original_order) != len(adjusted_order):
            return 0.5
        
        # Calculate order preservation using longest common subsequence
        preserved_order = self._longest_common_subsequence(original_order, adjusted_order)
        preservation_ratio = len(preserved_order) / len(original_order) if original_order else 1.0
        
        if preservation_ratio < 0.8:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.LAYOUT_PRESERVATION,
                severity=IssueSeverity.MEDIUM,
                description=f"Reading order significantly changed: {preservation_ratio:.2f} preserved",
                suggested_fix="Review element positioning",
                confidence=0.7
            ))
        
        return preservation_ratio
    
    def _check_bounding_box_changes(self, adjusted_regions: List[AdjustedRegion],
                                  issues: List[QualityIssue]) -> float:
        """Check the extent of bounding box changes."""
        total_change = 0.0
        significant_changes = 0
        
        for adj_region in adjusted_regions:
            original_box = adj_region.original_region.bounding_box
            new_box = adj_region.new_bounding_box
            
            # Calculate relative change in area
            original_area = original_box.area()
            new_area = new_box.area()
            
            if original_area > 0:
                area_change = abs(new_area - original_area) / original_area
                total_change += area_change
                
                if area_change > 0.5:  # More than 50% change
                    significant_changes += 1
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.LAYOUT_PRESERVATION,
                        severity=IssueSeverity.MEDIUM,
                        description=f"Significant size change in region {adj_region.original_region.id}: {area_change:.1%}",
                        element_id=adj_region.original_region.id,
                        suggested_fix="Consider font size or layout adjustments",
                        confidence=0.9
                    ))
        
        if not adjusted_regions:
            return 1.0
        
        average_change = total_change / len(adjusted_regions)
        return max(0.0, 1.0 - average_change)
    
    def _relationship_preserved(self, relationship, adj1: AdjustedRegion, 
                              adj2: AdjustedRegion) -> bool:
        """Check if a spatial relationship is preserved."""
        # Simplified check - in practice would need more sophisticated analysis
        box1 = adj1.new_bounding_box
        box2 = adj2.new_bounding_box
        
        if relationship.relationship_type == "above":
            return box1.y + box1.height <= box2.y + 10  # Allow some tolerance
        elif relationship.relationship_type == "below":
            return box2.y + box2.height <= box1.y + 10
        elif relationship.relationship_type == "left":
            return box1.x + box1.width <= box2.x + 10
        elif relationship.relationship_type == "right":
            return box2.x + box2.width <= box1.x + 10
        
        return True  # Default to preserved for other relationships
    
    def _longest_common_subsequence(self, seq1: List, seq2: List) -> List:
        """Find longest common subsequence between two sequences."""
        if not seq1 or not seq2:
            return []
        
        # Dynamic programming approach
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        # Reconstruct LCS
        lcs = []
        i, j = m, n
        while i > 0 and j > 0:
            if seq1[i-1] == seq2[j-1]:
                lcs.append(seq1[i-1])
                i -= 1
                j -= 1
            elif dp[i-1][j] > dp[i][j-1]:
                i -= 1
            else:
                j -= 1
        
        return lcs[::-1]


class ReadabilityAssessor:
    """Assesses readability of translated text."""
    
    def assess_readability(self, text: str, language: str = "en") -> Tuple[float, List[QualityIssue]]:
        """Assess readability of text.
        
        Args:
            text: Text to assess
            language: Language code
            
        Returns:
            Tuple of (readability_score, list_of_issues)
        """
        issues = []
        
        if not text.strip():
            return 0.0, [QualityIssue(
                issue_type=QualityIssueType.MISSING_CONTENT,
                severity=IssueSeverity.CRITICAL,
                description="No text to assess",
                confidence=1.0
            )]
        
        # Calculate basic readability metrics
        sentence_count = len(re.findall(r'[.!?]+', text))
        word_count = len(text.split())
        char_count = len(text.replace(' ', ''))
        
        if sentence_count == 0 or word_count == 0:
            return 0.5, issues
        
        # Average sentence length
        avg_sentence_length = word_count / sentence_count
        if avg_sentence_length > 25:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.TRANSLATION_ACCURACY,
                severity=IssueSeverity.LOW,
                description=f"Long average sentence length: {avg_sentence_length:.1f} words",
                suggested_fix="Consider breaking long sentences",
                confidence=0.6
            ))
        
        # Average word length
        avg_word_length = char_count / word_count
        if avg_word_length > 7:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.TRANSLATION_ACCURACY,
                severity=IssueSeverity.LOW,
                description=f"Long average word length: {avg_word_length:.1f} characters",
                suggested_fix="Consider using simpler vocabulary",
                confidence=0.5
            ))
        
        # Calculate readability score (simplified Flesch-like formula)
        readability_score = max(0.0, min(1.0, 
            1.0 - (avg_sentence_length - 15) * 0.02 - (avg_word_length - 5) * 0.05
        ))
        
        return readability_score, issues


class QualityAssessmentService:
    """Main quality assessment service."""
    
    def __init__(self, quality_threshold: Optional[QualityThreshold] = None):
        """Initialize the quality assessment service.
        
        Args:
            quality_threshold: Quality thresholds to use
        """
        self.quality_threshold = quality_threshold or QualityThreshold()
        self.translation_assessor = TranslationAccuracyAssessor()
        self.layout_assessor = LayoutPreservationAssessor()
        self.readability_assessor = ReadabilityAssessor()
    
    def assess_translation_quality(self, original_text: str, translated_text: str,
                                 source_lang: str = "en", target_lang: str = "fr") -> QualityScore:
        """Assess the quality of a single translation.
        
        Args:
            original_text: Original text
            translated_text: Translated text
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            QualityScore with detailed assessment
        """
        all_issues = []
        
        # Assess translation accuracy
        translation_accuracy, translation_issues = self.translation_assessor.assess_translation_accuracy(
            original_text, translated_text, source_lang, target_lang
        )
        all_issues.extend(translation_issues)
        
        # Assess readability
        readability, readability_issues = self.readability_assessor.assess_readability(
            translated_text, target_lang
        )
        all_issues.extend(readability_issues)
        
        # Create quality metrics
        metrics = QualityMetrics(
            translation_accuracy=translation_accuracy,
            layout_preservation=1.0,  # No layout changes for single text
            formatting_preservation=1.0,  # No formatting changes for single text
            readability=readability,
            context_preservation=translation_accuracy,  # Use translation accuracy as proxy
            visual_consistency=1.0  # No visual changes for single text
        )
        
        return QualityScore(
            overall_score=metrics.overall_score,
            metrics=metrics,
            issues=all_issues
        )
    
    def assess_layout_preservation(self, original_analysis: LayoutAnalysis,
                                 adjusted_regions: List[AdjustedRegion]) -> QualityScore:
        """Assess layout preservation quality.
        
        Args:
            original_analysis: Original layout analysis
            adjusted_regions: Adjusted regions after translation
            
        Returns:
            QualityScore focused on layout preservation
        """
        layout_preservation, layout_issues = self.layout_assessor.assess_layout_preservation(
            original_analysis, adjusted_regions
        )
        
        # Calculate formatting preservation based on adjustments
        formatting_preservation = self._calculate_formatting_preservation(adjusted_regions)
        
        # Calculate visual consistency
        visual_consistency = self._calculate_visual_consistency(adjusted_regions)
        
        metrics = QualityMetrics(
            translation_accuracy=0.8,  # Assume good translation accuracy
            layout_preservation=layout_preservation,
            formatting_preservation=formatting_preservation,
            readability=0.8,  # Assume good readability
            context_preservation=0.8,  # Assume good context preservation
            visual_consistency=visual_consistency
        )
        
        return QualityScore(
            overall_score=metrics.overall_score,
            metrics=metrics,
            issues=layout_issues
        )
    
    def generate_quality_report(self, document: DocumentStructure,
                              page_assessments: List[QualityScore],
                              overall_assessment: QualityScore) -> QualityReport:
        """Generate a comprehensive quality report.
        
        Args:
            document: Original document structure
            page_assessments: Quality scores for each page
            overall_assessment: Overall quality score
            
        Returns:
            Comprehensive quality report
        """
        # Generate recommendations
        recommendations = self._generate_recommendations(overall_assessment, page_assessments)
        
        # Create report
        report = QualityReport(
            document_id=document.metadata.title or "Unknown Document",
            overall_score=overall_assessment,
            page_scores=page_assessments,
            recommendations=recommendations
        )
        
        # Generate summary
        report.summary = report.generate_summary()
        
        return report
    
    def _calculate_formatting_preservation(self, adjusted_regions: List[AdjustedRegion]) -> float:
        """Calculate formatting preservation score."""
        if not adjusted_regions:
            return 1.0
        
        total_preservation = 0.0
        
        for adj_region in adjusted_regions:
            # Count formatting-related adjustments
            formatting_adjustments = sum(
                1 for adj in adj_region.adjustments
                if adj.adjustment_type.value in ['font_size_change', 'line_spacing_change']
            )
            
            # Calculate preservation (fewer adjustments = better preservation)
            region_preservation = max(0.0, 1.0 - formatting_adjustments * 0.2)
            total_preservation += region_preservation
        
        return total_preservation / len(adjusted_regions)
    
    def _calculate_visual_consistency(self, adjusted_regions: List[AdjustedRegion]) -> float:
        """Calculate visual consistency score."""
        if not adjusted_regions:
            return 1.0
        
        # Check for consistent adjustment patterns
        font_size_changes = []
        position_changes = []
        
        for adj_region in adjusted_regions:
            for adj in adj_region.adjustments:
                if adj.adjustment_type.value == 'font_size_change':
                    font_size_changes.append(adj.new_value / adj.original_value)
                elif adj.adjustment_type.value == 'position_shift':
                    # Calculate position change magnitude
                    old_pos = adj.original_value
                    new_pos = adj.new_value
                    change_magnitude = math.sqrt((new_pos[0] - old_pos[0])**2 + (new_pos[1] - old_pos[1])**2)
                    position_changes.append(change_magnitude)
        
        # Calculate consistency (lower variance = higher consistency)
        consistency_score = 1.0
        
        if font_size_changes:
            font_variance = sum((x - sum(font_size_changes)/len(font_size_changes))**2 for x in font_size_changes) / len(font_size_changes)
            consistency_score *= max(0.5, 1.0 - font_variance)
        
        if position_changes:
            pos_variance = sum((x - sum(position_changes)/len(position_changes))**2 for x in position_changes) / len(position_changes)
            consistency_score *= max(0.5, 1.0 - pos_variance / 1000)  # Normalize by expected range
        
        return consistency_score
    
    def _generate_recommendations(self, overall_assessment: QualityScore,
                                page_assessments: List[QualityScore]) -> List[QualityRecommendation]:
        """Generate quality improvement recommendations."""
        recommendations = []
        
        # Check overall score
        if overall_assessment.overall_score < self.quality_threshold.minimum_overall_score:
            recommendations.append(QualityRecommendation(
                recommendation_type="overall_improvement",
                description=f"Overall quality score ({overall_assessment.overall_score:.2f}) below threshold ({self.quality_threshold.minimum_overall_score:.2f})",
                priority=5,
                estimated_effort="high",
                expected_improvement=self.quality_threshold.minimum_overall_score - overall_assessment.overall_score
            ))
        
        # Check translation accuracy
        if overall_assessment.metrics.translation_accuracy < self.quality_threshold.minimum_translation_accuracy:
            recommendations.append(QualityRecommendation(
                recommendation_type="retranslate",
                description="Translation accuracy below threshold - consider retranslation",
                priority=4,
                estimated_effort="high",
                expected_improvement=0.2
            ))
        
        # Check layout preservation
        if overall_assessment.metrics.layout_preservation < self.quality_threshold.minimum_layout_preservation:
            recommendations.append(QualityRecommendation(
                recommendation_type="layout_adjustment",
                description="Layout preservation below threshold - review layout adjustments",
                priority=3,
                estimated_effort="medium",
                expected_improvement=0.15
            ))
        
        # Check for critical issues
        if overall_assessment.critical_issues:
            recommendations.append(QualityRecommendation(
                recommendation_type="manual_review",
                description=f"Critical issues found: {len(overall_assessment.critical_issues)} issues require immediate attention",
                priority=5,
                estimated_effort="medium",
                expected_improvement=0.3
            ))
        
        # Check readability
        if overall_assessment.metrics.readability < 0.7:
            recommendations.append(QualityRecommendation(
                recommendation_type="readability_improvement",
                description="Readability could be improved - consider simplifying language",
                priority=2,
                estimated_effort="low",
                expected_improvement=0.1
            ))
        
        return recommendations