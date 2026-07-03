import json
import sys
from pathlib import Path

from agent import generate_test_cases
from evals import run_gate


DEFAULT_STORY_PATH = Path("golden/story_login.md")
OUTPUT_PATH = Path("last_output.json")


def main() -> None:
    story_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_STORY_PATH
    story_text = story_path.read_text(encoding="utf-8")

    result = generate_test_cases(story_text)
    pretty_result = json.dumps(result, indent=2, ensure_ascii=False)
    OUTPUT_PATH.write_text(pretty_result + "\n", encoding="utf-8")

    gate_result = run_gate(story_text, result)
    print_report(gate_result)
    sys.exit(0 if gate_result["passed"] else 1)


def print_report(gate_result: dict) -> None:
    print("Deterministic checks:")
    for check in gate_result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']} — {check['detail']}")

    print()
    print("Judge:")
    judge_result = gate_result["judge"]
    if judge_result is None:
        print("Not called.")
    else:
        print(f"coverage: {judge_result.get('coverage')} — {judge_result.get('coverage_reason')}")
        print(f"grounded: {judge_result.get('grounded')} — {judge_result.get('grounded_reason')}")
        print(f"clarity: {judge_result.get('clarity')} — {judge_result.get('clarity_reason')}")

    print()
    status = "PASS" if gate_result["passed"] else "FAIL"
    print(f"GATE: {status} — {gate_result['summary']}")


if __name__ == "__main__":
    main()
