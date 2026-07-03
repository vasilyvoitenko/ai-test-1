import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI


JUDGE_PROMPT_PATH = Path(__file__).parent / "prompts" / "judge.md"
REQUIRED_CASE_FIELDS = {
    "id",
    "title",
    "type",
    "preconditions",
    "steps",
    "expected_result",
}
VALID_TYPES = {"positive", "negative", "edge"}

EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b",
    re.IGNORECASE,
)
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?!\w)"
)


def deterministic_checks(output: dict) -> list[dict]:
    test_cases = output.get("test_cases") if isinstance(output, dict) else None

    checks = [
        _check_schema(output, test_cases),
        _check_min_count(test_cases),
        _check_positive_and_negative(test_cases),
        _check_no_empty_fields(test_cases),
        _check_no_pii(output),
    ]

    return checks


def judge(story_text: str, output: dict) -> dict:
    system_prompt = JUDGE_PROMPT_PATH.read_text(encoding="utf-8")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    user_content = json.dumps(
        {
            "story_text": story_text,
            "generated_test_cases": output,
        },
        indent=2,
        ensure_ascii=False,
    )

    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI judge response did not include JSON content.")

    return json.loads(content)


def run_gate(story_text: str, output: dict) -> dict:
    checks = deterministic_checks(output)
    failed_checks = [check for check in checks if not check["passed"]]

    if failed_checks:
        failed_names = ", ".join(check["name"] for check in failed_checks)
        return {
            "passed": False,
            "checks": checks,
            "judge": None,
            "summary": f"Deterministic checks failed: {failed_names}. Judge was not called.",
        }

    judge_result = judge(story_text, output)
    passed = (
        _score_at_least(judge_result.get("coverage"), 3)
        and judge_result.get("grounded") == "yes"
        and _score_at_least(judge_result.get("clarity"), 3)
    )

    if passed:
        summary = "Passed deterministic checks and judge thresholds."
    else:
        summary = "Failed judge thresholds: requires coverage >= 3, grounded == yes, and clarity >= 3."

    return {
        "passed": passed,
        "checks": checks,
        "judge": judge_result,
        "summary": summary,
    }


def _check_schema(output: Any, test_cases: Any) -> dict:
    issues = []

    if not isinstance(output, dict):
        issues.append("output is not a dict")

    if not isinstance(test_cases, list):
        issues.append("test_cases is not a list")
    elif len(test_cases) < 1:
        issues.append("test_cases must contain at least one case")
    else:
        for index, case in enumerate(test_cases):
            if not isinstance(case, dict):
                issues.append(f"test_cases[{index}] is not an object")
                continue

            missing = sorted(REQUIRED_CASE_FIELDS - set(case.keys()))
            if missing:
                issues.append(f"test_cases[{index}] missing fields: {', '.join(missing)}")

            case_type = case.get("type")
            if case_type is not None and case_type not in VALID_TYPES:
                issues.append(f"test_cases[{index}] has invalid type: {case_type}")

    return _result("schema", not issues, "; ".join(issues) if issues else "Schema is valid.")


def _check_min_count(test_cases: Any) -> dict:
    count = len(test_cases) if isinstance(test_cases, list) else 0
    passed = count >= 3
    detail = f"Found {count} test case(s); expected at least 3."
    return _result("min_count", passed, detail)


def _check_positive_and_negative(test_cases: Any) -> dict:
    if not isinstance(test_cases, list):
        return _result("positive_and_negative", False, "test_cases is not a list.")

    types = {case.get("type") for case in test_cases if isinstance(case, dict)}
    passed = "positive" in types and "negative" in types
    detail = f"Found types: {', '.join(sorted(str(item) for item in types)) or 'none'}."
    return _result("positive_and_negative", passed, detail)


def _check_no_empty_fields(test_cases: Any) -> dict:
    issues = []

    if not isinstance(test_cases, list):
        issues.append("test_cases is not a list")
    else:
        for index, case in enumerate(test_cases):
            if not isinstance(case, dict):
                issues.append(f"test_cases[{index}] is not an object")
                continue

            steps = case.get("steps")
            if not isinstance(steps, list) or not steps:
                issues.append(f"test_cases[{index}].steps is empty or not a list")
            else:
                for step_index, step in enumerate(steps):
                    if not isinstance(step, str) or not step.strip():
                        issues.append(f"test_cases[{index}].steps[{step_index}] is empty")

            expected_result = case.get("expected_result")
            if not isinstance(expected_result, str) or not expected_result.strip():
                issues.append(f"test_cases[{index}].expected_result is empty")

    return _result(
        "no_empty_fields",
        not issues,
        "; ".join(issues) if issues else "No empty steps or expected_result fields.",
    )


def _check_no_pii(output: Any) -> dict:
    findings = []

    for value in _iter_strings(output):
        for match in EMAIL_RE.finditer(value):
            domain = match.group(1).lower()
            if domain != "example.com":
                findings.append(f"email: {match.group(0)}")

        for match in CARD_RE.finditer(value):
            digits = re.sub(r"\D", "", match.group(0))
            if _looks_like_card_number(digits):
                findings.append("card number")

        for match in PHONE_RE.finditer(value):
            digits = re.sub(r"\D", "", match.group(0))
            if len(digits) >= 10:
                findings.append("phone number")

    passed = not findings
    detail = "No PII found." if passed else f"Found possible PII: {', '.join(sorted(set(findings)))}."
    return _result("no_pii", passed, detail)


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings = []
        for key, item in value.items():
            strings.extend(_iter_strings(key))
            strings.extend(_iter_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_iter_strings(item))
        return strings
    return []


def _looks_like_card_number(digits: str) -> bool:
    if not 13 <= len(digits) <= 19:
        return False

    total = 0
    reverse_digits = digits[::-1]
    for index, char in enumerate(reverse_digits):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return total % 10 == 0


def _score_at_least(value: Any, minimum: int) -> bool:
    return isinstance(value, int) and value >= minimum


def _result(name: str, passed: bool, detail: str) -> dict:
    return {
        "name": name,
        "passed": passed,
        "detail": detail,
    }
