"""oturum-fisi: Claude Code sohbetlerinden modelsiz, anlik dizin fisi uretir.
(Turns Claude Code transcripts into one-line "receipts", no model, in seconds.)
Kullanim / usage: python fis.py [--out DIR] [--olc|--measure] [--hatirla|--recall "words"] [--only PATH|-]
Her oturum icin tek satir: tarih | klasor | id | ilk istek | dosyalar | kelimeler | kaynak yol.
Yalnizca kisa alintilar ve ust veri yerelde saklanir; sohbetin tamami degil."""
import argparse, json, os, re, sys
from collections import Counter
from pathlib import Path

PROJ = Path.home() / ".claude" / "projects"
CODEX = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
STOP = set("""ve ile bir bu da de mi ne için icin gibi daha çok cok ama olarak şu su o ki ya the and to of a in is for on it that this with you be are not have i me my your we can do""".split())
FILE_KEYS = ("file_path", "path", "notebook_path")

def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
    return "\n".join(out)

def all_paths():
    return sorted(PROJ.glob("*/*.jsonl")) + sorted(CODEX.glob("**/rollout-*.jsonl"))

def codex_request(t):
    # Codex puts attached-file lists before the request: keep only the request
    m = re.search(r"^## My request[^\n]*:\s*\n", t, re.M)
    return t[m.end():] if m else t

