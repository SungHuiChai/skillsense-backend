"""
Comprehensive API tests for GitHub Integration and Skills Dashboard features.

This test suite validates:
1. Authentication endpoints
2. CV submission endpoints
3. Collection status endpoints
4. GitHub results endpoints
5. Skills analysis endpoints
"""

import pytest
import httpx
from uuid import UUID
import json


# Test configuration
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:8080"
TEST_USER = {
    "email": "testuser@example.com",
    "password": "password123"
}
TEST_SUBMISSION_ID = "85c7bd86-c30d-4cab-a22c-004f3a11b134"
GITHUB_USERNAME = "K1ta141k"


class TestAuthentication:
    """Test authentication endpoints"""

    @pytest.mark.asyncio
    async def test_user_login_success(self):
        """Test successful user login"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )

            assert response.status_code == 200, f"Login failed: {response.text}"
            data = response.json()
            assert "access_token" in data, "No access token in response"
            assert data["token_type"] == "bearer", "Wrong token type"
            assert data["access_token"], "Access token is empty"

    @pytest.mark.asyncio
    async def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": "testuser@example.com", "password": "wrongpassword"}
            )

            assert response.status_code == 401, "Should return 401 for invalid credentials"
            data = response.json()
            assert "detail" in data, "No error detail in response"

    @pytest.mark.asyncio
    async def test_get_current_user(self):
        """Test getting current user information"""
        # First login to get token
        async with httpx.AsyncClient() as client:
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get current user
            response = await client.get(
                f"{BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Get current user failed: {response.text}"
            data = response.json()
            assert data["email"] == TEST_USER["email"], "Email doesn't match"
            assert "id" in data, "No user ID in response"


class TestCVSubmissions:
    """Test CV submission endpoints"""

    @pytest.mark.asyncio
    async def test_get_submissions_list(self):
        """Test retrieving user's CV submissions"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get submissions
            response = await client.get(
                f"{BASE_URL}/api/v1/cv/submissions",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Get submissions failed: {response.text}"
            data = response.json()
            assert isinstance(data, list), "Response should be a list"

            # Check if test submission exists
            submission_ids = [s["id"] for s in data]
            assert TEST_SUBMISSION_ID in submission_ids, f"Test submission {TEST_SUBMISSION_ID} not found"

    @pytest.mark.asyncio
    async def test_get_submission_details(self):
        """Test retrieving specific submission details"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get submission details
            response = await client.get(
                f"{BASE_URL}/api/v1/cv/submissions/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Get submission details failed: {response.text}"
            data = response.json()
            assert data["id"] == TEST_SUBMISSION_ID, "Wrong submission ID"
            assert "status" in data, "No status field"
            assert "filename" in data, "No filename field"


class TestCollectionStatus:
    """Test data collection status endpoints"""

    @pytest.mark.asyncio
    async def test_get_collection_status(self):
        """Test retrieving collection status for submission"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get collection status
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/status/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Get collection status failed: {response.text}"
            data = response.json()
            assert "submission_id" in data, "No submission_id in response"
            assert "sources" in data, "No sources in response"

            # Validate sources structure
            if data["sources"]:
                for source_name, source_data in data["sources"].items():
                    assert "status" in source_data, f"No status for source {source_name}"
                    assert "collected_at" in source_data or source_data["status"] == "pending", \
                        f"No collected_at for completed source {source_name}"


class TestGitHubResults:
    """Test GitHub data collection results endpoints"""

    @pytest.mark.asyncio
    async def test_get_github_results(self):
        """Test retrieving GitHub collection results"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get GitHub results
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/results/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Get GitHub results failed: {response.text}"
            data = response.json()

            # Validate structure
            assert "submission_id" in data, "No submission_id in response"
            assert "github_data" in data or "github" in data, "No GitHub data in response"

            # Get GitHub data (handle different response structures)
            github_data = data.get("github_data") or data.get("github")

            if github_data:
                # Validate GitHub profile data
                assert "username" in github_data, "No username in GitHub data"
                assert github_data["username"] == GITHUB_USERNAME, f"Expected username {GITHUB_USERNAME}"

                # Validate profile stats
                assert "public_repos" in github_data, "No public_repos in GitHub data"
                assert "followers" in github_data, "No followers in GitHub data"

                # Validate repositories
                assert "repositories" in github_data, "No repositories in GitHub data"
                repos = github_data["repositories"]
                assert isinstance(repos, list), "Repositories should be a list"
                assert len(repos) >= 20, f"Expected at least 20 repos, got {len(repos)}"

                # Validate languages
                assert "languages" in github_data, "No languages in GitHub data"
                languages = github_data["languages"]
                assert isinstance(languages, dict), "Languages should be a dictionary"

                # Validate technologies/frameworks
                assert "technologies" in github_data or "frameworks" in github_data, \
                    "No technologies/frameworks in GitHub data"

    @pytest.mark.asyncio
    async def test_get_github_results_unauthorized(self):
        """Test GitHub results access without authentication"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/results/{TEST_SUBMISSION_ID}"
            )

            assert response.status_code == 401, "Should require authentication"


