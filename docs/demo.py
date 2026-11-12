"""Terminal demo for the README GIF: types each line, then runs it for real.

    pip install rich "catalejo[pdf]"
    python docs/demo.py

Everything shown is live data from the CNMV.
"""

import random
import time

from rich.console import Console

console = Console()
ns: dict[str, object] = {}

STEPS = [
    ("import catalejo", 0.4),
    ("from rich import print", 0.6),
    (
        'for f in catalejo.filings(days=3, kind="IP"): '
        'print(f"{f.registered_at:%d %b %H:%M}  {f.issuer[:26]:<26}  {f.title[:52]}")',
        2.5,
    ),
    ("from datetime import date", 0.3),
    ('bbva = catalejo.filings(since=date(2020, 1, 1), kind="IP", issuer="A48265169")', 0.5),
    ("len(bbva)", 0.2),
    ('for y in range(2020, 2027): print(y, "█" * sum(f.registered_at.year == y for f in bbva))', 2.5),
    ('sabadell = [f for f in reversed(bbva) if "Sabadell" in f.title]', 0.4),
    ('for f in sabadell: print(f"{f.registered_at:%d %b %Y}  {f.title[:85]}")', 4.0),
    ('result = next(f for f in bbva if "resultado de la opa" in f.title)', 0.3),
    ("text = catalejo.document_text(result)", 0.3),
    ('print(text[text.find("En consecuencia"):text.find(" al no haber")])', 5.0),
]


def type_out(code: str) -> None:
    console.print("[bold green]>>>[/] ", end="")
    for ch in code:
        console.print(ch, end="", markup=False, highlight=False)
        time.sleep(random.uniform(0.008, 0.025))
    console.print()


console.clear()
time.sleep(1)
for code, pause in STEPS:
    type_out(code)
    if "=" not in code.split("(")[0] and not code.startswith(("import", "from", "for", "print")):
        console.print(eval(code, ns))  # bare expressions echo like the real REPL
    else:
        exec(code, ns)
    time.sleep(pause)
console.print("[bold green]>>>[/] ")
time.sleep(3)
