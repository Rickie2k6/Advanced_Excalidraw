# LLM checks without starting FastAPI

From the project root, activate your backend Python environment, then install
its dependencies if needed:

```bash
python -m pip install -r backend/requirements.txt
```

Run the offline tests from the project root:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
```

These tests use fake keys and mocked responses, never call an API, never load
local keys, and never change `.env`. They cover both providers' four function
signatures, prompts, image payloads, JSON validation, provider/model caching,
provider logs, provider ordering and fallback, missing SDKs, and missing keys.

## Live generate_reply checks

These commands call the real APIs and use provider credits. In Bash, enter keys
at the hidden prompts (skip a prompt if you do not have that provider's key):

```bash
cd backend
read -r -s -p 'OpenAI API key: ' TEST_OPENAI_KEY
printf '\n'
read -r -s -p 'Anthropic API key: ' TEST_CLAUDE_KEY
printf '\n'
LLM_REPLY_TEST='import logging; logging.basicConfig(level=logging.INFO); from app.services.llm_service import generate_reply; print(generate_reply("Say hello in one sentence.", "The whiteboard is empty."))'
```

Each command sets unused keys to empty strings, which prevents the dotenv loader
from filling them from `backend/.env`. No files are edited.

Only OpenAI (requires a valid OpenAI key):

```bash
OPENAI_API_KEY="$TEST_OPENAI_KEY" ANTHROPIC_API_KEY= CLAUDE_API_KEY= python -c "$LLM_REPLY_TEST"
```

Only Claude (requires a valid Anthropic key):

```bash
OPENAI_API_KEY= ANTHROPIC_API_KEY="$TEST_CLAUDE_KEY" CLAUDE_API_KEY= python -c "$LLM_REPLY_TEST"
```

Both keys, OpenAI first:

```bash
OPENAI_API_KEY="$TEST_OPENAI_KEY" ANTHROPIC_API_KEY="$TEST_CLAUDE_KEY" CLAUDE_API_KEY= LLM_PROVIDER=openai python -c "$LLM_REPLY_TEST"
```

Both keys, Claude first:

```bash
OPENAI_API_KEY="$TEST_OPENAI_KEY" ANTHROPIC_API_KEY="$TEST_CLAUDE_KEY" CLAUDE_API_KEY= LLM_PROVIDER=claude python -c "$LLM_REPLY_TEST"
```

No keys (expected to exit with `ValueError` naming the keys and `backend/.env`):

```bash
OPENAI_API_KEY= ANTHROPIC_API_KEY= CLAUDE_API_KEY= python -c "$LLM_REPLY_TEST"
```

Successful calls print the reply and an INFO message naming the provider.
With both keys set, a provider failure prints a WARNING and tries the other
provider once. If both fail, the second exception propagates. The offline suite
forces this failure path without sending a request or requiring real keys.

To use the legacy Claude key name, set `ANTHROPIC_API_KEY=` and provide
`CLAUDE_API_KEY="$TEST_CLAUDE_KEY"` instead. `LLM_PROVIDER=anthropic` is an alias
for `claude`. With only one key, the preference is ignored.

Clean up the temporary shell variables when finished:

```bash
unset TEST_OPENAI_KEY TEST_CLAUDE_KEY LLM_REPLY_TEST
```
