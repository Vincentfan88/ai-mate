# Sanitization Report: ai-companion-ng

**Date:** 2026-05-03
**Auditor:** opensource-sanitizer v1.0.0
**Verdict:** FAIL

## Summary

| Category | Status | Findings |
|----------|--------|----------|
| Secrets | FAIL | 2 critical findings |
| PII | FAIL | 1 critical finding |
| Internal References | PASS | 0 findings (build/ dir not tracked) |
| Dangerous Files | FAIL | 2 findings |
| Config Completeness | WARN | 1 missing variable |
| Git History | PASS | No leaked secrets in history |

## Critical Findings (Must Fix Before Release)

### [SECRETS] `workspace/companion/config.json:3` -- Hardcoded Feishu app secret

```json
"feishu_app_secret": "OjQC4MrR..."  (truncated)
```

Real Feishu app secret exposed. Must be removed before release.

### [SECRETS] `workspace/companion/config.json:5` -- Hardcoded API key

```json
"api_key": "sk-8da3..."  (truncated)
```

Real API key exposed. Must be removed before release.

### [SECRETS] `.env` -- Contains real Feishu App ID and Chat ID

File exists in working directory with real infrastructure identifiers:
- `FEISHU_APP_ID=cli_a961d7c7...`
- `FEISHU_CHAT_ID=oc_db6e9682b759...`

The actual secret values (`LLM_API_KEY`, `FEISHU_APP_SECRET`) are empty in `.env`, but the infrastructure IDs are real and should not be exposed.

### [PII] `workspace/companion/` -- Personal runtime data directory

Contains user-specific data that must not be released:
- `conversations/` -- conversation history
- `memory/` -- user memory data
- `facts/` -- extracted facts about user
- `preference.json` -- user preferences
- `relationship_state.json` -- relationship progression data
- `liveness.json` -- behavioral liveness data
- `token_stats.json` -- usage statistics
- `states/` -- HMM state history
- `anniversaries.json` -- personal anniversary tracking
- `habits_state.json` -- habit tracking state
- `trending_cache.json` -- cached trending data

### [DANGEROUS FILES] `.env` -- Exists in working directory

Not tracked in git (correctly excluded by `.gitignore`), but present in the working directory. Ensure it is never committed.

### [DANGEROUS FILES] `workspace/` -- Exists in working directory with real data

Not tracked in git (correctly excluded by `.gitignore`), but contains runtime data that would be included if someone packages the directory without excluding `workspace/`. The `.gitignore` already excludes it, so this is safe for git-based releases.

## Warnings (Review Before Release)

1. **[CONFIG]** `companion/webui/server.py:59` -- `FEISHU_ENABLED` environment variable used in code but NOT defined in `.env.example`
2. **[GIT]** 83 commits include upstream MiniMax repository history -- acceptable for a fork, but verify no sensitive upstream data was inherited
3. **[LOGS]** `logs/` directory contains 5.6MB error log (`webui.err.log`) -- not tracked in git but present in working directory
4. **[BUILD]** `companion/mobile/android/app/build/` contains Android build artifacts with `/Users/vincentfan/` paths -- not tracked in git but should be added to `.gitignore` if not already (verified: not tracked)

## .env.example Audit

**Variables in code but NOT in `.env.example`:**
- `FEISHU_ENABLED` (referenced in `companion/webui/server.py:59`)

**Variables in `.env.example` but NOT in code:** (none -- all covered)

**Complete env var mapping:**

| Variable | In Code | In .env.example |
|----------|---------|-----------------|
| `LLM_MODEL` | Yes | Yes |
| `LLM_API_BASE` | Yes | Yes |
| `LLM_API_KEY` | Yes | Yes |
| `CLOUD_PRICE_IN` | Yes | Yes |
| `CLOUD_PRICE_OUT` | Yes | Yes |
| `PRICE_CACHE_IN` | Yes | Yes |
| `LOCAL_MODEL_ENABLED` | Yes | Yes |
| `LOCAL_MODEL` | Yes | Yes |
| `LOCAL_API_BASE` | Yes | Yes |
| `FEISHU_APP_ID` | Yes | Yes |
| `FEISHU_APP_SECRET` | Yes | Yes |
| `FEISHU_CHAT_ID` | Yes | Yes |
| `FEISHU_ENABLED` | Yes | **MISSING** |
| `SERVER_HOST` | No (hardcoded) | Yes |
| `SERVER_PORT` | No (hardcoded) | Yes |

## .gitignore Audit

| Pattern | Covered |
|---------|---------|
| `.env` | Yes (`.env`, `.env.*`, `!.env.example`) |
| `node_modules/` | N/A (Python project) |
| `__pycache__/` | Yes |
| `*.pyc` | Yes (`*.py[cod]`) |
| `workspace/` | Yes |
| `logs/` | Partial (`*.log` covered, directory itself not) |
| `.DS_Store` | Yes |
| `.venv/` | Yes |
| `build/` | Yes |

## Git History Audit

- **Commit count:** 83 (includes upstream MiniMax mini_agent history)
- **Secrets in history:** None found -- no real API keys, tokens, or passwords were ever committed and then deleted
- **Personal emails in history:** Upstream contributor emails visible (e.g., `chmod777john@gmail.com`, `yufengzhang483@gmail.com`) -- these are from the original open-source project, not personal data
- **Deleted sensitive files:** No evidence of secrets being added then removed in history

## Non-Working-Directory Checks (Git-Tracked Only)

All checks on git-tracked files (excluding `workspace/`, `logs/`, `.venv/`, `build/`):
- No hardcoded secrets in source code -- PASS
- No JWT tokens -- PASS
- No private keys -- PASS
- No GitHub tokens -- PASS
- No Slack webhooks -- PASS
- No SendGrid/Mailgun keys -- PASS
- No SSH connection strings -- PASS
- `.env.example` exists -- PASS
- LICENSE exists (MIT) -- PASS
- README.md exists -- PASS

## Recommendation

**Fix the 2 critical findings before release:**

1. **Delete `workspace/companion/config.json`** -- Contains real API key (`sk-8da3...`) and Feishu app secret (`OjQC4MrR...`). The `workspace/` directory is already in `.gitignore`, so it is safe for git-based releases. However, if packaging as a tarball/zip, ensure `workspace/` is excluded.

2. **Delete `.env` from working directory** or move to a safe location -- Contains real Feishu App ID and Chat ID. Already excluded by `.gitignore`.

3. **Add `FEISHU_ENABLED` to `.env.example`** -- One-line fix:
   ```
   FEISHU_ENABLED=false
   ```

4. **Verify packaging excludes `workspace/`** -- The `.gitignore` protects git clones, but `MANIFEST.in` should also exclude `workspace/` for PyPI distribution.

Once these items are addressed, re-run this sanitizer to confirm a clean PASS.
