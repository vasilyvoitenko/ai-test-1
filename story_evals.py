import json
import os
import re
from pathlib import Path

from openai import OpenAI


REVIEW_STORY_PROMPT_PATH = Path(__file__).parent / "prompts" / "review_story.md"
VAGUE_PHRASES = [
    "something goes wrong",
    "appropriate error",
    "behaves correctly",
    "manage my work",
    "works as expected",
    "etc.",
    "and so on",
]


def deterministic_story_checks(story_text: str) -> list[dict]:
    acceptance_criteria = _extract_acceptance_criteria(story_text)

    return [
        _check_story_title(story_text),
        _check_user_story_format(story_text),
        _check_acceptance_criteria_present(acceptance_criteria),
        _check_acceptance_criteria_count(acceptance_criteria),
        _check_acceptance_criteria_observable(acceptance_criteria),
        _check_no_vague_phrases(story_text),
    ]


def review_story(story_text: str) -> dict:
    system_prompt = REVIEW_STORY_PROMPT_PATH.read_text(encoding="utf-8")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": story_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI story reviewer response did not include JSON content.")

    return json.loads(content)


def run_story_gate(story_text: str) -> dict:
    checks = deterministic_story_checks(story_text)
    failed_checks = [check for check in checks if not check["passed"]]

    if failed_checks:
        failed_names = ", ".join(check["name"] for check in failed_checks)
        return {
            "passed": False,
            "checks": checks,
            "review": None,
            "summary": f"Deterministic story checks failed: {failed_names}. Story reviewer was not called.",
        }

    review_result = review_story(story_text)
    passed = (
        review_result.get("passed") is True
        and _score_at_least(review_result.get("testability"), 3)
        and _score_at_least(review_result.get("clarity"), 3)
        and _score_at_least(review_result.get("completeness"), 3)
    )

    if passed:
        summary = "Story passed deterministic checks and reviewer thresholds."
    else:
        summary = (
            "Story failed reviewer thresholds: requires passed == true, "
            "testability >= 3, clarity >= 3, and completeness >= 3."
        )

    return {
        "passed": passed,
        "checks": checks,
        "review": review_result,
        "summary": summary,
    }


def _extract_acceptance_criteria(story_text: str) -> list[str]:
    lines = story_text.splitlines()
    criteria = []
    in_section = False

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if lower.startswith("#") and "acceptance criteria" in lower:
            in_section = True
            continue

        if in_section and stripped.startswith("#"):
            break

        if in_section and stripped.startswith(("-", "*")):
            criteria.append(stripped[1:].strip())

    return criteria


def _check_story_title(story_text: str) -> dict:
    has_title = any(line.strip().startswith("#") and len(line.strip("# ").strip()) > 0 for line in story_text.splitlines())
    return _result("story_title", has_title, "Story has a title." if has_title else "Story title is missing.")


def _check_user_story_format(story_text: str) -> dict:
    normalized = " ".join(story_text.lower().split())
    has_format = bool(re.search(r"\bas\s+a[n]?\b", normalized)) and "i want" in normalized and "so that" in normalized
    detail = (
        "Story includes role, goal, and value."
        if has_format
        else "Story should include role, goal, and value, for example: As a..., I want..., so that..."
    )
    return _result("user_story_format", has_format, detail)


def _check_acceptance_criteria_present(acceptance_criteria: list[str]) -> dict:
    passed = len(acceptance_criteria) > 0
    detail = (
        f"Found {len(acceptance_criteria)} acceptance criteria."
        if passed
        else "Acceptance criteria section is missing or empty."
    )
    return _result("acceptance_criteria_present", passed, detail)


def _check_acceptance_criteria_count(acceptance_criteria: list[str]) -> dict:
    count = len(acceptance_criteria)
    passed = count >= 2
    return _result("acceptance_criteria_count", passed, f"Found {count} acceptance criteria; expected at least 2.")


def _check_acceptance_criteria_observable(acceptance_criteria: list[str]) -> dict:
    issues = []

    for index, criterion in enumerate(acceptance_criteria):
        normalized = criterion.lower()
        if "then" not in normalized:
            issues.append(f"AC {index + 1} has no observable 'then' result")
        elif not normalized.split("then", 1)[1].strip().rstrip("."):
            issues.append(f"AC {index + 1} has an empty 'then' result")

    return _result(
        "acceptance_criteria_observable",
        not issues,
        "; ".join(issues) if issues else "Acceptance criteria include observable expected results.",
    )


def _check_no_vague_phrases(story_text: str) -> dict:
    normalized = story_text.lower()
    found = [phrase for phrase in VAGUE_PHRASES if phrase in normalized]
    passed = not found
    detail = "No blocked vague phrases found." if passed else f"Found vague phrase(s): {', '.join(found)}."
    return _result("no_vague_phrases", passed, detail)


def _score_at_least(value: object, minimum: int) -> bool:
    return isinstance(value, int) and value >= minimum


def _result(name: str, passed: bool, detail: str) -> dict:
    return {
        "name": name,
        "passed": passed,
        "detail": detail,
    }
