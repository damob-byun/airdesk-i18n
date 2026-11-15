#!/usr/bin/env python3
"""AirDesk translation catalogs: standalone tool for this repository.

Needs only the Python 3.8+ standard library and works from a bare checkout of
the i18n repository (no app sources required).

  python tools/catalog.py status            per-language translation coverage
  python tools/catalog.py check             fail on registry/catalog problems
  python tools/catalog.py add <code> <name> scaffold a new language, e.g.
                                            add pt-BR "Português (Brasil)"
  python tools/catalog.py sync              add missing reference msgids to every catalog

Layout (see README.md):
  languages.tsv                      <code><TAB><native name>, append-only
  <code>/LC_MESSAGES/repc.po         UI strings (required)
  <code>/LC_MESSAGES/native.po       desktop native strings (optional)
Korean (the first registry line) is the reference catalog.
"""
import ast
import re
import sys
from pathlib import Path

LANG = Path(__file__).resolve().parents[1]
REGISTRY = LANG / "languages.tsv"
REFERENCE = "ko"
SOURCE_LANGUAGE = "en"  # msgid language: sync leaves existing English copy alone
DOMAINS = ("repc", "native")
REQUIRED_DOMAINS = ("repc",)
CODE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]+)*$")
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")


def read_registry():
    languages = []
    for number, line in enumerate(REGISTRY.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2 or not CODE_RE.fullmatch(fields[0]) or not fields[1].strip():
            raise SystemExit(f"{REGISTRY}:{number}: expected '<code><TAB><native name>': {line!r}")
        languages.append((fields[0], fields[1]))
    codes = [code.lower() for code, _ in languages]
    if len(set(codes)) != len(codes):
        raise SystemExit(f"{REGISTRY}: duplicate language code")
    if not languages:
        raise SystemExit(f"{REGISTRY}: lists no languages")
    return languages


def parse_po(path):
    """Return ({(context, msgid): msgstr}, [entry order]). Header is skipped."""
    entries, order = {}, []
    context = msgid = msgstr = None
    field = None
    fuzzy = False

    def flush():
        nonlocal context, msgid, msgstr, field, fuzzy
        if msgid:
            key = (context or "", msgid)
            entries[key] = "" if fuzzy else (msgstr or "")
            order.append(key)
        context = msgid = msgstr = None
        field = None
        fuzzy = False

    if not path.exists():
        return entries, order
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("#,"):
            if field == "str":
                flush()
            fuzzy = fuzzy or "fuzzy" in line
        elif line.startswith("#"):
            if field == "str":
                flush()
        elif line.startswith("msgctxt "):
            if field == "str":
                flush()
            context, field = ast.literal_eval(line[8:]), "ctx"
        elif line.startswith("msgid "):
            if field == "str":
                flush()
            msgid, field = ast.literal_eval(line[6:]), "id"
        elif line.startswith("msgstr "):
            msgstr, field = ast.literal_eval(line[7:]), "str"
        elif line.startswith('"'):
            part = ast.literal_eval(line)
            if field == "ctx":
                context += part
            elif field == "id":
                msgid += part
            elif field == "str":
                msgstr += part
    flush()
    return entries, order


def po_quote(text):
    return '"' + (text.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\t", "\\t")) + '"'


def header(code, domain):
    project = "RePC" if domain == "repc" else "AirDesk native"
    return ['msgid ""', 'msgstr ""', f'"Project-Id-Version: {project}\\n"', f'"Language: {code}\\n"',
            '"MIME-Version: 1.0\\n"', '"Content-Type: text/plain; charset=UTF-8\\n"',
            '"Content-Transfer-Encoding: 8bit\\n"', ""]


def entry_lines(key, text):
    context, msgid = key
    lines = [f"msgctxt {po_quote(context)}"] if context else []
    return lines + [f"msgid {po_quote(msgid)}", f"msgstr {po_quote(text)}", ""]


def catalog_path(code, domain):
    return LANG / code / "LC_MESSAGES" / f"{domain}.po"


def reference_keys(domain):
    _, order = parse_po(catalog_path(REFERENCE, domain))
    return order


def status():
    languages = read_registry()
    print(f"{'code':8} {'name':22} " + " ".join(f"{d + '.po':>16}" for d in DOMAINS))
    for code, name in languages:
        cells = []
        for domain in DOMAINS:
            if code == SOURCE_LANGUAGE:
                cells.append(f"{'source':>16}")
                continue
            keys = reference_keys(domain)
            entries, _ = parse_po(catalog_path(code, domain))
            done = sum(1 for key in keys if entries.get(key))
            cells.append(f"{done:>6}/{len(keys):<5}{100 * done // max(len(keys), 1):>3}%")
        print(f"{code:8} {name:22} " + " ".join(cells))


def catalog_warnings():
    """Allowed but probably unintended: the language builds and shows English."""
    return [f"warning: {catalog_path(code, domain)} is missing; {code} shows English"
            for code, _ in read_registry() for domain in REQUIRED_DOMAINS
            if code != SOURCE_LANGUAGE and not catalog_path(code, domain).exists()]


def catalog_failures():
    """Problems in the registry and catalogs alone (no app sources needed)."""
    failures = []
    languages = read_registry()
    if languages[0][0] != REFERENCE:
        failures.append(f"{REGISTRY}: the first language must stay '{REFERENCE}' (stored index 0)")
    for code, _ in languages:
        for domain in DOMAINS:
            path = catalog_path(code, domain)
            entries, order = parse_po(path)
            if code == REFERENCE and not entries:
                failures.append(f"{path}: the reference catalog needs at least one translation")
            seen = set()
            for key in order:
                if key in seen:
                    failures.append(f"{code}/{domain}.po: duplicate entry {key!r}")
                seen.add(key)
            for (context, msgid), text in entries.items():
                if code == REFERENCE and not text:
                    failures.append(f"{code}/{domain}.po: missing reference translation for {(context, msgid)!r}")
                if text and sorted(PLACEHOLDER_RE.findall(msgid)) != sorted(PLACEHOLDER_RE.findall(text)):
                    failures.append(f"{code}/{domain}.po: placeholders differ for {msgid!r}")
    registered = {code for code, _ in languages}
    for folder in sorted(p.name for p in LANG.iterdir() if (p / "LC_MESSAGES").is_dir()):
        if folder not in registered:
            failures.append(f"{LANG / folder}: folder is not listed in languages.tsv")
    return failures


def check():
    for warning in catalog_warnings():
        print(warning)
    failures = catalog_failures()
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS: {len(read_registry())} languages; catalog entries and placeholders match")


def write_catalog(code, domain, keys, existing):
    path = catalog_path(code, domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# AirDesk {domain}.po for {code}. msgid is the English source;",
             "# empty msgstr shows English. See README.md."] + header(code, domain)
    for key in keys:
        lines += entry_lines(key, existing.get(key, ""))
    with path.open("w", encoding="utf-8", newline="\n") as out:
        out.write("\n".join(lines))


def add(code, name):
    if not CODE_RE.fullmatch(code):
        raise SystemExit(f"invalid language code {code!r} (use BCP 47 like 'fr' or 'pt-BR')")
    if any(not char.isprintable() for char in name) or not name.strip():
        raise SystemExit("language name must be nonempty text on one registry line")
    name = name.strip()
    if any(existing.lower() == code.lower() for existing, _ in read_registry()):
        raise SystemExit(f"{code} is already registered")
    for domain in DOMAINS:
        if catalog_path(code, domain).exists():
            raise SystemExit(f"{catalog_path(code, domain)} already exists")
    for domain in DOMAINS:
        write_catalog(code, domain, reference_keys(domain), {})
    text = REGISTRY.read_text(encoding="utf-8")
    with REGISTRY.open("w", encoding="utf-8", newline="\n") as out:
        out.write(text + ("" if text.endswith("\n") else "\n") + f"{code}\t{name}\n")
    print(f"Added {code} ({name}). Translate the msgstr lines in:")
    for domain in DOMAINS:
        print(f"  {catalog_path(code, domain).relative_to(LANG)}")


def sync():
    """Append reference msgids missing from each language's catalogs."""
    for code, _ in read_registry():
        if code in (REFERENCE, SOURCE_LANGUAGE):
            continue
        for domain in DOMAINS:
            path = catalog_path(code, domain)
            entries, _ = parse_po(path)
            missing = [key for key in reference_keys(domain) if key not in entries]
            if not missing:
                continue
            if not path.exists():
                write_catalog(code, domain, reference_keys(domain), {})
            else:
                with path.open("a", encoding="utf-8", newline="\n") as out:
                    out.write("\n" + "\n".join(line for key in missing for line in entry_lines(key, "")))
            print(f"{code}/{domain}.po: added {len(missing)} untranslated msgids")


def main(argv):
    # Native language names must not crash a non-UTF-8 console (cp949, cp932).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if argv[:1] == ["status"]:
        status()
    elif argv[:1] == ["check"]:
        check()
    elif len(argv) == 3 and argv[0] == "add":
        add(argv[1], argv[2])
    elif argv[:1] == ["sync"]:
        sync()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
