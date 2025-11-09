"""
End-to-End Integration Test for GPT Scoring System
Tests the complete flow from data collection to GPT scoring
"""
import asyncio
from app.services.gpt_scoring_service import get_gpt_scoring_service
from app.services.skill_validation_service import SkillValidationService
from app.aggregation.data_aggregator import DataAggregator
from app.database import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_sample_profile():
    """
    Test GPT scoring with a sample developer profile
    """
    print("\n" + "="*80)
    print("GPT SCORING INTEGRATION TEST")
    print("="*80 + "\n")

    # Sample profile data
    sample_github_data = {
        "username": "testdev",
        "name": "Test Developer",
        "bio": "Full-stack engineer passionate about Python and machine learning",
        "public_repos": 42,
        "followers": 150,
        "languages": {"Python": 15, "JavaScript": 10, "Go": 5},
        "repositories": [
            {
                "name": "ml-pipeline",
                "description": "Production ML pipeline with FastAPI and TensorFlow",
                "language": "Python",
                "stars": 45,
                "forks": 12
            },
            {
                "name": "react-dashboard",
                "description": "Real-time analytics dashboard with React and D3",
                "language": "JavaScript",
                "stars": 28,
                "forks": 5
            }
        ],
        "readme_samples": [
            {
                "repo_name": "ml-pipeline",
                "content": """# ML Pipeline

Production-ready machine learning pipeline built with:
- FastAPI for REST API
- TensorFlow 2.x for model training
- Docker for containerization
- PostgreSQL for data storage

Features:
- Automated model training and evaluation
- Real-time inference API
- Model versioning and rollback
- Comprehensive monitoring and logging

Used in production serving 1M+ requests/day.""",
                "stars": 45,
                "language": "Python"
            }
        ],
        "commit_samples": [
            {"message": "feat: Add distributed training support with Horovod"},
            {"message": "fix: Resolve memory leak in data preprocessing pipeline"},
            {"message": "docs: Update API documentation with OpenAPI schema"},
            {"message": "perf: Optimize database queries with connection pooling"},
            {"message": "feat: Implement A/B testing framework for model evaluation"}
        ],
        "commit_statistics": {
            "commit_frequency": "daily",
            "has_conventional_commits": True,
            "conventional_commit_percentage": 90.0
        }
    }

    sample_linkedin_data = {
        "full_name": "Test Developer",
        "headline": "Senior Machine Learning Engineer | Python | TensorFlow",
        "summary": "Experienced ML engineer with 6+ years building production systems. Specialized in deep learning, NLP, and scalable data pipelines.",
        "experience": [
            {
                "title": "Senior ML Engineer",
                "company": "Tech Corp",
                "description": "Led ML infrastructure team. Built production ML pipelines serving millions of users."
            },
            {
                "title": "ML Engineer",
                "company": "Data Inc",
                "description": "Developed recommendation systems and NLP models."
            }
        ],
        "skills": ["Python", "TensorFlow", "Machine Learning", "FastAPI", "Docker", "PostgreSQL", "React"]
    }

    sample_cv_data = {
        "skills": ["Python", "Machine Learning", "TensorFlow", "FastAPI", "Docker", "PostgreSQL"],
        "work_history": [
            {
                "title": "Senior ML Engineer",
                "company": "Tech Corp",
                "duration": "2020-Present"
            }
        ],
        "education": [
            {
                "degree": "MS Computer Science",
                "institution": "University",
                "year": "2017"
            }
        ]
    }

    # Test 1: Score Individual Skills
    print("TEST 1: Individual Skill Scoring")
    print("-" * 80)

    gpt_scorer = get_gpt_scoring_service()

    skills_to_test = ["Python", "TensorFlow", "Docker", "FastAPI"]

    for skill in skills_to_test:
        print(f"\nScoring: {skill}")
        result = await gpt_scorer.score_skill_confidence(
            skill,
            github_data=sample_github_data,
            linkedin_data=sample_linkedin_data,
            cv_data=sample_cv_data
        )

        print(f"  Confidence: {result['confidence_score']}%")
        print(f"  Proficiency: {result['proficiency_level']}")
        print(f"  Years Experience: {result['years_experience']}")
        print(f"  Evidence Quality: {result['evidence_quality']}")
        print(f"  Reasoning: {result['reasoning'][:150]}...")

    # Test 2: Batch Skill Scoring
    print("\n\nTEST 2: Batch Skill Scoring")
    print("-" * 80)

    all_skills = ["Python", "JavaScript", "TensorFlow", "FastAPI", "Docker", "React", "PostgreSQL"]

    batch_results = await gpt_scorer.score_multiple_skills(
        all_skills,
        github_data=sample_github_data,
        linkedin_data=sample_linkedin_data,
        cv_data=sample_cv_data
    )

    print(f"\nScored {len(batch_results)} skills:")
    print("\nSkill                 | Confidence | Proficiency | Years | Quality")
    print("-" * 80)
    for result in batch_results:
        skill = result.get('skill', 'Unknown')
        conf = result.get('confidence_score', 0)
        prof = result.get('proficiency_level', 'N/A')
        years = result.get('years_experience', 0)
        qual = result.get('evidence_quality', 'N/A')
        print(f"{skill:20} | {conf:>10}% | {prof:11} | {years:>5} | {qual}")

    # Test 3: Profile Quality Assessment
    print("\n\nTEST 3: Profile Quality Assessment")
    print("-" * 80)

    profile_quality = await gpt_scorer.calculate_profile_quality(
        github_data=sample_github_data,
        linkedin_data=sample_linkedin_data,
        cv_data=sample_cv_data
    )

    print(f"\nOverall Quality Score: {profile_quality['overall_quality_score']}/100")
    print(f"Profile Completeness: {profile_quality['profile_completeness']}/100")
    print(f"Technical Depth: {profile_quality['technical_depth']}")
    print(f"Professional Presence: {profile_quality['professional_presence']}")
    print(f"Activity Level: {profile_quality['activity_level']}")
    print(f"Hirability Score: {profile_quality['hirability_score']}/100")

    print(f"\nStrengths:")
    for strength in profile_quality.get('strengths', []):
        print(f"  ✓ {strength}")

    print(f"\nAreas for Improvement:")
    for area in profile_quality.get('areas_for_improvement', []):
        print(f"  → {area}")

    print(f"\nSummary:")
    print(f"  {profile_quality.get('summary', 'N/A')}")

    print(f"\nRecommended Roles:")
    for role in profile_quality.get('recommended_for', []):
        print(f"  • {role}")

    # Test 4: Compare with Legacy Scoring
    print("\n\nTEST 4: GPT vs Legacy Scoring Comparison")
    print("-" * 80)

    print("\nGPT Scoring:")
    print(f"  Average Confidence: {sum(r['confidence_score'] for r in batch_results) / len(batch_results):.1f}%")
    print(f"  Provides: Proficiency levels, years experience, evidence quality, reasoning")

    print("\nLegacy Scoring (Mathematical):")
    print(f"  Would be: 75% (CV + GitHub)")
    print(f"  Provides: Only confidence percentage")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


