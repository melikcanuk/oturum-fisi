---
name: oturum-fisi
description: Recall past Claude Code and Codex sessions from one-line "receipts" (date, folder, first request, files touched, keywords, transcript path) instead of re-reading whole transcripts. Use when the user asks "what did we do last time", "which session", "search my chat history", "summarise/map my sessions", or in Turkish "geçen sefer ne yapmıştık", "hangi oturumda", "oturumları özetle", "sohbet geçmişinde ara".
---

# Oturum fişi (session receipts)

Receipts live in `~/.oturum-fisi/` (override with `--out DIR` or the `OTURUM_FISI_DIR` env var). A hook (Claude Code: SessionEnd, Codex: Stop) keeps one line per session up to date; the first hook run indexes all past sessions.

1. Recall first: `python "${CLAUDE_SKILL_DIR}/fis.py" --recall "<words>"`. It prints matching receipts and a closing "Not:" line with the estimated tokens saved (appended to `kazanc.log`). Show that line to the user, verbatim, as a small note at the end of your answer.
2. Each line: `date | folder | id | first request | files | keywords | transcript path`. You can also Grep `INDEX.md` in the receipts folder.
3. Need detail? Grep the `.jsonl` transcript named on the line for specific terms. Never read the whole transcript.
4. Rebuild everything: `python "${CLAUDE_SKILL_DIR}/fis.py"`. Size check: add `--measure`.

The receipts contain first requests and file names. They stay on this machine; do not share `INDEX.md`.