class TestSkillsAnalysis:
    """Test GPT-4o skills analysis endpoints"""

    @pytest.mark.asyncio
    async def test_get_github_analysis(self):
        """Test retrieving GPT-4o GitHub analysis"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get GitHub analysis
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/analysis/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Get GitHub analysis failed: {response.text}"
            data = response.json()

            # Validate core structure
            assert "submission_id" in data, "No submission_id in response"
            assert "github_username" in data, "No github_username in response"
            assert data["github_username"] == GITHUB_USERNAME, f"Expected username {GITHUB_USERNAME}"

            # Validate skills analysis section
            assert "skills_analysis" in data, "No skills_analysis in response"
            skills = data["skills_analysis"]

            assert "technical_skills" in skills, "No technical_skills in skills_analysis"
            assert isinstance(skills["technical_skills"], list), "technical_skills should be a list"

            assert "frameworks" in skills, "No frameworks in skills_analysis"
            assert isinstance(skills["frameworks"], list), "frameworks should be a list"

            assert "languages" in skills, "No languages in skills_analysis"
            assert isinstance(skills["languages"], list), "languages should be a list"

            assert "tools" in skills, "No tools in skills_analysis"
            assert isinstance(skills["tools"], list), "tools should be a list"

            assert "domains" in skills, "No domains in skills_analysis"
            assert isinstance(skills["domains"], list), "domains should be a list"

            assert "soft_skills" in skills, "No soft_skills in skills_analysis"
            assert isinstance(skills["soft_skills"], list), "soft_skills should be a list"

            # Validate activity analysis section
            assert "activity_analysis" in data, "No activity_analysis in response"
            activity = data["activity_analysis"]

            assert "activity_level" in activity, "No activity_level in activity_analysis"
            assert activity["activity_level"] == "very_high", \
                f"Expected activity_level 'very_high', got '{activity['activity_level']}'"

            assert "commit_quality_score" in activity, "No commit_quality_score in activity_analysis"
            assert activity["commit_quality_score"] == 85, \
                f"Expected commit_quality_score 85, got {activity['commit_quality_score']}"

            assert "collaboration_score" in activity, "No collaboration_score in activity_analysis"
            assert "project_diversity" in activity, "No project_diversity in activity_analysis"

            assert "strengths" in activity, "No strengths in activity_analysis"
            assert isinstance(activity["strengths"], list), "strengths should be a list"

            assert "areas_for_growth" in activity, "No areas_for_growth in activity_analysis"
            assert isinstance(activity["areas_for_growth"], list), "areas_for_growth should be a list"

            # Validate professional summary
            assert "professional_summary" in data, "No professional_summary in response"
            assert isinstance(data["professional_summary"], str), "professional_summary should be a string"
            assert len(data["professional_summary"]) > 0, "professional_summary is empty"

    @pytest.mark.asyncio
    async def test_get_github_analysis_data_completeness(self):
        """Test that GitHub analysis contains complete data"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get GitHub analysis
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/analysis/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )

            data = response.json()

            # Ensure all skill categories have data
            skills = data["skills_analysis"]
            assert len(skills["technical_skills"]) > 0, "technical_skills is empty"
            assert len(skills["languages"]) > 0, "languages is empty"

            # Ensure activity insights are present
            activity = data["activity_analysis"]
            assert "insights" in activity, "No insights in activity_analysis"
            insights = activity["insights"]

            assert "activity_insights" in insights, "No activity_insights"
            assert "commit_quality_insights" in insights, "No commit_quality_insights"
            assert "collaboration_insights" in insights, "No collaboration_insights"
            assert "project_insights" in insights, "No project_insights"


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_submission(self):
        """Test accessing non-existent submission"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Try to get non-existent submission
            fake_id = "00000000-0000-0000-0000-000000000000"
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/status/{fake_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 404, "Should return 404 for non-existent submission"

    @pytest.mark.asyncio
    async def test_invalid_submission_id_format(self):
        """Test handling of invalid UUID format"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Try invalid UUID format
            response = await client.get(
                f"{BASE_URL}/api/v1/collection/status/not-a-valid-uuid",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code in [400, 422], \
                "Should return 400 or 422 for invalid UUID format"


class TestDataIntegrity:
    """Test data integrity and consistency"""

    @pytest.mark.asyncio
    async def test_github_data_matches_analysis(self):
        """Test that GitHub username matches between results and analysis"""
        async with httpx.AsyncClient() as client:
            # Login first
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=TEST_USER
            )
            token = login_response.json()["access_token"]

            # Get GitHub results
            results_response = await client.get(
                f"{BASE_URL}/api/v1/collection/results/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )
            results_data = results_response.json()

            # Get GitHub analysis
            analysis_response = await client.get(
                f"{BASE_URL}/api/v1/collection/analysis/{TEST_SUBMISSION_ID}",
                headers={"Authorization": f"Bearer {token}"}
            )
            analysis_data = analysis_response.json()

            # Extract GitHub username from results
            github_data = results_data.get("github_data") or results_data.get("github")
            results_username = github_data["username"] if github_data else None

            # Extract GitHub username from analysis
            analysis_username = analysis_data.get("github_username")

            assert results_username == analysis_username, \
                f"GitHub username mismatch: results={results_username}, analysis={analysis_username}"
            assert results_username == GITHUB_USERNAME, \
                f"Expected username {GITHUB_USERNAME}, got {results_username}"


# Test execution summary
if __name__ == "__main__":
    print("GitHub Integration and Skills Dashboard API Tests")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test User: {TEST_USER['email']}")
    print(f"Test Submission ID: {TEST_SUBMISSION_ID}")
    print(f"Expected GitHub Username: {GITHUB_USERNAME}")
    print("=" * 80)
    print("\nRun with: pytest -v tests/test_github_integration_api.py")
