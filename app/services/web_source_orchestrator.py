"""
Web Source Orchestrator
Coordinates extraction from Stack Overflow, web mentions, and personal blogs
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.services.chatgpt_web_search import get_web_search_service
from app.services.skill_normalization import get_normalization_service
from app.models.collected_data import StackOverflowData, SkillWebMention
from app.models.cv_submission import CVSubmission
from app.models.collected_data import GitHubData

logger = logging.getLogger(__name__)


class WebSourceOrchestrator:
    """
    Orchestrates web-based skill extraction from multiple sources:
    - Stack Overflow profiles
    - Web mentions and articles
    - Personal blogs and technical writing
    """

    def __init__(self):
        """Initialize orchestrator with services"""
        self.web_search = get_web_search_service()
        self.normalizer = get_normalization_service()

    async def process_submission(
        self,
        submission_id: UUID,
        db: Session,
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Process a submission to extract web-based skill data.

        Args:
            submission_id: CV submission ID
            db: Database session
            force_reprocess: If True, reprocess even if already done

        Returns:
            Processing results with skills and metadata
        """
        logger.info(f"Starting web source processing for submission {submission_id}")

        # Get submission
        submission = db.query(CVSubmission).filter(CVSubmission.id == str(submission_id)).first()
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        # Get GitHub data if available
        github_data = db.query(GitHubData).filter(
            GitHubData.submission_id == str(submission_id)
        ).first()

        # Build person context
        person_context = self._build_person_context(submission, github_data)

        results = {
            "submission_id": str(submission_id),
            "processing_started_at": datetime.now().isoformat(),
            "stackoverflow": {},
            "web_mentions": [],
            "blog": {},
            "skills_discovered": [],
            "processing_errors": []
        }

        # 1. Discover and process Stack Overflow
        try:
            stackoverflow_result = await self._process_stackoverflow(
                submission_id=submission_id,
                person_context=person_context,
                db=db,
                force_reprocess=force_reprocess
            )
            results["stackoverflow"] = stackoverflow_result
        except Exception as e:
            logger.error(f"Error processing Stack Overflow: {e}")
            results["processing_errors"].append({
                "source": "stackoverflow",
                "error": str(e)
            })

        # 2. Search for web mentions
        try:
            web_mentions_result = await self._process_web_mentions(
                submission_id=submission_id,
                person_context=person_context,
                db=db,
                force_reprocess=force_reprocess
            )
            results["web_mentions"] = web_mentions_result
        except Exception as e:
            logger.error(f"Error processing web mentions: {e}")
            results["processing_errors"].append({
                "source": "web_mentions",
                "error": str(e)
            })

        # 3. Discover personal blog
        try:
            blog_result = await self._process_blog(
                submission_id=submission_id,
                person_context=person_context,
                db=db,
                force_reprocess=force_reprocess
            )
            results["blog"] = blog_result
        except Exception as e:
            logger.error(f"Error processing blog: {e}")
            results["processing_errors"].append({
                "source": "blog",
                "error": str(e)
            })

        # 4. Consolidate skills from all sources
        all_skills = set()
        if results["stackoverflow"].get("skills"):
            all_skills.update(results["stackoverflow"]["skills"])
        if results["blog"].get("skills"):
            all_skills.update(results["blog"]["skills"])
        for mention in results["web_mentions"]:
            if mention.get("skills"):
                all_skills.update(mention["skills"])

        # Normalize skills
        results["skills_discovered"] = self.normalizer.normalize_skills(list(all_skills))

        results["processing_completed_at"] = datetime.now().isoformat()
        results["total_skills_discovered"] = len(results["skills_discovered"])

        logger.info(f"Web source processing complete. Discovered {len(results['skills_discovered'])} skills")

        return results

    def _build_person_context(
        self,
        submission: CVSubmission,
        github_data: Optional[GitHubData]
    ) -> Dict[str, Any]:
        """Build context about the person for search queries"""
        context = {
            "submission_id": submission.id,
            "full_name": None,
            "email": None,
            "github_username": None,
            "github_blog_url": None
        }

        # Get from extracted data if available
        if submission.extracted_data:
            context["full_name"] = submission.extracted_data.full_name
            context["email"] = submission.extracted_data.email

        # Get from GitHub data
        if github_data:
            context["github_username"] = github_data.username
            context["github_blog_url"] = github_data.blog
            if not context["full_name"]:
                context["full_name"] = github_data.name
            if not context["email"]:
                context["email"] = github_data.email

        return context

    async def _process_stackoverflow(
        self,
        submission_id: UUID,
        person_context: Dict[str, Any],
        db: Session,
        force_reprocess: bool
    ) -> Dict[str, Any]:
        """Process Stack Overflow profile discovery"""
        logger.info("Processing Stack Overflow profile")

        # Check if already processed
        existing = db.query(StackOverflowData).filter(
            StackOverflowData.submission_id == str(submission_id)
        ).first()

        if existing and not force_reprocess:
            logger.info("Stack Overflow data already exists, skipping")
            return {
                "status": "already_processed",
                "profile_found": existing.profile_url is not None,
                "skills": existing.skills_from_tags or []
            }

        # Discover Stack Overflow profile
        so_data = self.web_search.discover_stackoverflow_profile(
            full_name=person_context["full_name"],
            email=person_context["email"],
            github_username=person_context["github_username"]
        )

        result = {
            "status": "processed",
            "profile_found": so_data.get("profile_found", False),
            "skills": []
        }

        # Save to database if profile found
        if so_data.get("profile_found"):
            so_record = StackOverflowData(
                submission_id=str(submission_id),
                profile_url=so_data.get("profile_url"),
                username=so_data.get("username"),
                display_name=so_data.get("username"),
                reputation=so_data.get("reputation"),
                total_questions=so_data.get("total_questions"),
                total_answers=so_data.get("total_answers"),
                accepted_answers=so_data.get("accepted_answers"),
                activity_level=so_data.get("activity_level"),
                top_tags=so_data.get("top_tags", []),
                skills_from_tags=so_data.get("skills_from_tags", []),
                notable_questions=so_data.get("notable_contributions", []),
                raw_data=so_data,
                discovered_via="chatgpt_search"
            )

            if existing:
                # Update existing
                for key, value in so_record.__dict__.items():
                    if key != "_sa_instance_state" and key != "id":
                        setattr(existing, key, value)
                db.commit()
            else:
                db.add(so_record)
                db.commit()

            result["skills"] = so_data.get("skills_from_tags", [])
            logger.info(f"Stack Overflow profile saved. Found {len(result['skills'])} skills")
        else:
            logger.info("No Stack Overflow profile found")

        return result

    async def _process_web_mentions(
        self,
        submission_id: UUID,
        person_context: Dict[str, Any],
        db: Session,
        force_reprocess: bool
    ) -> List[Dict[str, Any]]:
        """Process web mentions and articles"""
        logger.info("Processing web mentions")

        # Check if already processed
        if not force_reprocess:
            existing_count = db.query(SkillWebMention).filter(
                SkillWebMention.submission_id == str(submission_id)
            ).count()
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing web mentions, skipping")
                existing_mentions = db.query(SkillWebMention).filter(
                    SkillWebMention.submission_id == str(submission_id)
                ).all()
                return [{
                    "skill": m.skill_name,
                    "url": m.url,
                    "source_type": m.source_type
                } for m in existing_mentions]

        # Search for web mentions
        web_data = self.web_search.search_skill_mentions(
            full_name=person_context["full_name"],
            github_username=person_context["github_username"],
            known_skills=None
        )

        mentions_result = []
        web_mentions = web_data.get("web_mentions", [])

        # Save each web mention to database
        for mention in web_mentions:
            skills_mentioned = mention.get("skills_mentioned", [])

            for skill in skills_mentioned:
                # Normalize skill
                canonical_skill = self.normalizer.normalize_skill(skill)

                # Determine credibility score
                credibility = mention.get("credibility", "medium")
                credibility_score = {
                    "high": 90,
                    "medium": 70,
                    "low": 50
                }.get(credibility, 70)

                mention_record = SkillWebMention(
                    submission_id=str(submission_id),
                    skill_name=skill,
                    canonical_skill=canonical_skill,
                    url=mention.get("url"),
                    title=mention.get("title"),
                    excerpt=mention.get("excerpt"),
                    source_type=mention.get("mention_type", "other"),
                    credibility=credibility,
                    credibility_score=credibility_score,
                    relevance_score=80,  # Default relevance
                    discovered_via="chatgpt_search",
                    search_query=f"{person_context['full_name']} {skill}",
                    raw_data=mention
                )

                db.add(mention_record)

                mentions_result.append({
                    "skill": canonical_skill,
                    "url": mention.get("url"),
                    "source_type": mention.get("mention_type"),
                    "credibility": credibility
                })

        db.commit()

        # Get unique skills
        unique_skills = set()
        for m in mentions_result:
            unique_skills.add(m["skill"])

        logger.info(f"Processed {len(web_mentions)} web mentions, found {len(unique_skills)} unique skills")

        return mentions_result

    async def _process_blog(
        self,
        submission_id: UUID,
        person_context: Dict[str, Any],
        db: Session,
        force_reprocess: bool
    ) -> Dict[str, Any]:
        """Process personal blog discovery"""
        logger.info("Processing personal blog")

        # Discover blog
        blog_data = self.web_search.discover_personal_blog(
            full_name=person_context["full_name"],
            github_username=person_context["github_username"],
            known_blog_url=person_context.get("github_blog_url")
        )

        result = {
            "status": "processed",
            "blog_found": blog_data.get("blog_found", False),
            "skills": []
        }

        # Extract skills from blog content
        if blog_data.get("blog_found"):
            skills_from_content = blog_data.get("skills_from_content", [])

            # Save blog mentions as skill web mentions
            for skill_data in skills_from_content:
                skill = skill_data.get("skill")
                canonical_skill = self.normalizer.normalize_skill(skill)

                # Determine credibility based on depth
                depth = skill_data.get("depth", "intermediate")
                credibility_score = {
                    "expert": 95,
                    "advanced": 85,
                    "intermediate": 75,
                    "beginner": 60
                }.get(depth, 75)

                mention_record = SkillWebMention(
                    submission_id=str(submission_id),
                    skill_name=skill,
                    canonical_skill=canonical_skill,
                    url=blog_data.get("blog_url"),
                    title=f"Blog: {skill}",
                    excerpt=skill_data.get("evidence", ""),
                    source_type="blog",
                    source_platform=blog_data.get("blog_url", "").split("//")[1].split("/")[0] if "://" in blog_data.get("blog_url", "") else "Unknown",
                    skill_depth=depth,
                    credibility="high",
                    credibility_score=credibility_score,
                    relevance_score=90,
                    discovered_via="blog_discovery",
                    raw_data=skill_data
                )

                db.add(mention_record)
                result["skills"].append(canonical_skill)

            db.commit()
            logger.info(f"Blog found with {len(result['skills'])} skills")
        else:
            logger.info("No personal blog found")

        return result

    def get_processing_status(
        self,
        submission_id: UUID,
        db: Session
    ) -> Dict[str, Any]:
        """Get current processing status for a submission"""
        stackoverflow = db.query(StackOverflowData).filter(
            StackOverflowData.submission_id == str(submission_id)
        ).first()

        web_mentions_count = db.query(SkillWebMention).filter(
            SkillWebMention.submission_id == str(submission_id)
        ).count()

        return {
            "submission_id": str(submission_id),
            "stackoverflow_processed": stackoverflow is not None,
            "stackoverflow_profile_found": stackoverflow.profile_url is not None if stackoverflow else False,
            "web_mentions_count": web_mentions_count,
            "processing_complete": stackoverflow is not None and web_mentions_count > 0
        }


# Singleton instance
_orchestrator = None

def get_web_orchestrator() -> WebSourceOrchestrator:
    """Get or create the web source orchestrator singleton"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WebSourceOrchestrator()
    return _orchestrator
