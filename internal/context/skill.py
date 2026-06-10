from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Skill:
    """Skill 定义从 SKILL.md 中解析出的标准化技能结构。"""

    name: str
    description: str
    body: str


class SkillLoader:
    """从本地文件系统加载并解析符合规范的技能模板。"""

    def __init__(self, work_dir: str) -> None:
        self.work_dir = Path(work_dir)

    def load_all(self) -> str:
        skill_base_dir = self.work_dir / ".claw" / "skills"
        if not skill_base_dir.exists():
            return ""

        parts = [
            "\n### 可用专业技能 (Agent Skills)\n",
            "以下是你拥有的标准化外挂技能，请在符合 description 描述的场景下严格遵循其正文指令：\n\n",
        ]

        try:
            skill_files = sorted(skill_base_dir.rglob("SKILL.md"))
        except OSError:
            return ""

        for skill_file in skill_files:
            try:
                content = skill_file.read_text(encoding="utf-8")
            except OSError:
                continue

            skill = parse_skill_md(content)
            parts.append(f"#### 技能名称: {skill.name}\n")
            parts.append(f"**触发条件**: {skill.description}\n\n")
            parts.append("**执行指南**:\n")
            parts.append(skill.body)
            parts.append("\n\n---\n")

        result = "".join(parts)
        if len(result) < 100:
            return ""
        return result


def parse_skill_md(content: str) -> Skill:
    skill = Skill(
        name="Unknown Skill",
        description="No description provided.",
        body=content,
    )

    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return skill

    parts = normalized.split("---", 2)
    if len(parts) != 3:
        return skill

    frontmatter = parts[1]
    skill.body = parts[2].strip()

    for line in frontmatter.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            skill.name = line.removeprefix("name:").strip()
        elif line.startswith("description:"):
            skill.description = line.removeprefix("description:").strip()

    return skill

