import argparse
import json
import os
import sys
from pathlib import Path

from agent import generate_test_cases
from evals import run_gate
from story_evals import run_story_gate


DEFAULT_STORY_PATH = Path("golden/story_login.md")
OUTPUT_PATH = Path("last_output.json")
GATE_OUTPUT_PATH = Path("last_gate.json")
STORY_GATE_OUTPUT_PATH = Path("last_story_gate.json")


def main() -> None:
    args = parse_args()
    story_text = load_story_text(args.story_file)

    story_gate_result = run_story_gate(story_text)
    STORY_GATE_OUTPUT_PATH.write_text(
        json.dumps(story_gate_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not story_gate_result["passed"]:
        print(format_report(story_gate_result, None))
        sys.exit(1)

    generated = generate_test_cases(story_text)
    test_gate_result = run_gate(story_text, generated)

    OUTPUT_PATH.write_text(json.dumps(generated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    GATE_OUTPUT_PATH.write_text(json.dumps(test_gate_result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(format_report(story_gate_result, test_gate_result))
    sys.exit(0 if test_gate_result["passed"] else 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate test cases and run the quality gate.")
    parser.add_argument(
        "story_file",
        nargs="?",
        default=None,
        help="Path to a markdown user story. Defaults to STORY_TEXT env or golden/story_login.md.",
    )
    return parser.parse_args()


def load_story_text(story_file: str | None) -> str:
    story_text = os.environ.get("STORY_TEXT")
    if story_text:
        return story_text

    story_path = Path(story_file) if story_file else DEFAULT_STORY_PATH
    return story_path.read_text(encoding="utf-8")


def format_report(story_gate_result: dict, test_gate_result: dict | None) -> str:
    lines = ["Story deterministic checks:"]
    for check in story_gate_result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"[{status}] {check['name']} - {check['detail']}")

    lines.append("")
    lines.append("Story reviewer:")
    review_result = story_gate_result["review"]
    if review_result is None:
        lines.append("Not called.")
    else:
        lines.append(f"passed: {review_result.get('passed')}")
        lines.append(f"testability: {review_result.get('testability')}")
        lines.append(f"clarity: {review_result.get('clarity')}")
        lines.append(f"completeness: {review_result.get('completeness')}")
        lines.append(f"summary: {review_result.get('summary')}")

    lines.append("")
    story_status = "PASS" if story_gate_result["passed"] else "FAIL"
    lines.append(f"STORY GATE: {story_status} - {story_gate_result['summary']}")

    if test_gate_result is None:
        lines.append("")
        lines.append("Test case gate: Not run because story gate failed.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Test case deterministic checks:")
    for check in test_gate_result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"[{status}] {check['name']} - {check['detail']}")

    lines.append("")
    lines.append("Test case judge:")
    judge_result = test_gate_result["judge"]
    if judge_result is None:
        lines.append("Not called.")
    else:
        lines.append(f"coverage: {judge_result.get('coverage')} - {judge_result.get('coverage_reason')}")
        lines.append(f"grounded: {judge_result.get('grounded')} - {judge_result.get('grounded_reason')}")
        lines.append(f"clarity: {judge_result.get('clarity')} - {judge_result.get('clarity_reason')}")

    lines.append("")
    test_status = "PASS" if test_gate_result["passed"] else "FAIL"
    lines.append(f"TEST CASE GATE: {test_status} - {test_gate_result['summary']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
