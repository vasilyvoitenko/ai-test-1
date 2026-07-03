import json
import os
from pathlib import Path

from openai import OpenAI


PROMPT_PATH = Path(__file__).parent / "prompts" / "generate.md"


def generate_test_cases(story_text: str) -> dict:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": story_text},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI response did not include JSON content.")

    return json.loads(content)
