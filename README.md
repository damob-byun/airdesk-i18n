# AirDesk i18n

Translation catalogs for every AirDesk app (Windows, macOS, Linux desktop,
Android, iOS). Every platform reads the same files, so a language added here
shows up on desktop and mobile in the next app build. No app code changes are
needed.

## Layout

```text
languages.tsv                    language registry (the only language list)
<code>/LC_MESSAGES/repc.po       UI strings: desktop Slint UI + mobile screens (required)
<code>/LC_MESSAGES/native.po     desktop native strings: overlay toolbar etc. (optional)
tools/catalog.py                 status / check / add / sync (Python 3 stdlib only)
```

- Catalogs are gettext `.po` files. **`msgid` is the English source text.**
  An empty `msgstr` (or a `#, fuzzy` entry) shows English.
- `en` is the source language. The English catalogs may supply alternate
  wording. `sync` leaves them as they are.
- `ko` is the reference catalog: it translates every msgid in use, and new
  languages are scaffolded from its msgids.
- Keep both Korean catalogs complete. Other languages may be partial.
- `msgctxt` separates one English word that needs two translations
  (for example `Off` as a status value vs. an effect state).
- Keep `{name}` style placeholders unchanged in translations. Word order may
  change; the placeholder set may not.

## languages.tsv

```text
ko	한국어
en	English
ja	日本語
```

- One line = `<code><TAB><language name written in that language>`.
  Codes are BCP 47 (`fr`, `pt-BR`, `zh-Hant`).
- **Append only.** Mobile apps store the line index as the user's language
  setting, so reordering or deleting lines changes users' languages.
- The first line (`ko`) stays first: it is the default language.
- Every folder with `LC_MESSAGES/` must be listed (`check` fails otherwise).

## Adding a language

```sh
python tools/catalog.py add pt-BR "Português (Brasil)"
# translate the msgstr lines in pt-BR/LC_MESSAGES/repc.po and native.po
python tools/catalog.py check
python tools/catalog.py status
```

Partly translated languages build and ship; untranslated entries show English.

## How apps load the catalogs (build time)

| Platform | Reads | Mechanism |
|---|---|---|
| Desktop Slint UI | `repc.po` of every registered language | Slint bundled translations (`SLINT_BUNDLE_TRANSLATIONS` → this folder) |
| Desktop native strings | `languages.tsv` + `native.po` | CMake embeds each catalog into the binary |
| Android / iOS | `languages.tsv` + `repc.po` | Cargo `build.rs` embeds each catalog with `include_str!` |

All of them scan `languages.tsv` when the app builds, so a new line + its
folder is picked up automatically. Lookup at runtime: exact code (`pt-BR`,
case and `_` ignored) → base language (`pt`) → the English msgid.

## Contributing

1. Edit or add `.po` files. Keep UTF-8 and LF line endings.
2. Run `python tools/catalog.py check`.
3. Open a pull request.

## License

MIT. See [LICENSE](LICENSE).
