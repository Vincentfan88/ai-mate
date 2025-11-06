"""
Skill Loader - Load Claude Skills

Supports loading skills from SKILL.md files and providing them to Agent
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class Skill:
    """Skill data structure"""

    name: str
    description: str
    content: str
    license: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None
    skill_path: Optional[Path] = None

    def to_prompt(self) -> str:
        """Convert skill to prompt format"""
        return f"""
# Skill: {self.name}

{self.description}

---

{self.content}
"""


class SkillLoader:
    """Skill loader"""

    def __init__(self, skills_dir: str = "./skills"):
        """
        Initialize Skill Loader

        Args:
            skills_dir: Skills directory path
        """
        self.skills_dir = Path(skills_dir)
        self.loaded_skills: Dict[str, Skill] = {}

    def load_skill(self, skill_path: Path) -> Optional[Skill]:
        """
        Load single skill from SKILL.md file

        Args:
            skill_path: SKILL.md file path

        Returns:
            Skill object, or None if loading fails
        """
        try:
            content = skill_path.read_text(encoding="utf-8")

            # Parse YAML frontmatter
            frontmatter_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)

            if not frontmatter_match:
                print(f"⚠️  {skill_path} missing YAML frontmatter")
                return None

            frontmatter_text = frontmatter_match.group(1)
            skill_content = frontmatter_match.group(2).strip()

            # Parse YAML
            try:
                frontmatter = yaml.safe_load(frontmatter_text)
            except yaml.YAMLError as e:
                print(f"❌ Failed to parse YAML frontmatter: {e}")
                return None

            # Required fields
            if "name" not in frontmatter or "description" not in frontmatter:
                print(f"⚠️  {skill_path} missing required fields (name or description)")
                return None

            # Get skill directory (parent of SKILL.md)
            skill_dir = skill_path.parent

            # Replace relative paths in content with absolute paths
            # This ensures scripts and resources can be found from any working directory
            processed_content = self._process_skill_paths(skill_content, skill_dir)

            # Create Skill object
            skill = Skill(
                name=frontmatter["name"],
                description=frontmatter["description"],
                content=processed_content,
                license=frontmatter.get("license"),
                allowed_tools=frontmatter.get("allowed-tools"),
                metadata=frontmatter.get("metadata"),
                skill_path=skill_path,
            )

            return skill

        except Exception as e:
            print(f"❌ Failed to load skill ({skill_path}): {e}")
            return None

    def _process_skill_paths(self, content: str, skill_dir: Path) -> str:
        """
        Process skill content to replace relative paths with absolute paths.

        Supports Progressive Disclosure Level 3+: converts relative file references
        to absolute paths so Agent can easily read nested resources.

        Args:
            content: Original skill content
            skill_dir: Skill directory path

        Returns:
            Processed content with absolute paths
        """
        import re

        # Pattern 1: Directory-based paths (scripts/, examples/, templates/, reference/)
        def replace_dir_path(match):
            prefix = match.group(1)  # e.g., "python " or "`"
            rel_path = match.group(2)  # e.g., "scripts/with_server.py"

            abs_path = skill_dir / rel_path
            if abs_path.exists():
                return f"{prefix}{abs_path}"
            return match.group(0)

        pattern_dirs = (
            r"(python\s+|`)((?:scripts|examples|templates|reference)/[^\s`\)]+)"
        )
        content = re.sub(pattern_dirs, replace_dir_path, content)

        # Pattern 2: Direct markdown/document references (forms.md, reference.md, etc.)
        # Matches phrases like "see reference.md" or "read forms.md"
        def replace_doc_path(match):
            prefix = match.group(1)  # e.g., "see ", "read "
            filename = match.group(2)  # e.g., "reference.md"
            suffix = match.group(3)  # e.g., punctuation

            abs_path = skill_dir / filename
            if abs_path.exists():
                # Add helpful instruction for Agent
                return f"{prefix}`{abs_path}` (use read_file to access){suffix}"
            return match.group(0)

        # Match patterns like: "see reference.md" or "read forms.md"
        pattern_docs = r"(see|read|refer to|check)\s+([a-zA-Z0-9_-]+\.(?:md|txt|json|yaml))([.,;\s])"
        content = re.sub(pattern_docs, replace_doc_path, content, flags=re.IGNORECASE)

        return content

    def discover_skills(self) -> List[Skill]:
        """
        Discover and load all skills in the skills directory

        Returns:
            List of Skills
        """
        skills = []

        if not self.skills_dir.exists():
            print(f"⚠️  Skills directory does not exist: {self.skills_dir}")
            return skills

        # Recursively find all SKILL.md files
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            skill = self.load_skill(skill_file)
            if skill:
                skills.append(skill)
                self.loaded_skills[skill.name] = skill

        return skills

    def get_skill(self, name: str) -> Optional[Skill]:
        """
        Get loaded skill

        Args:
            name: Skill name

        Returns:
            Skill object, or None if not found
        """
        return self.loaded_skills.get(name)

    def list_skills(self) -> List[str]:
        """
        List all loaded skill names

        Returns:
            List of skill names
        """
        return list(self.loaded_skills.keys())

    def get_skills_metadata_prompt(self) -> str:
        """
        Generate prompt containing ONLY metadata (name + description) for all skills.
        This implements Progressive Disclosure - Level 1.

        Returns:
            Metadata-only prompt string
        """
        if not self.loaded_skills:
            return ""

        prompt_parts = ["## Available Skills\n"]
        prompt_parts.append(
            "You have access to specialized skills. Each skill provides expert guidance for specific tasks.\n"
        )
        prompt_parts.append(
            "Load a skill's full content using the appropriate skill tool when needed.\n"
        )

        # List all skills with their descriptions
        for skill in self.loaded_skills.values():
            prompt_parts.append(f"- `{skill.name}`: {skill.description}")

        return "\n".join(prompt_parts)

    def get_skills_prompt(self, skill_names: Optional[List[str]] = None) -> str:
        """
        Generate prompt containing specified skills

        Args:
            skill_names: List of skill names to include, None means include all skills

        Returns:
            Combined prompt string
        """
        if skill_names is None:
            skills = list(self.loaded_skills.values())
        else:
            skills = [
                self.loaded_skills[name]
                for name in skill_names
                if name in self.loaded_skills
            ]

        if not skills:
            return ""

        prompt_parts = ["# Available Skills\n"]
        for skill in skills:
            prompt_parts.append(skill.to_prompt())

        return "\n".join(prompt_parts)


# Example usage
def load_example_skills() -> SkillLoader:
    """Load example skills (for testing)"""
    loader = SkillLoader("./skills/example-skills")
    skills = loader.discover_skills()
    print(f"✅ Discovered {len(skills)} skills:")
    for skill in skills:
        print(f"  - {skill.name}: {skill.description}")
    return loader


if __name__ == "__main__":
    # Test
    loader = load_example_skills()
