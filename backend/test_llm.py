"""
Run from backend/:   python test_llm.py
Tests llm_service.generate_reply under different key setups (no server needed).
"""

import os
import subprocess
import sys

SNIPPET = """
import logging; logging.basicConfig(level=logging.INFO, format='  [log] %(message)s')
from app.services.llm_service import generate_reply
print('  reply:', generate_reply('What is 2 + 2? Answer in one short sentence.', ''))
"""

HIDE_OPENAI = {"OPENAI_API_KEY": ""}
HIDE_CLAUDE = {"ANTHROPIC_API_KEY": "", "CLAUDE_API_KEY": ""}

TESTS = [
    # (name, env overrides, should succeed?)
    ("Both keys (default provider)", {}, True),
    ("Only Claude key", HIDE_OPENAI, True),
    ("Only OpenAI key", HIDE_CLAUDE, True),
    ("Prefer Claude (LLM_PROVIDER=claude)", {"LLM_PROVIDER": "claude"}, True),
    ("Fallback: fake OpenAI key -> Claude", {"OPENAI_API_KEY": "sk-fake-key"}, True),
    ("No keys (should raise clear error)", {**HIDE_OPENAI, **HIDE_CLAUDE}, False),
]


def run(name, overrides, should_succeed):
    env = os.environ.copy()
    env.update(overrides)
    result = subprocess.run(
        [sys.executable, "-c", SNIPPET],
        env=env, capture_output=True, text=True, timeout=120,
    )
    succeeded = result.returncode == 0
    passed = succeeded == should_succeed
    print(f"\n{'PASS' if passed else 'FAIL'}  {name}")
    output = (result.stdout + result.stderr).strip().splitlines()
    # Show logs/reply, or just the last error line
    for line in (output if succeeded else output[-1:]):
        print(line if line.startswith("  ") else "  " + line)
    return passed


if __name__ == "__main__":
    results = [run(*t) for t in TESTS]
    print(f"\n{sum(results)}/{len(results)} tests passed")