async def test_with_real_submission(submission_id: str):
    """
    Test GPT scoring with a real submission from database

    Args:
        submission_id: UUID of existing submission
    """
    print("\n" + "="*80)
    print(f"TESTING WITH REAL SUBMISSION: {submission_id}")
    print("="*80 + "\n")

    db = SessionLocal()

    try:
        # Test Skill Validation Service
        print("Running Skill Validation with GPT Scoring...")
        validation_service = SkillValidationService(use_gpt_scoring=True)
        from uuid import UUID
        result = validation_service.validate_submission_skills(
            submission_id=UUID(submission_id),
            db=db
        )

        print(f"\nValidation Results:")
        print(f"  Total Skills: {result['total_skills_validated']}")
        print(f"  Average Confidence: {result['profile_confidence']['average_score']}%")

        print(f"\nTop 5 Skills:")
        for skill_data in result['validated_skills'][:5]:
            print(f"  - {skill_data['skill']}: {skill_data['confidence_score']}% "
                  f"({skill_data.get('proficiency_level', 'N/A')})")

        # Test Data Aggregator
        print("\n\nRunning Data Aggregation with GPT Quality...")
        aggregator = DataAggregator(db, use_gpt_quality=True)
        aggregated = await aggregator.aggregate(submission_id)

        print(f"\nAggregation Results:")
        print(f"  Overall Quality: {float(aggregated.overall_quality_score):.2f}/100")
        print(f"  Data Freshness: {float(aggregated.data_freshness_score):.2f}/100")
        print(f"  Sources Collected: {aggregated.sources_collected}/{aggregated.total_sources_attempted}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

    print("\n" + "="*80)
    print("REAL SUBMISSION TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    print("\n🚀 Starting GPT Scoring Integration Tests\n")

    # Run sample profile test
    asyncio.run(test_sample_profile())

    # To test with real submission, uncomment and provide submission ID:
    # asyncio.run(test_with_real_submission("your-submission-id-here"))

    print("\n✅ All tests completed successfully!\n")