def scan(path):
    first_user = None; start = end = cwd = None
    files = Counter(); words = Counter(); conv_chars = 0
    usage = {}; turns = 0; codex_spent = 0
    def user_text(t):
        nonlocal first_user, turns, conv_chars
        t = t.strip()
        if not t or t.startswith(("<", "# AGENTS.md")):
            return
        turns += 1; conv_chars += len(t)
        first_user = first_user or t
        words.update(w for w in re.findall(r"[a-zçğıöşü0-9_-]{4,}", t.lower()) if w not in STOP)
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        ts = r.get("timestamp")
        if ts:
            start = start or ts; end = ts
        cwd = cwd or r.get("cwd")
        p = r.get("payload")
        if isinstance(p, dict):  # Codex rollout record
            if r.get("type") == "session_meta":
                cwd = cwd or p.get("cwd")
            elif r.get("type") == "event_msg":
                if p.get("type") == "user_message":  # older Codex versions
                    user_text(codex_request(str(p.get("message") or "")))
                elif p.get("type") == "token_count":
                    tot = ((p.get("info") or {}).get("total_token_usage") or {}).get("total_tokens")
                    codex_spent = max(codex_spent, tot or 0)
                it = p.get("item") if p.get("type") == "item_completed" else None
                if isinstance(it, dict):
                    k = it.get("type")
                    if k == "UserMessage":
                        user_text(codex_request("\n".join(b.get("text", "") for b in it.get("content") or []
                                                           if isinstance(b, dict) and b.get("type") == "text")))
                    elif k == "AgentMessage":
                        conv_chars += sum(len(b.get("text", "")) for b in it.get("content") or [] if isinstance(b, dict))
                    elif k == "FileChange":
                        conv_chars += len(json.dumps(it, ensure_ascii=False))
                        for f in (it.get("changes") or {}):
                            if len(f) < 200:
                                files[f] += 1
                    elif k in ("CommandExecution", "McpToolCall"):  # the call, not its (huge) output
                        conv_chars += len(json.dumps({x: it.get(x) for x in ("command", "server", "tool", "arguments")},
                                                     ensure_ascii=False))
            continue
        m = r.get("message")
        if not isinstance(m, dict) or r.get("isSidechain"):
            continue
        c = m.get("content")
        if r.get("type") == "user":
            t = text_of(c).strip()
            if t and not t.startswith("<") and not r.get("isMeta"):
                turns += 1; conv_chars += len(t)
                first_user = first_user or t
                words.update(w for w in re.findall(r"[a-zçğıöşü0-9_-]{4,}", t.lower()) if w not in STOP)
        elif r.get("type") == "assistant":
            conv_chars += len(text_of(c))
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    conv_chars += len(json.dumps(inp, ensure_ascii=False))
                    for k in FILE_KEYS:
                        v = inp.get(k)
                        if isinstance(v, str) and len(v) < 200:
                            files[v.replace("\\\\", "\\")] += 1
            u = m.get("usage")
            if u and m.get("id"):
                usage[m["id"]] = sum(u.get(k, 0) or 0 for k in
                    ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return dict(start=start, end=end, cwd=cwd, first=first_user or "", files=files,
                words=words, conv_chars=conv_chars, spent=sum(usage.values()) + codex_spent, turns=turns)

def card(path, s):
    first = re.sub(r"\s+", " ", s["first"])[:90]
    fl = ", ".join(Path(f).name for f, _ in s["files"].most_common(5))
    kw = " ".join(w for w, _ in s["words"].most_common(6))
    sid = "codex:" + path.stem[-8:] if path.stem.startswith("rollout-") else path.stem[:8]
    return (f"{(s['start'] or '')[:10]} | {Path(s['cwd'] or '').name} | {sid} | "
            f"{first} | {fl} | {kw} | {path}")

def hatirla(db, out, sorgu):
    from datetime import datetime
    cards = json.loads(db.read_text(encoding="utf-8")) if db.exists() else {}
    terms = sorgu.lower().split()
    hits = [v for v in cards.values() if all(t in v["card"].lower() for t in terms)]
    for v in sorted(hits, key=lambda v: v["start"]):
        print(v["card"])
    okunan = sum(len(v["card"]) for v in hits) // 4
    tam = sum(v.get("conv", 0) for v in hits) // 4
    kazanc = max(tam - okunan, 0)
    log = out / "kazanc.log"
    toplam = kazanc
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            m = re.search(r"kazanc=(\d+)", line)
            toplam += int(m[1]) if m else 0
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} sorgu={sorgu!r} eslesen={len(hits)} okunan={okunan} tam={tam} kazanc={kazanc}\n")
    print(f"\nNot: {len(hits)} fis okundu (~{okunan} token). Tam sohbetleri okumak ~{tam} token tutardi; "
          f"~{kazanc} token olasi israf onlendi. Toplam birikmis olasi kazanc: ~{toplam} token. (tahmin: karakter/4, tum sohbetin okunacagi varsayimiyla; fatura olcumu degil)")
    usd = float(os.environ.get("OTURUM_FISI_USD_PER_MTOK", "4"))  # Opus 5.5 API input price, Oct 2026
    rows = dict(zaman=f"{datetime.now():%Y-%m-%d %H:%M}", sorgu=sorgu, eslesen=len(hits),
                okunan=okunan, tam=tam, kazanc=kazanc, toplam=toplam, usd=usd,
                oran=(tam // okunan) if okunan else 0)
    print("\n" + fis_metin(rows))
    svg = out / "son-fis.svg"
    svg.write_text(fis_svg(rows), encoding="utf-8")
    print(f"Fis gorseli: {svg}")

def tr(n):  # 125504 -> 125.504
    return f"{n:,}".replace(",", ".")

def para(tok, usd):  # tokens -> "0,50 $" at usd per million tokens
    v = tok * usd / 1e6
    return (f"{v:,.2f}" if v >= 0.01 else f"{v:.4f}").replace(",", " ").replace(".", ",").replace(" ", ".") + " $"

def fis_metin(r, w=34):
    """Terminal receipt drawn with plain characters."""
    def line(a, b=""):
        return "| " + a + " " * max(1 if b else 0, w - 4 - len(a) - len(b)) + b + " |"
    sorgu = r["sorgu"] if len(r["sorgu"]) <= w - 14 else r["sorgu"][:w - 17] + "..."
    rows = [" " + "_" * (w - 2), line("oturum fisi".center(w - 4)), line(r["zaman"], f'"{sorgu}"'),
            line("-" * (w - 4)),
            line("okunan fis", str(r["eslesen"])), line("okunan", f"~{tr(r['okunan'])} tok"),
            line("tam sohbet", f"~{tr(r['tam'])} tok"), line("=" * (w - 4)),
            line("SAVED", f"-{tr(r['kazanc'])} token"), line("oran", f"~{r['oran']}x az token"),
            line("API fiyati", f"{para(r['tam'], r['usd'])} -> {para(r['okunan'], r['usd'])}"),
            line("toplam", f"-{tr(r['toplam'])} token"),
            line("-" * (w - 4)), line(f"tahmin: karakter/4, {r['usd']:g}$/MTok"), " " + "/\\" * ((w - 2) // 2)]
    return "\n".join(rows)

def fis_svg(r):
    """Thermal-paper receipt as a standalone SVG (no dependencies)."""
    from html import escape
    W, pad = 520, 44
    ink, paper, mark = "#26231f", "#f3f0e8", "#f2ea3b"
    body = [("c", "oturum fişi", 40, 600), ("gap", 18),
            ("lr", r["zaman"], "", 20, 400), ("l", f'“{r["sorgu"]}”', 24, 600), ("rule",),
            ("lr", "okunan fiş", str(r["eslesen"]), 22, 400),
            ("lr", "okunan", f"~{tr(r['okunan'])} token", 22, 400),
            ("lr", "tam sohbet", f"~{tr(r['tam'])} token", 22, 400), ("rule",), ("gap", 8),
            ("big", f"−{tr(r['kazanc'])}", 64), ("c", "token saved", 26, 600), ("gap", 14),
            ("lr", "oran", f"~{r['oran']}× daha az token", 22, 400),
            ("lr", "API fiyatıyla", f"{para(r['tam'], r['usd'])} → {para(r['okunan'], r['usd'])}", 22, 400),
            ("lr", "toplam", f"−{tr(r['toplam'])} token", 22, 600), ("rule",),
            ("l", "tahmin: karakter/4, tüm sohbet okunsaydı", 16, 400),
            ("l", f"fiyat: {r['usd']:g} $ / 1M girdi token (Opus 5.5 API)", 16, 400)]
    y, el = 70, []
    for b in body:
        k = b[0]
        if k == "gap":
            y += b[1]; continue
        if k == "rule":
            y += 22
            el.append(f'<line x1="{pad}" y1="{y}" x2="{W - pad}" y2="{y}" stroke="{ink}" stroke-width="2" stroke-dasharray="7 6"/>')
            y += 30; continue
        if k == "big":
            y += b[2]
            tw = len(b[1]) * b[2] * 0.6
            el.append(f'<path d="M{W/2 - tw/2 - 16} {y - b[2]*0.78} L{W/2 + tw/2 + 14} {y - b[2]*0.84} L{W/2 + tw/2 + 18} {y + 12} '
                      f'L{W/2 - tw/2 - 12} {y + 16} Z" fill="{mark}" style="mix-blend-mode:multiply"/>')
            el.append(f'<text x="{W/2}" y="{y}" font-size="{b[2]}" font-weight="600" text-anchor="middle">{escape(b[1])}</text>')
            y += 18; continue
        size = b[3] if k == "lr" else b[2]
        weight = b[4] if k == "lr" else b[3]
        y += size + 10
        if k == "c":
            el.append(f'<text x="{W/2}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="middle">{escape(b[1])}</text>')
        elif k == "l":
            el.append(f'<text x="{pad}" y="{y}" font-size="{size}" font-weight="{weight}">{escape(b[1])}</text>')
        else:
            el.append(f'<text x="{pad}" y="{y}" font-size="{size}" font-weight="{weight}">{escape(b[1])}</text>'
                      f'<text x="{W - pad}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="end">{escape(b[2])}</text>')
    H = y + 70
    teeth = " ".join(f"L{x} {H - (12 if i % 2 else 0)}" for i, x in enumerate(range(W, -1, -20)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<defs><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9 .25" numOctaves="2" seed="4"/>'
            f'<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .06 0"/><feComposite in2="SourceGraphic" operator="in"/></filter>'
            f'<linearGradient id="curl" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".10"/>'
            f'<stop offset=".06" stop-color="#000" stop-opacity="0"/><stop offset=".94" stop-color="#000" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="#000" stop-opacity=".12"/></linearGradient></defs>'
            f'<path d="M0 0 L{W} 0 {teeth} Z" fill="{paper}"/>'
            f'<path d="M0 0 L{W} 0 {teeth} Z" fill="url(#curl)"/><path d="M0 0 L{W} 0 {teeth} Z" filter="url(#grain)"/>'
            f'<g fill="{ink}" font-family="\'IBM Plex Mono\', Consolas, \'Courier New\', monospace">{"".join(el)}</g></svg>')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.environ.get("OTURUM_FISI_DIR", str(Path.home() / ".oturum-fisi")))
    ap.add_argument("--olc", "--measure", dest="olc", action="store_true", help="sikistirma ve token olcumu yaz")
    ap.add_argument("--only", help="tek bir oturum jsonl yolu (hook icin)")
    ap.add_argument("--hatirla", "--recall", dest="hatirla", help="fislerde ara, eslesenleri ve token kazanc notunu yaz")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    db = out / "fis.json"
    if a.hatirla:
        return hatirla(db, out, a.hatirla)
    cards = json.loads(db.read_text(encoding="utf-8")) if db.exists() else {}
    if a.only == "-":  # Claude Code hook: JSON on stdin with transcript_path
        try:
            a.only = json.load(sys.stdin).get("transcript_path")
        except (ValueError, AttributeError, OSError):
            a.only = None
        if not a.only or not Path(a.only).is_file():  # no usable stdin: take the newest transcript
            newest = max(all_paths(), key=lambda q: q.stat().st_mtime, default=None)
            a.only = str(newest) if newest else None
        if not a.only:
            return
        if not db.exists():  # first run from the hook: index every past session once
            a.only = None
    paths = [Path(a.only)] if a.only else all_paths()
    rows = []
    for p in paths:
        s = scan(p)
        if not s["turns"]:
            continue
        c = card(p, s)
        cards[p.stem] = {"card": c, "start": s["start"] or "", "conv": s["conv_chars"]}
        rows.append((p, s, c))
    db.write_text(json.dumps(cards, ensure_ascii=False, indent=0), encoding="utf-8")
    lines = sorted((v["start"], v["card"]) for v in cards.values())
    (out / "INDEX.md").write_text("# Oturum fisleri (tarih | klasor | id | ilk istek | dosyalar | kelimeler | kaynak)\n"
        + "\n".join(c for _, c in lines) + "\n", encoding="utf-8")
    if a.olc and rows:
        raw = sum(p.stat().st_size for p, _, _ in rows)
        conv = sum(s["conv_chars"] for _, s, _ in rows)
        spent = sum(s["spent"] for _, s, _ in rows)
        fis = sum(len(c) for _, _, c in rows)
        print(f"oturum={len(rows)}")
        print(f"ham_dosya_bayt={raw}")
        print(f"sohbet_metni_karakter={conv}  (~{conv//4} token tahmini)")
        print(f"fis_karakter={fis}  (~{fis//4} token tahmini)")
        print(f"oran_ham/fis={raw/fis:.0f}x  oran_sohbet/fis={conv/fis:.0f}x")
        print(f"oturumlarda_harcanan_gercek_token={spent}")
        for p, s, c in sorted(rows, key=lambda x: -x[1]["conv_chars"])[:5]:
            print(f"  {p.stem[:8]} sohbet={s['conv_chars']} fis={len(c)} oran={s['conv_chars']/len(c):.0f}x harcanan={s['spent']}")

if __name__ == "__main__":
    main()
