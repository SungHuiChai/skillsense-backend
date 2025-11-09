"""
Skill Normalization Service
Handles canonicalization of skill names to prevent duplicates
"""
from typing import Dict, List, Set, Optional
import re
import logging

logger = logging.getLogger(__name__)


class SkillNormalizationService:
    """
    Service for normalizing skill names to canonical forms.
    Handles variations like "Python" = "python" = "Python3"
    """

    # Canonical skill mappings - all variations map to the canonical name
    SKILL_MAPPINGS = {
        # Programming Languages
        "python": ["python", "python3", "python 3", "py", "python2"],
        "javascript": ["javascript", "js", "ecmascript", "es6", "es2015", "es2016", "es2017", "es2018", "es2019", "es2020", "es2021"],
        "typescript": ["typescript", "ts"],
        "java": ["java", "java se", "java ee"],
        "c++": ["c++", "cpp", "c plus plus", "cplusplus"],
        "c#": ["c#", "csharp", "c sharp"],
        "c": ["c", "c language"],
        "go": ["go", "golang"],
        "rust": ["rust", "rust lang"],
        "ruby": ["ruby", "ruby lang"],
        "php": ["php", "php7", "php8"],
        "swift": ["swift", "swift ui", "swiftui"],
        "kotlin": ["kotlin", "kotlin jvm"],
        "r": ["r", "r language", "r programming"],
        "scala": ["scala", "scala lang"],
        "perl": ["perl", "perl5"],
        "shell": ["shell", "bash", "zsh", "sh"],
        "powershell": ["powershell", "pwsh"],

        # Frontend Frameworks/Libraries
        "react": ["react", "reactjs", "react.js", "react js"],
        "vue": ["vue", "vuejs", "vue.js", "vue js"],
        "angular": ["angular", "angularjs", "angular.js", "angular js"],
        "svelte": ["svelte", "sveltejs"],
        "next.js": ["next.js", "nextjs", "next js", "next"],
        "nuxt": ["nuxt", "nuxtjs", "nuxt.js"],
        "gatsby": ["gatsby", "gatsbyjs"],

        # Backend Frameworks
        "django": ["django", "django rest framework", "drf"],
        "flask": ["flask", "flask framework"],
        "fastapi": ["fastapi", "fast api"],
        "express": ["express", "expressjs", "express.js"],
        "nest.js": ["nest.js", "nestjs", "nest"],
        "spring": ["spring", "spring boot", "spring framework"],
        "asp.net": ["asp.net", "aspnet", "asp .net core"],
        "rails": ["rails", "ruby on rails", "ror"],
        "laravel": ["laravel", "laravel framework"],

        # Databases
        "postgresql": ["postgresql", "postgres", "pg", "pgsql"],
        "mysql": ["mysql", "my sql"],
        "mongodb": ["mongodb", "mongo"],
        "redis": ["redis", "redis cache"],
        "elasticsearch": ["elasticsearch", "elastic search", "es"],
        "cassandra": ["cassandra", "apache cassandra"],
        "dynamodb": ["dynamodb", "dynamo db", "amazon dynamodb"],
        "sqlite": ["sqlite", "sqlite3"],
        "mariadb": ["mariadb", "maria db"],
        "oracle": ["oracle", "oracle db", "oracle database"],
        "mssql": ["mssql", "ms sql", "sql server", "microsoft sql server"],

        # Cloud Platforms
        "aws": ["aws", "amazon web services", "amazon aws"],
        "azure": ["azure", "microsoft azure", "azure cloud"],
        "gcp": ["gcp", "google cloud", "google cloud platform"],
        "heroku": ["heroku", "heroku cloud"],
        "digitalocean": ["digitalocean", "digital ocean"],

        # DevOps Tools
        "docker": ["docker", "docker container"],
        "kubernetes": ["kubernetes", "k8s", "k8"],
        "jenkins": ["jenkins", "jenkins ci"],
        "gitlab": ["gitlab", "gitlab ci", "gitlab ci/cd"],
        "github actions": ["github actions", "gh actions"],
        "terraform": ["terraform", "tf"],
        "ansible": ["ansible", "ansible automation"],
        "circleci": ["circleci", "circle ci"],

        # Data Science/ML
        "tensorflow": ["tensorflow", "tf", "tensor flow"],
        "pytorch": ["pytorch", "torch", "py torch"],
        "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "pandas": ["pandas", "pandas library"],
        "numpy": ["numpy", "numerical python"],
        "keras": ["keras", "keras api"],
        "jupyter": ["jupyter", "jupyter notebook", "jupyterlab"],

        # Testing
        "pytest": ["pytest", "py.test"],
        "jest": ["jest", "jest testing"],
        "mocha": ["mocha", "mochajs"],
        "selenium": ["selenium", "selenium webdriver"],
        "cypress": ["cypress", "cypress.io"],

        # Other Tools
        "git": ["git", "git scm"],
        "graphql": ["graphql", "graph ql"],
        "rest": ["rest", "rest api", "restful", "restful api"],
        "grpc": ["grpc", "grpc api"],
        "websocket": ["websocket", "websockets", "web socket"],
        "tailwind": ["tailwind", "tailwindcss", "tailwind css"],
        "bootstrap": ["bootstrap", "bootstrap css"],
        "sass": ["sass", "scss"],
        "webpack": ["webpack", "webpack js"],
        "vite": ["vite", "vitejs"],
    }

    # Build reverse mapping for fast lookup
    _REVERSE_MAPPING = {}

    def __init__(self):
        """Initialize the normalization service and build reverse mapping"""
        self._build_reverse_mapping()

    def _build_reverse_mapping(self):
        """Build reverse mapping from all variations to canonical names"""
        self._REVERSE_MAPPING = {}
        for canonical, variations in self.SKILL_MAPPINGS.items():
            for variation in variations:
                # Store normalized version (lowercase, trimmed)
                normalized_var = variation.lower().strip()
                self._REVERSE_MAPPING[normalized_var] = canonical

        logger.info(f"Built skill normalization mapping with {len(self._REVERSE_MAPPING)} variations")

    def normalize_skill(self, skill: str) -> str:
        """
        Normalize a skill name to its canonical form.

        Args:
            skill: Raw skill name

        Returns:
            Canonical skill name
        """
        if not skill:
            return skill

        # Clean the skill name
        cleaned = skill.lower().strip()

        # Remove common suffixes/prefixes
        cleaned = re.sub(r'\s+(framework|library|lang|language|programming)$', '', cleaned)
        cleaned = cleaned.strip()

        # Look up in reverse mapping
        canonical = self._REVERSE_MAPPING.get(cleaned)

        if canonical:
            return canonical

        # If not found in mapping, return cleaned version with proper casing
        # Try to preserve proper nouns (capitalize first letter of each word)
        return ' '.join(word.capitalize() for word in cleaned.split())

    def normalize_skills(self, skills: List[str]) -> List[str]:
        """
        Normalize a list of skills and remove duplicates.

        Args:
            skills: List of raw skill names

        Returns:
            List of unique canonical skill names
        """
        if not skills:
            return []

        normalized = set()
        for skill in skills:
            if skill:
                canonical = self.normalize_skill(skill)
                normalized.add(canonical)

        return sorted(list(normalized))

    def merge_skill_lists(
        self,
        *skill_lists: List[str]
    ) -> List[str]:
        """
        Merge multiple skill lists, normalizing and deduplicating.

        Args:
            skill_lists: Variable number of skill lists

        Returns:
            Merged and normalized skill list
        """
        all_skills = []
        for skill_list in skill_lists:
            if skill_list:
                all_skills.extend(skill_list)

        return self.normalize_skills(all_skills)

    def group_similar_skills(
        self,
        skills: List[str]
    ) -> Dict[str, List[str]]:
        """
        Group skills by their canonical form.

        Args:
            skills: List of raw skill names

        Returns:
            Dict mapping canonical names to list of original variations
        """
        groups = {}

        for skill in skills:
            if not skill:
                continue

            canonical = self.normalize_skill(skill)

            if canonical not in groups:
                groups[canonical] = []

            # Only add if it's a different variation
            if skill not in groups[canonical]:
                groups[canonical].append(skill)

        return groups

    def find_skill_synonyms(self, skill: str) -> List[str]:
        """
        Find all known synonyms for a skill.

        Args:
            skill: Skill name

        Returns:
            List of known synonyms
        """
        canonical = self.normalize_skill(skill)
        return self.SKILL_MAPPINGS.get(canonical, [canonical])

    def is_valid_skill(self, skill: str, min_length: int = 1) -> bool:
        """
        Validate if a string is a valid skill name.

        Args:
            skill: Skill name to validate
            min_length: Minimum length for skill name

        Returns:
            True if valid, False otherwise
        """
        if not skill or not isinstance(skill, str):
            return False

        cleaned = skill.strip()

        # Check minimum length
        if len(cleaned) < min_length:
            return False

        # Check if it's not just numbers
        if cleaned.isdigit():
            return False

        # Check if it's not just special characters
        if re.match(r'^[^a-zA-Z0-9]+$', cleaned):
            return False

        return True

    def extract_skill_category(self, skill: str) -> Optional[str]:
        """
        Determine the category of a skill.

        Args:
            skill: Skill name

        Returns:
            Category name or None
        """
        canonical = self.normalize_skill(skill)

        # Language category
        languages = {"python", "javascript", "typescript", "java", "c++", "c#", "c", "go",
                    "rust", "ruby", "php", "swift", "kotlin", "r", "scala", "perl", "shell"}
        if canonical in languages:
            return "programming_language"

        # Frontend category
        frontend = {"react", "vue", "angular", "svelte", "next.js", "nuxt", "gatsby",
                   "tailwind", "bootstrap", "sass", "webpack", "vite"}
        if canonical in frontend:
            return "frontend"

        # Backend category
        backend = {"django", "flask", "fastapi", "express", "nest.js", "spring",
                  "asp.net", "rails", "laravel"}
        if canonical in backend:
            return "backend"

        # Database category
        databases = {"postgresql", "mysql", "mongodb", "redis", "elasticsearch",
                    "cassandra", "dynamodb", "sqlite", "mariadb", "oracle", "mssql"}
        if canonical in databases:
            return "database"

        # Cloud category
        cloud = {"aws", "azure", "gcp", "heroku", "digitalocean"}
        if canonical in cloud:
            return "cloud"

        # DevOps category
        devops = {"docker", "kubernetes", "jenkins", "gitlab", "github actions",
                 "terraform", "ansible", "circleci"}
        if canonical in devops:
            return "devops"

        # ML/Data Science category
        ml = {"tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "keras", "jupyter"}
        if canonical in ml:
            return "machine_learning"

        # Testing category
        testing = {"pytest", "jest", "mocha", "selenium", "cypress"}
        if canonical in testing:
            return "testing"

        return "other"


# Singleton instance
_normalization_service = None

def get_normalization_service() -> SkillNormalizationService:
    """Get or create the skill normalization service singleton"""
    global _normalization_service
    if _normalization_service is None:
        _normalization_service = SkillNormalizationService()
    return _normalization_service
