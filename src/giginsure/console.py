"""Tiny terminal formatting helpers (ANSI colours, fixed-width tables) shared by scripts and the server."""
import sys, time

try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:  # pragma: no cover
    pass

try:  # the Windows console may default to cp1252, which cannot print the rupee sign
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

C = dict(reset="\033[0m", bold="\033[1m", dim="\033[2m", red="\033[31m", green="\033[32m", yellow="\033[33m",
         blue="\033[34m", magenta="\033[35m", cyan="\033[36m", grey="\033[90m")


def c(text, *styles):
    return "".join(C[s] for s in styles) + str(text) + C["reset"]


def banner(title):
    line = "=" * 78
    print("\n" + c(line, "cyan") + "\n" + c(f"  {title}", "bold", "cyan") + "\n" + c(line, "cyan"), flush=True)


def stage(i, n, title):
    print("\n" + c(f"[{i}/{n}] ", "bold", "magenta") + c(title, "bold") + c(f"   ({time.strftime('%H:%M:%S')})", "grey"), flush=True)


def info(msg):
    print("   " + msg, flush=True)


def ok(msg):
    print("   " + c("✔ ", "green") + msg, flush=True)


def warn(msg):
    print("   " + c("⚠ ", "yellow") + msg, flush=True)


def fmt(v, nd=3):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.{nd}f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def table(rows, cols, headers=None, nd=3, highlight=None):
    """Print list-of-dicts as an aligned table. `highlight(row)` -> style name for the row, or None."""
    headers = headers or cols
    cells = [[fmt(r.get(k, ""), nd) for k in cols] for r in rows]
    w = [max(len(h), *(len(x[i]) for x in cells)) if cells else len(h) for i, h in enumerate(headers)]
    print("   " + c("  ".join(h.ljust(w[i]) for i, h in enumerate(headers)), "bold"))
    print("   " + c("  ".join("-" * w[i] for i in range(len(headers))), "grey"))
    for r, x in zip(rows, cells):
        line = "  ".join(v.rjust(w[i]) if i else v.ljust(w[i]) for i, v in enumerate(x))
        st = highlight(r) if highlight else None
        print("   " + (c(line, st) if st else line))
    sys.stdout.flush()
