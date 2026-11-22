import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.domain.ports import LLMRequest
from app.pipeline.datamark import MARKER

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_REQUIRED = ("injection", "document_type")
_GENERATION = ("chunk_output", "document_combine", "consolidation")
# Used only when a page reader is on. A catalog without it still loads.
_OPTIONAL_GENERATION = ("page_image",)
_QUESTION_TYPES = {"noul", "choice"}
CANARY = "CANARY-7F3A9C"


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    template: str
    placeholders: tuple[str, ...]
    question_type: str | None = None
    instructions: str | None = None
    criteria: dict[str, str] | None = None
    system: str | None = None

    def render(self, values: str | Mapping[str, str]) -> str:
        if isinstance(values, str):
            if len(self.placeholders) != 1:
                raise ValueError(f"System prompt {self.id} needs one placeholder")
            values = {self.placeholders[0]: values}
        missing = [name for name in self.placeholders if name not in values]
        if missing:
            raise ValueError(f"System prompt {self.id} is missing {', '.join(missing)}")
        rendered = self.template
        for name in sorted(self.placeholders, key=len, reverse=True):
            rendered = rendered.replace("{" + name + "}", values[name])
        return rendered

    def for_call(self, values: Mapping[str, str]) -> LLMRequest:
        if self.system is None:
            raise ValueError(f"System prompt {self.id} has no system text")
        return LLMRequest(
            prompt_id=self.id,
            prompt_version=self.version,
            system=self.system,
            user=self.render(values),
        )

    def api_question(self) -> dict[str, Any]:
        if self.question_type is None or self.instructions is None:
            raise ValueError(f"System prompt {self.id} has no question")
        body: dict[str, Any] = {"type": self.question_type, "instructions": self.instructions}
        if self.criteria is not None:
            body["criteria"] = self.criteria
        return body


@dataclass(frozen=True)
class SystemPromptCatalog:
    prompts: dict[str, Prompt]

    def get(self, prompt_id: str) -> Prompt:
        try:
            return self.prompts[prompt_id]
        except KeyError:
            raise ValueError(f"Unknown system prompt: {prompt_id}") from None


def load_system_prompts(path: Path) -> SystemPromptCatalog:
    if not path.is_file():
        raise ValueError(f"System prompt file not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or not loaded:
        raise ValueError(f"{path}: expected a list of system prompts")
    prompts: dict[str, Prompt] = {}
    for entry in loaded:
        prompt = _prompt(path, entry)
        if prompt.id in prompts:
            raise ValueError(f"{path}: duplicate system prompt id {prompt.id}")
        prompts[prompt.id] = prompt
    missing = [prompt_id for prompt_id in (*_REQUIRED, *_GENERATION) if prompt_id not in prompts]
    if missing:
        raise ValueError(f"{path}: missing system prompts: {', '.join(missing)}")
    for prompt_id in _REQUIRED:
        if prompts[prompt_id].question_type is None:
            raise ValueError(f"{path}: system prompt {prompt_id} has no question")
    for prompt_id in (*_GENERATION, *(item for item in _OPTIONAL_GENERATION if item in prompts)):
        system = prompts[prompt_id].system
        if system is None or CANARY not in system or MARKER not in system:
            raise ValueError(f"{path}: system prompt {prompt_id} needs system text")
    return SystemPromptCatalog(prompts)


def llm_call_key(model: str, prompt_id: str, prompt_version: int) -> str:
    key = f"{model}:{prompt_id}:v{prompt_version}"
    logging.getLogger("app.llm").info("llm call %s", key)
    return key


def _prompt(path: Path, entry: object) -> Prompt:
    if not isinstance(entry, dict):
        raise ValueError(f"{path}: each system prompt must be a mapping")  # noqa: TRY004
    prompt_id = _text(path, entry, "id")
    version = entry.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError(f"{path}: system prompt {prompt_id} needs a version of 1 or more")
    template = _text(path, entry, "template")
    placeholders = _placeholders(path, prompt_id, template, entry.get("placeholders"))
    question_type, instructions, criteria = _question(path, prompt_id, entry.get("question"))
    return Prompt(
        id=prompt_id,
        version=version,
        template=template,
        placeholders=placeholders,
        question_type=question_type,
        instructions=instructions,
        criteria=criteria,
        system=_system(path, prompt_id, entry.get("system")),
    )


def _system(path: Path, prompt_id: str, system: object) -> str | None:
    if system is None:
        return None
    if not isinstance(system, str) or not system.strip():
        raise ValueError(f"{path}: system prompt {prompt_id} needs system text")
    return system.strip()


def _text(path: Path, entry: dict[str, Any], field: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: system prompt {entry.get('id', '?')} needs a {field}")
    return value.strip()


def _placeholders(path: Path, prompt_id: str, template: str, listed: object) -> tuple[str, ...]:
    if not isinstance(listed, list) or not all(isinstance(item, str) and item for item in listed):
        raise ValueError(f"{path}: system prompt {prompt_id} needs a placeholders list")
    names = _PLACEHOLDER.findall(template)
    if set(names) != set(listed) or len(listed) != len(set(listed)):
        raise ValueError(
            f"{path}: system prompt {prompt_id} placeholders do not match its template"
        )
    return tuple(listed)


def _question(
    path: Path,
    prompt_id: str,
    question: object,
) -> tuple[str | None, str | None, dict[str, str] | None]:
    if question is None:
        return None, None, None
    if not isinstance(question, dict):
        raise ValueError(f"{path}: system prompt {prompt_id} question must be a mapping")  # noqa: TRY004
    question_type = question.get("type")
    if question_type not in _QUESTION_TYPES:
        raise ValueError(f"{path}: system prompt {prompt_id} question type must be noul or choice")
    instructions = question.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError(f"{path}: system prompt {prompt_id} question needs instructions")
    criteria = _criteria(path, prompt_id, question_type, question.get("criteria"))
    return question_type, instructions.strip(), criteria


def _criteria(
    path: Path,
    prompt_id: str,
    question_type: str,
    criteria: object,
) -> dict[str, str] | None:
    if criteria is None:
        if question_type == "choice":
            raise ValueError(f"{path}: system prompt {prompt_id} choice needs criteria")
        return None
    if not isinstance(criteria, dict) or not criteria:
        raise ValueError(f"{path}: system prompt {prompt_id} criteria must be a mapping")
    if any(not isinstance(key, str) for key in criteria):
        raise ValueError(f"{path}: system prompt {prompt_id} criteria keys must be strings")
    if any(not isinstance(value, str) or not value.strip() for value in criteria.values()):
        raise ValueError(f"{path}: system prompt {prompt_id} criteria need text")
    cleaned = {key: value.strip() for key, value in criteria.items()}
    if question_type == "noul" and set(cleaned) != {"true", "false"}:
        raise ValueError(f"{path}: system prompt {prompt_id} noul criteria must be true and false")
    return cleaned
