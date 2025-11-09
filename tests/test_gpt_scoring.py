"""
Test suite for GPT Scoring Service
"""
import pytest
import asyncio
from app.services.gpt_scoring_service import GPTScoringService, get_gpt_scoring_service


def test_service_initialization():
    """Test that service initializes correctly"""
    service = GPTScoringService()
    assert service is not None


def test_singleton_pattern():
    """Test that get_gpt_scoring_service returns same instance"""
    service1 = get_gpt_scoring_service()
    service2 = get_gpt_scoring_service()
    assert service1 is service2


@pytest.mark.asyncio
async def test_fallback_skill_score():
    """Test fallback scoring when GPT unavailable"""
    service = GPTScoringService()

    # Force client to None to test fallback
    service.client = None

    result = await service.score_skill_confidence("Python")

    assert result["skill"] == "Python"
    assert "confidence_score" in result
    assert "proficiency_level" in result
    assert "years_experience" in result
    assert result["confidence_score"] == 50  # Fallback default


@pytest.mark.asyncio
async def test_score_with_github_data():
    """Test scoring with GitHub data"""
    service = get_gpt_scoring_service()

    github_data = {
        "username": "testuser",
        "languages": {"Python": 15, "JavaScript": 8},
        "readme_samples": [
            {
                "repo_name": "ml-pipeline",
                "content": "A machine learning pipeline built with Python and scikit-learn",
                "stars": 50
            }
        ],
        "commit_samples": [
            {"message": "feat: Add Python data preprocessing module"},
            {"message": "fix: Update Python dependencies"}
        ],
        "commit_statistics": {
            "commit_frequency": "daily",
            "has_conventional_commits": True
        }
    }

    result = await service.score_skill_confidence(
        "Python",
        github_data=github_data
    )

    assert result["skill"] == "Python"
    assert 0 <= result["confidence_score"] <= 100
    assert result["proficiency_level"] in ["beginner", "intermediate", "advanced", "expert"]
    assert isinstance(result["years_experience"], int)
    assert result["evidence_quality"] in ["low", "medium", "high", "excellent"]


@pytest.mark.asyncio
async def test_score_multiple_skills():
    """Test batch scoring of multiple skills"""
    service = get_gpt_scoring_service()

    skills = ["Python", "JavaScript", "Docker"]

    github_data = {
        "username": "testuser",
        "languages": {"Python": 10, "JavaScript": 5},
        "readme_samples": [],
        "commit_samples": []
    }

    results = await service.score_multiple_skills(
        skills,
        github_data=github_data
    )

    assert isinstance(results, list)
    assert len(results) <= len(skills)  # May return fewer if GPT unavailable

    for result in results:
        assert "skill" in result
        assert "confidence_score" in result


@pytest.mark.asyncio
async def test_calculate_profile_quality():
    """Test profile quality calculation"""
    service = get_gpt_scoring_service()

    github_data = {
        "username": "testuser",
        "public_repos": 25,
        "followers": 50,
        "languages": {"Python": 10, "JavaScript": 8},
        "readme_samples": [{"repo_name": "test", "content": "Test project"}],
        "commit_samples": [{"message": "Initial commit"}],
        "commit_statistics": {"commit_frequency": "weekly"}
    }

    linkedin_data = {
        "full_name": "Test User",
        "headline": "Software Engineer",
        "experience": [{"title": "Developer", "company": "Tech Corp"}],
        "skills": ["Python", "JavaScript"]
    }

    result = await service.calculate_profile_quality(
        github_data=github_data,
        linkedin_data=linkedin_data
    )

    assert "overall_quality_score" in result
    assert 0 <= result["overall_quality_score"] <= 100
    assert "profile_completeness" in result
    assert result["data_richness"] in ["poor", "fair", "good", "excellent"]
    assert result["technical_depth"] in ["low", "medium", "high", "exceptional"]


@pytest.mark.asyncio
async def test_context_preparation():
    """Test that context is properly formatted"""
    service = GPTScoringService()

    github_data = {
        "username": "testuser",
        "languages": {"Python": 5},
        "readme_samples": [{"repo_name": "test", "content": "Python project"}]
    }

    context = service._prepare_skill_context(
        "Python",
        github_data=github_data,
        linkedin_data=None,
        web_mentions=None,
        cv_data=None
    )

    assert "Python" in context
    assert "testuser" in context or "GITHUB" in context


if __name__ == "__main__":
    # Run tests
    print("Running GPT Scoring Service tests...")
    pytest.main([__file__, "-v"])
