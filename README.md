# oturum-fisi

**Session receipts for Claude Code and OpenAI Codex.** Every session becomes one searchable line. A `SessionEnd` hook writes it the moment you close the session. No model, no cloud, no API key, standard-library Python.

*Oturum fişi* is Turkish for "session receipt".

```
2026-11-09 | my-app | 69cd5e36 | fix the login redirect loop | auth.ts, middleware.ts | login redirect cookie | ~/.claude/projects/.../69cd5e36-....jsonl
```

`date | folder | id | first request | files touched | keywords | transcript path`

## Why

Claude Code keeps every session as a `.jsonl` transcript. When you ask "what did we do last time?", the expensive way is to read those transcripts back into context. A receipt is enough to find the right session. Then Claude greps that one transcript for the detail it needs.

Measured on the author's machine (28 sessions):

| | size |
|---|---|
| transcripts on disk | 282 MB |
| conversation text inside them | 2.87 M characters (~718k tokens) |
| all 28 receipts | 7.5k characters (~1.9k tokens) |

The receipts are about 380× smaller than the conversation text. Indexing all 28 sessions took 3.3 s. Each later session takes about 0.3 s.

## Install (plugin, with the hook)

In Claude Code:

```
/plugin marketplace add melikcanuk/oturum-fisi
/plugin install oturum-fisi@oturum-fisi
```

That installs two things:

- **the hook**: on `SessionEnd` it adds the finished session to `~/.oturum-fisi/INDEX.md`. On its first run it indexes all your past sessions once.
- **the skill**: when you ask things like "which session did we fix the login in?", Claude runs a recall over the receipts instead of opening transcripts.

Requires Python 3.9+ on your `PATH` (`python3`, `python` or the Windows `py` launcher).

## Install in OpenAI Codex

Codex reads its own transcripts (`~/.codex/sessions`) too; one index covers both tools. Codex has no session-end event, so the hook runs on `Stop`. On Windows, run this in PowerShell (not inside Codex, whose sandbox cannot write to `~/.codex`):

```powershell
irm https://raw.githubusercontent.com/melikcanuk/oturum-fisi/main/codex/install.ps1 | iex
```

It finds or installs Python, copies the skill, backs up `config.toml`, adds the hook and builds the first index. Then restart Codex and approve the new hook.

Or paste this into Codex and let it do the steps (needs a session that may write outside the workspace):

```
Install the oturum-fisi skill and hook from https://github.com/melikcanuk/oturum-fisi by following codex/INSTALL.md in that repo. Ask me before installing Python or editing config.toml. Then run the checks in step 5 and tell me the result.
```

Manual steps: [codex/INSTALL.md](codex/INSTALL.md).

## Use it by hand

```bash
python skills/oturum-fisi/fis.py                    # (re)build every receipt
python skills/oturum-fisi/fis.py --recall "login"   # matching receipts + estimated tokens saved
python skills/oturum-fisi/fis.py --measure          # compression numbers for your own sessions
```

| Option | |
|---|---|
| `--out DIR` | receipts folder (default `~/.oturum-fisi`, or `$OTURUM_FISI_DIR`) |
| `--recall "words"` | print receipts containing all the words (alias `--hatirla`) |
| `--measure` | print sizes and ratios (alias `--olc`) |
| `--only PATH` | index one transcript; `--only -` reads the hook's JSON from stdin |

`--recall` prints a small receipt (`SAVED -832.422 token`) in the terminal and saves the same receipt as a thermal-paper image, `son-fis.svg`, in the receipts folder. The receipt also shows the ratio (e.g. `~903x less token` for that lookup) and what the avoided tokens would cost at API input prices, as two examples: Claude Fable 5.1 ($10 per million tokens) and Claude Opus 5.5 ($4). The saving applies to recalling past sessions, not to the rest of your usage. It also ends with a note estimating the tokens it avoided (characters ÷ 4, assuming the matched transcripts would otherwise have been read in full). It is an estimate, not a billing figure. Notes add up in `kazanc.log`.

## Privacy

Everything stays on your machine. The script makes no network calls. It stores only a 90-character excerpt of each session's first request, file names and keywords. Never the full conversation. Do not share your `INDEX.md`: it shows what you worked on.

## Related

[session-atlas](https://github.com/melikcanuk/Session-Atlas) writes longer per-session summaries with a free local model (Ollama). Use oturum-fisi for an instant index and session-atlas when you want readable summaries.

## License

MIT
