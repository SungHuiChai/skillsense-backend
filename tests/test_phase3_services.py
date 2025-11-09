#!/usr/bin/env python3
"""
Unit tests for Phase 3 services:
- ChatGPT Web Search Service
- Skill Normalization Service
- Confidence Calculator Service
- Hallucination Detector Service
"""
import pytest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.skill_normalization import SkillNormalizationService
from app.services.confidence_calculator import ConfidenceCalculatorService
from app.services.hallucination_detector import HallucinationDetectorService


class TestSkillNormalization:
    """Test Skill Normalization Service"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = SkillNormalizationService()

    def test_normalize_python_variations(self):
        """Test that Python variations normalize correctly"""
        variations = ["Python", "python", "Python3", "python 3", "PYTHON", "Py"]
        for variation in variations:
            assert self.service.normalize_skill(variation) == "python", f"Failed for: {variation}"

    def test_normalize_javascript_variations(self):
        """Test JavaScript variations"""
        variations = ["JavaScript", "javascript", "JS", "js", "ECMAScript"]
        for variation in variations:
            assert self.service.normalize_skill(variation) == "javascript", f"Failed for: {variation}"

    def test_normalize_react_variations(self):
        """Test React variations"""
        variations = ["React", "react", "ReactJS", "react.js", "React.js"]
        for variation in variations:
            assert self.service.normalize_skill(variation) == "react", f"Failed for: {variation}"

    def test_normalize_skill_list_removes_duplicates(self):
        """Test that normalizing a list removes duplicates"""
        skills = ["Python", "python", "JavaScript", "javascript", "React", "react"]
        normalized = self.service.normalize_skills(skills)
        assert len(normalized) == 3
        assert "python" in normalized
        assert "javascript" in normalized
        assert "react" in normalized

    def test_merge_skill_lists(self):
        """Test merging multiple skill lists"""
        list1 = ["Python", "JavaScript"]
        list2 = ["python", "React"]
        list3 = ["JAVASCRIPT", "react"]

        merged = self.service.merge_skill_lists(list1, list2, list3)
        assert len(merged) == 3
        assert "python" in merged
        assert "javascript" in merged
        assert "react" in merged

    def test_group_similar_skills(self):
        """Test grouping skills by canonical form"""
        skills = ["Python", "python", "Python3", "JavaScript", "js"]
        groups = self.service.group_similar_skills(skills)

        assert "python" in groups
        assert len(groups["python"]) == 3
        assert "javascript" in groups
        assert len(groups["javascript"]) == 2

    def test_find_skill_synonyms(self):
        """Test finding synonyms for a skill"""
        synonyms = self.service.find_skill_synonyms("Python")
        assert "python" in synonyms
        assert "python3" in synonyms

    def test_is_valid_skill(self):
        """Test skill validation"""
        assert self.service.is_valid_skill("Python") == True
        assert self.service.is_valid_skill("") == False
        assert self.service.is_valid_skill("123") == False
        assert self.service.is_valid_skill("!!!") == False

    def test_extract_skill_category(self):
        """Test skill category extraction"""
        assert self.service.extract_skill_category("Python") == "programming_language"
        assert self.service.extract_skill_category("React") == "frontend"
        assert self.service.extract_skill_category("Django") == "backend"
        assert self.service.extract_skill_category("PostgreSQL") == "database"
        assert self.service.extract_skill_category("Docker") == "devops"
        assert self.service.extract_skill_category("AWS") == "cloud"
        assert self.service.extract_skill_category("TensorFlow") == "machine_learning"
        assert self.service.extract_skill_category("pytest") == "testing"


class TestConfidenceCalculator:
    """Test Confidence Calculator Service"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = ConfidenceCalculatorService()

    def test_cv_only_base_score(self):
        """Test CV-only base score is 60%"""
        sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
        result = self.service.calculate_skill_confidence("Python", sources)
        assert result["base_score"] == 60
        assert result["confidence_level"] == "medium"

    def test_cv_github_base_score(self):
        """Test CV + GitHub base score is 75%"""
        sources = {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        result = self.service.calculate_skill_confidence("Python", sources)
        assert result["base_score"] == 75
        assert result["confidence_level"] == "high"

    def test_cv_github_web_base_score(self):
        """Test CV + GitHub + Web base score is 90%"""
        sources = {"cv": True, "github": True, "web_mentions": True, "stackoverflow": False}
        result = self.service.calculate_skill_confidence("Python", sources)
        assert result["base_score"] == 90
        assert result["confidence_level"] == "expert"

    def test_all_sources_base_score(self):
        """Test all sources base score is 95%"""
        sources = {"cv": True, "github": True, "web_mentions": True, "stackoverflow": True}
        result = self.service.calculate_skill_confidence("Python", sources)
        assert result["base_score"] == 95
        assert result["confidence_level"] == "expert"

    def test_endorsement_bonus(self):
        """Test endorsement bonus adds 5%"""
        sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
        evidence = {"endorsements": 3}
        result = self.service.calculate_skill_confidence("Python", sources, evidence)
        assert result["total_bonus"] == 5
        assert result["confidence_score"] == 65  # 60 + 5

    def test_articles_bonus(self):
        """Test articles bonus adds 5%"""
        sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
        evidence = {"articles_written": 2}
        result = self.service.calculate_skill_confidence("Python", sources, evidence)
        assert result["total_bonus"] == 5
        assert result["confidence_score"] == 65  # 60 + 5

    def test_recent_activity_bonus_very_recent(self):
        """Test recent activity bonus for very recent activity (< 3 months)"""
        sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
        last_activity = datetime.now() - timedelta(days=60)  # 2 months ago
        evidence = {"last_activity_date": last_activity}
        result = self.service.calculate_skill_confidence("Python", sources, evidence)
        assert result["total_bonus"] == 10  # Very recent bonus
        assert result["confidence_score"] == 70  # 60 + 10

    def test_recent_activity_bonus_recent(self):
        """Test recent activity bonus for recent activity (3-6 months)"""
        sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
        last_activity = datetime.now() - timedelta(days=120)  # 4 months ago
        evidence = {"last_activity_date": last_activity}
        result = self.service.calculate_skill_confidence("Python", sources, evidence)
        assert result["total_bonus"] == 5  # Recent bonus
        assert result["confidence_score"] == 65  # 60 + 5

    def test_all_bonuses_combined(self):
        """Test all bonuses combined"""
        sources = {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        last_activity = datetime.now() - timedelta(days=30)
        evidence = {
            "endorsements": 5,
            "articles_written": 3,
            "last_activity_date": last_activity
        }
        result = self.service.calculate_skill_confidence("Python", sources, evidence)
        # Base: 75, Endorsements: +5, Articles: +5, Very recent: +10 = 95
        assert result["total_bonus"] == 20
        assert result["confidence_score"] == 95

    def test_confidence_score_capped_at_100(self):
        """Test that confidence score is capped at 100"""
        sources = {"cv": True, "github": True, "web_mentions": True, "stackoverflow": True}
        last_activity = datetime.now() - timedelta(days=10)
        evidence = {
            "endorsements": 10,
            "articles_written": 10,
            "last_activity_date": last_activity
        }
        result = self.service.calculate_skill_confidence("Python", sources, evidence)
        # Base: 95, bonuses: 20, total would be 115, but capped at 100
        assert result["confidence_score"] == 100

    def test_github_only_no_cv(self):
        """Test GitHub only (no CV) gives 50%"""
        sources = {"cv": False, "github": True, "web_mentions": False, "stackoverflow": False}
        result = self.service.calculate_skill_confidence("Python", sources)
        assert result["base_score"] == 50

    def test_merge_skill_sources(self):
        """Test merging skills from multiple sources"""
        cv_skills = ["Python", "JavaScript"]
        github_skills = ["Python", "React"]
        web_skills = ["Python", "Django"]
        so_skills = ["Python"]

        merged = self.service.merge_skill_sources(cv_skills, github_skills, web_skills, so_skills)

        assert "Python" in merged
        assert merged["Python"]["cv"] == True
        assert merged["Python"]["github"] == True
        assert merged["Python"]["web_mentions"] == True
        assert merged["Python"]["stackoverflow"] == True

        assert "React" in merged
        assert merged["React"]["cv"] == False
        assert merged["React"]["github"] == True

    def test_detect_skill_conflicts_single_source(self):
        """Test detecting skills from single source"""
        skill_sources = {
            "Python": {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False},
            "React": {"cv": False, "github": True, "web_mentions": False, "stackoverflow": False}
        }

        conflicts = self.service.detect_skill_conflicts(skill_sources)
        assert len(conflicts) == 2
        # React is high risk (single source, no CV)
        react_conflict = [c for c in conflicts if c["skill"] == "React"][0]
        assert react_conflict["risk"] == "high"


class TestHallucinationDetector:
    """Test Hallucination Detector Service"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = HallucinationDetectorService()

    def test_single_source_increases_risk(self):
        """Test that single source increases risk"""
        sources = {"cv": False, "github": True, "web_mentions": False, "stackoverflow": False}
        result = self.service.analyze_skill("Python", sources)
        assert result["risk_score"] > 0
        assert "single_source" in [f["factor"] for f in result["risk_factors"]]

    def test_no_primary_source_high_risk(self):
        """Test that missing primary sources is high risk"""
        sources = {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False}
        result = self.service.analyze_skill("Python", sources)
        assert result["risk_score"] >= 40
        assert any(f["severity"] == "high" for f in result["risk_factors"])

    def test_vague_skill_increases_risk(self):
        """Test that vague skills increase risk"""
        sources = {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        result = self.service.analyze_skill("programming", sources)  # Vague skill
        assert "vague_skill" in [f["factor"] for f in result["risk_factors"]]

    def test_high_level_skill_without_evidence(self):
        """Test high-level skill without evidence is high risk"""
        sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
        evidence = {}  # No evidence
        result = self.service.analyze_skill("machine learning", sources, evidence)
        assert any(f["factor"] == "no_evidence" for f in result["risk_factors"])

    def test_skill_with_evidence_lower_risk(self):
        """Test skill with evidence has lower risk"""
        sources = {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        evidence = {"repository_count": 5, "commit_count": 100}
        result = self.service.analyze_skill("machine learning", sources, evidence)
        # Should not have no_evidence factor
        assert not any(f["factor"] == "no_evidence" for f in result["risk_factors"])

    def test_stale_skill_increases_risk(self):
        """Test old skills increase risk"""
        sources = {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        old_date = datetime.now() - timedelta(days=500)
        evidence = {"last_activity_date": old_date}
        result = self.service.analyze_skill("Python", sources, evidence)
        assert any(f["factor"] == "stale_skill" for f in result["risk_factors"])

    def test_high_risk_score_is_hallucination(self):
        """Test high risk score is flagged as hallucination"""
        # Multiple risk factors: single source, no CV, no GitHub, vague skill
        sources = {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False}
        result = self.service.analyze_skill("coding", sources)
        assert result["risk_score"] >= 60
        assert result["is_hallucination"] == True
        assert result["risk_level"] == "high"

    def test_low_risk_score_not_hallucination(self):
        """Test low risk score is not hallucination"""
        sources = {"cv": True, "github": True, "web_mentions": True, "stackoverflow": False}
        evidence = {"repository_count": 10, "commit_count": 500}
        result = self.service.analyze_skill("Python", sources, evidence)
        assert result["is_hallucination"] == False

    def test_analyze_skill_list(self):
        """Test analyzing multiple skills"""
        skills_with_sources = {
            "Python": {"cv": True, "github": True, "web_mentions": True, "stackoverflow": True},
            "coding": {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False},
            "React": {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        }

        result = self.service.analyze_skill_list(skills_with_sources)
        assert result["total_skills"] == 3
        assert result["hallucination_count"] >= 1  # "coding" should be flagged
        assert "coding" in result["flagged_skills"]

    def test_filter_hallucinations(self):
        """Test filtering out hallucinations"""
        skills_with_sources = {
            "Python": {"cv": True, "github": True, "web_mentions": True, "stackoverflow": True},
            "coding": {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False},
            "React": {"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}
        }

        analysis = self.service.analyze_skill_list(skills_with_sources)
        validated = self.service.filter_hallucinations(analysis, exclude_threshold=60)

        assert "Python" in validated
        assert "React" in validated
        assert "coding" not in validated  # Should be filtered out

    def test_get_validation_report(self):
        """Test generating validation report"""
        skills_with_sources = {
            "Python": {"cv": True, "github": True, "web_mentions": True, "stackoverflow": True},
            "coding": {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False}
        }

        analysis = self.service.analyze_skill_list(skills_with_sources)
        report = self.service.get_validation_report(analysis)

        assert "SKILL VALIDATION REPORT" in report
        assert "Total Skills Analyzed" in report
        assert str(analysis["total_skills"]) in report


def run_all_tests():
    """Run all Phase 3 service tests"""
    print("=" * 60)
    print("Running Phase 3 Service Tests")
    print("=" * 60)

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_all_tests()
