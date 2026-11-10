# Install oturum-fisi in OpenAI Codex

Written for a Codex agent to follow. Ask the user before installing software (step 1) and before editing `config.toml` (step 4). Do not touch anything else.

Paths below use `~` for the user's home folder (on Windows `C:\Users\<name>`).

## 1. Python 3.9+

Find a working interpreter and note its absolute path as `PY`:

```
python  -c "import sys; print(sys.executable)"
py -3   -c "import sys; print(sys.executable)"     # Windows launcher
python3 -c "import sys; print(sys.executable)"
```

On Windows, `python` may be the Microsoft Store stub (it prints "Python was not found" or opens the Store). If no interpreter works, ask the user, then install one:
- Windows: `winget install -e --id Python.Python.3.12`, then open a new shell and read `PY` again (`py -3 -c ...`).
- macOS: `brew install python`. Linux: the distro package `python3`.

## 2. Copy the skill

Download this repository (`git clone https://github.com/melikcanuk/oturum-fisi` into a temp folder, or the GitHub zip) and copy the folder `skills/oturum-fisi` to:

```
~/.agents/skills/oturum-fisi/        (contains SKILL.md and fis.py)
```

## 3. Make SKILL.md point at the real files

Codex does not expand `${CLAUDE_SKILL_DIR}`. In the copied `~/.agents/skills/oturum-fisi/SKILL.md`, replace every `python "${CLAUDE_SKILL_DIR}/fis.py"` with the absolute command, e.g.
`"C:\Users\<name>\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\<name>\.agents\skills\oturum-fisi\fis.py"`.

## 4. Add the hook

Codex has no session-end event, so the hook runs on `Stop` (after every reply). It re-reads only the current session and takes well under a second; its first run indexes all past Claude Code and Codex sessions once (about 10 s for ~100 sessions).

Back up `~/.codex/config.toml`, then append (fill in `PY` and the home path; these are double-quoted TOML strings, so write every Windows backslash as `\\`):

```toml
[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = "'PY' '/home/<name>/.agents/skills/oturum-fisi/fis.py' --only -"
command_windows = "& 'PY' 'C:\\Users\\<name>\\.agents\\skills\\oturum-fisi\\fis.py' --only -"
timeout = 60
```

If the file already has `[[hooks.Stop]]` entries, add this as one more `[[hooks.Stop]]` block; do not merge it into an existing one.

## 5. Trust the hook, then check

New hooks start as untrusted. Restart Codex and approve the `oturum-fisi` Stop hook when Codex asks for a review (or trust it from the hooks list).

Check:
1. Run once by hand: `PY ~/.agents/skills/oturum-fisi/fis.py` → `~/.oturum-fisi/INDEX.md` exists and has one line per session.
2. Send Codex any message, wait for the reply, and confirm `~/.oturum-fisi/fis.json` was modified just now.
3. Ask Codex "what did we do last time?": it should run `fis.py --recall "<words>"` and end its answer with the "Not:" line.

## Uninstall

Delete the `[[hooks.Stop]]` block from `config.toml`, the folder `~/.agents/skills/oturum-fisi`, and optionally `~/.oturum-fisi` (the receipts).
