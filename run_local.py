import json
import sys
from pathlib import Path

from agent import generate_test_cases
from evals import run_gate
from story_evals import run_story_gate


DEFAULT_STORY_PATH = Path("golden/story_login.md")
OUTPUT_PATH = Path("last_output.json")


def main() -> None:
    story_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_STORY_PATH
    story_text = story_path.read_text(encoding="utf-8")

    story_gate_result = run_story_gate(story_text)
    if not story_gate_result["passed"]:
        print_report(story_gate_result, None)
        sys.exit(1)

    result = generate_test_cases(story_text)
    pretty_result = json.dumps(result, indent=2, ensure_ascii=False)
    OUTPUT_PATH.write_text(pretty_result + "\n", encoding="utf-8")

    test_gate_result = run_gate(story_text, result)
    print_report(story_gate_result, test_gate_result)
    sys.exit(0 if test_gate_result["passed"] else 1)


def print_report(story_gate_result: dict, test_gate_result: dict | None) -> None:
    print("Story deterministic checks:")
    for check in story_gate_result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']} — {check['detail']}")

    print()
    print("Story reviewer:")
    review_result = story_gate_result["review"]
    if review_result is None:
        print("Not called.")
    else:
        print(f"passed: {review_result.get('passed')}")
        print(f"testability: {review_result.get('testability')}")
        print(f"clarity: {review_result.get('clarity')}")
        print(f"completeness: {review_result.get('completeness')}")
        print(f"summary: {review_result.get('summary')}")

    print()
    story_status = "PASS" if story_gate_result["passed"] else "FAIL"
    print(f"STORY GATE: {story_status} — {story_gate_result['summary']}")

    if test_gate_result is None:
        print()
        print("Test case gate: Not run because story gate failed.")
        return

    print()
    print("Test case deterministic checks:")
    for check in test_gate_result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']} — {check['detail']}")

    print()
    print("Test case judge:")
    judge_result = test_gate_result["judge"]
    if judge_result is None:
        print("Not called.")
    else:
        print(f"coverage: {judge_result.get('coverage')} — {judge_result.get('coverage_reason')}")
        print(f"grounded: {judge_result.get('grounded')} — {judge_result.get('grounded_reason')}")
        print(f"clarity: {judge_result.get('clarity')} — {judge_result.get('clarity_reason')}")

    print()
    test_status = "PASS" if test_gate_result["passed"] else "FAIL"
    print(f"TEST CASE GATE: {test_status} — {test_gate_result['summary']}")


if __name__ == "__main__":
    main()
