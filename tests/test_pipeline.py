"""Item 4 — the product surface: translate_project composition.

The full model-in-the-loop run (ingest->translate->verify->Miri->signed manifest) is
proven on the box; here we lock the composition's honesty path without a model: an
out-of-scope function is refused (with a reason) before any translation is attempted.
"""

from alchemist.autonomy.pipeline import translate_project


def test_translate_project_refuses_oos_without_model(tmp_path):
    (tmp_path / "lib.c").write_text(
        "#include <stdio.h>\nvoid logit(const char *m) { printf(\"%s\", m); }\n")
    # oos functions never reach the model -> llm=None is fine
    manifest = translate_project(str(tmp_path), tmp_path / "work", llm=None, env={}, max_fns=5)
    outcomes = {f.function: f for f in manifest.functions}
    assert outcomes["logit"].verdict == "refused"
    assert "oos" in outcomes["logit"].reason
    assert manifest.summary()["by_verdict"].get("verified", 0) == 0


def test_translate_project_manifest_is_signed(tmp_path):
    (tmp_path / "lib.c").write_text("void logit(const char *m) { fputs(m, stderr); }\n")
    manifest = translate_project(str(tmp_path), tmp_path / "work", llm=None, env={})
    att = manifest.attest()
    assert att["project"] == tmp_path.name
    assert len(att["sha256"]) == 64 and "summary" in att and "signature" in att
