"""oturum-fisi: Claude Code sohbetlerinden modelsiz, anlik dizin fisi uretir.
(Turns Claude Code transcripts into one-line "receipts", no model, in seconds.)
Kullanim / usage: python fis.py [--out DIR] [--olc|--measure] [--hatirla|--recall "words"] [--only PATH|-]
Her oturum icin tek satir: tarih | klasor | id | ilk istek | dosyalar | kelimeler | kaynak yol.
Yalnizca kisa alintilar ve ust veri yerelde saklanir; sohbetin tamami degil."""
import argparse, json, os, re, sys
from collections import Counter
from pathlib import Path

PROJ = Path.home() / ".claude" / "projects"
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

def scan(path):
    first_user = None; start = end = cwd = None
    files = Counter(); words = Counter(); conv_chars = 0
    usage = {}; turns = 0
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
                words=words, conv_chars=conv_chars, spent=sum(usage.values()), turns=turns)

def card(path, s):
    first = re.sub(r"\s+", " ", s["first"])[:90]
    fl = ", ".join(Path(f).name for f, _ in s["files"].most_common(5))
    kw = " ".join(w for w, _ in s["words"].most_common(6))
    return (f"{(s['start'] or '')[:10]} | {Path(s['cwd'] or '').name} | {path.stem[:8]} | "
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
        except ValueError:
            a.only = None
        if not a.only or not Path(a.only).is_file():
            return
        if not db.exists():  # first run from the hook: index every past session once
            a.only = None
    paths = [Path(a.only)] if a.only else sorted(PROJ.glob("*/*.jsonl"))
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
