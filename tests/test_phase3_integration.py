#!/usr/bin/env python3
"""
Phase 3 Integration Tests
Tests the complete Phase 3 processing pipeline
"""
import pytest
import sys
import os
from uuid import uuid4
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_phase3_imports():
    """Test that all Phase 3 modules can be imported"""
    try:
        from app.services.chatgpt_web_search import get_web_search_service
        from app.services.skill_normalization import get_normalization_service
        from app.services.confidence_calculator import get_confidence_calculator
        from app.services.hallucination_detector import get_hallucination_detector
        from app.services.web_source_orchestrator import get_web_orchestrator
        from app.services.skill_validation_service import get_validation_service
        from app.services.skill_profile_service import get_profile_service
        from app.api import processing, skills
        from app.models.collected_data import StackOverflowData, SkillWebMention

        # All imports successful
        assert True
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


def test_normalization_service_initialization():
    """Test that normalization service initializes correctly"""
    from app.services.skill_normalization import get_normalization_service

    service = get_normalization_service()
    assert service is not None

    # Test basic normalization
    normalized = service.normalize_skill("Python")
    assert normalized == "python"

    normalized = service.normalize_skill("JavaScript")
    assert normalized == "javascript"


def test_confidence_calculator_initialization():
    """Test that confidence calculator initializes correctly"""
    from app.services.confidence_calculator import get_confidence_calculator

    calculator = get_confidence_calculator()
    assert calculator is not None

    # Test basic calculation
    sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
    result = calculator.calculate_skill_confidence("Python", sources)

    assert result["base_score"] == 60
    assert result["confidence_level"] == "medium"


def test_hallucination_detector_initialization():
    """Test that hallucination detector initializes correctly"""
    from app.services.hallucination_detector import get_hallucination_detector

    detector = get_hallucination_detector()
    assert detector is not None

    # Test basic detection
    sources = {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False}
    result = detector.analyze_skill("coding", sources)

    # Should have high risk score due to vague skill + no primary sources
    assert result["risk_score"] > 0


def test_validation_service_initialization():
    """Test that validation service initializes correctly"""
    from app.services.skill_validation_service import get_validation_service

    service = get_validation_service()
    assert service is not None


def test_profile_service_initialization():
    """Test that profile service initializes correctly"""
    from app.services.skill_profile_service import get_profile_service

    service = get_profile_service()
    assert service is not None


def test_web_orchestrator_initialization():
    """Test that web orchestrator initializes correctly"""
    import os

    # Skip if no OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not configured")

    from app.services.web_source_orchestrator import get_web_orchestrator

    orchestrator = get_web_orchestrator()
    assert orchestrator is not None


def test_database_models():
    """Test that Phase 3 database models are defined correctly"""
    from app.models.collected_data import StackOverflowData, SkillWebMention

    # Check StackOverflowData has required fields
    so_data = StackOverflowData(
        submission_id=str(uuid4()),
        username="testuser",
        reputation=1000
    )
    assert so_data.username == "testuser"
    assert so_data.reputation == 1000

    # Check SkillWebMention has required fields
    mention = SkillWebMention(
        submission_id=str(uuid4()),
        skill_name="Python",
        canonical_skill="python",
        url="https://example.com"
    )
    assert mention.skill_name == "Python"
    assert mention.canonical_skill == "python"


def test_skill_normalization_comprehensive():
    """Test comprehensive skill normalization scenarios"""
    from app.services.skill_normalization import get_normalization_service

    normalizer = get_normalization_service()

    # Test various skill variations
    test_cases = [
        (["Python", "python", "Python3"], ["python"]),
        (["JavaScript", "js", "ECMAScript"], ["javascript"]),
        (["React", "ReactJS", "react.js"], ["react"]),
        (["PostgreSQL", "postgres", "pg"], ["postgresql"]),
        (["Docker", "docker"], ["docker"])
    ]

    for inputs, expected in test_cases:
        result = normalizer.normalize_skills(inputs)
        assert result == expected, f"Failed for inputs {inputs}: expected {expected}, got {result}"


def test_confidence_scoring_algorithm():
    """Test that confidence scoring follows the exact algorithm"""
    from app.services.confidence_calculator import get_confidence_calculator

    calculator = get_confidence_calculator()

    # Test base scores
    test_cases = [
        ({"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}, 60),
        ({"cv": True, "github": True, "web_mentions": False, "stackoverflow": False}, 75),
        ({"cv": True, "github": True, "web_mentions": True, "stackoverflow": False}, 90),
        ({"cv": True, "github": True, "web_mentions": True, "stackoverflow": True}, 95),
    ]

    for sources, expected_score in test_cases:
        result = calculator.calculate_skill_confidence("Python", sources)
        assert result["base_score"] == expected_score, \
            f"Expected {expected_score}, got {result['base_score']} for sources {sources}"


def test_confidence_bonuses():
    """Test confidence score bonuses"""
    from app.services.confidence_calculator import get_confidence_calculator
    from datetime import datetime, timedelta

    calculator = get_confidence_calculator()

    # Test endorsement bonus
    sources = {"cv": True, "github": False, "web_mentions": False, "stackoverflow": False}
    evidence = {"endorsements": 3}
    result = calculator.calculate_skill_confidence("Python", sources, evidence)
    assert result["total_bonus"] == 5  # Endorsement bonus

    # Test articles bonus
    evidence = {"articles_written": 2}
    result = calculator.calculate_skill_confidence("Python", sources, evidence)
    assert result["total_bonus"] == 5  # Articles bonus

    # Test recent activity bonus
    last_activity = datetime.now() - timedelta(days=30)
    evidence = {"last_activity_date": last_activity}
    result = calculator.calculate_skill_confidence("Python", sources, evidence)
    assert result["total_bonus"] == 10  # Very recent activity bonus


def test_hallucination_detection_scenarios():
    """Test various hallucination detection scenarios"""
    from app.services.hallucination_detector import get_hallucination_detector

    detector = get_hallucination_detector()

    # Scenario 1: High risk - single source, no CV, vague skill
    sources = {"cv": False, "github": False, "web_mentions": True, "stackoverflow": False}
    result = detector.analyze_skill("coding", sources)
    assert result["risk_level"] in ["high", "medium"]

    # Scenario 2: Low risk - multiple sources, concrete skill
    sources = {"cv": True, "github": True, "web_mentions": True, "stackoverflow": False}
    evidence = {"repository_count": 5, "commit_count": 100}
    result = detector.analyze_skill("Python", sources, evidence)
    assert result["risk_level"] in ["minimal", "low"]


def test_skill_profile_categorization():
    """Test skill categorization"""
    from app.services.skill_normalization import get_normalization_service

    normalizer = get_normalization_service()

    # Test category detection
    assert normalizer.extract_skill_category("Python") == "programming_language"
    assert normalizer.extract_skill_category("React") == "frontend"
    assert normalizer.extract_skill_category("Django") == "backend"
    assert normalizer.extract_skill_category("PostgreSQL") == "database"
    assert normalizer.extract_skill_category("Docker") == "devops"
    assert normalizer.extract_skill_category("AWS") == "cloud"
    assert normalizer.extract_skill_category("TensorFlow") == "machine_learning"


def run_integration_tests():
    """Run all Phase 3 integration tests"""
    print("=" * 60)
    print("Running Phase 3 Integration Tests")
    print("=" * 60)

    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_integration_tests()
