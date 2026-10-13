from rozmarra.language.check import RULES_FILE, check


def _write(root, path, text):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")


def test_the_check_finds_words_to_avoid_and_american_spellings(tmp_path):
    readme = "# Title\n\nThe twin warns before a hypo.\nWe analyzed the data.\n"
    _write(tmp_path, "README.md", readme)
    _write(
        tmp_path,
        "backend/src/rozmarra/example.py",
        '# The pt takes two meds.\nMESSAGE = "Glucose may spike after the meal."\nSU = 1\n',
    )
    _write(tmp_path, "frontend/src/i18n/en.json", '{\n  "alert": "Break your fast now!"\n}\n')
    found = {(f.path, f.line, f.found) for f in check(tmp_path, RULES_FILE)}
    assert ("README.md", 3, "hypo") in found
    assert ("README.md", 4, "analyzed") in found
    assert ("backend/src/rozmarra/example.py", 1, "pt") in found
    assert ("backend/src/rozmarra/example.py", 1, "meds") in found
    assert ("backend/src/rozmarra/example.py", 2, "spike") in found
    assert ("frontend/src/i18n/en.json", 2, "!") in found
    # A code name may use a technical term, so the variable name is not reported.
    assert not any(f[2] == "SU" for f in found)


def test_the_check_keeps_examples_titles_web_addresses_and_code(tmp_path):
    _write(
        tmp_path,
        "docs/prd.md",
        '## 17.1 Rules\n\n- Use "low blood sugar", not "hypo".\n   - Not: "hypo alert"\n\n'
        "### 17.3 Words to avoid\n\n| hypo, hypos | low blood sugar |\n\n## 18. Next\n\nText.\n",
    )
    _write(
        tmp_path,
        "README.md",
        "See https://github.com/example/stanford-hypoglycemia-forecasting for details.\n\n"
        "```powershell\nuv run rozmarra --meds\n```\n\nRun `hypo` only in code.\n",
    )
    assert check(tmp_path, RULES_FILE) == []


def test_the_repository_passes_the_language_check():
    findings = check()
    assert findings == [], "\n".join(str(f) for f in findings)
