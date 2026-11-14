import json
from pathlib import Path


def test_tauri_strict_content_security_policy():
    """Verify that Tauri 2 desktop configuration enforces a strict Content Security Policy."""
    project_root = Path(__file__).resolve().parent.parent.parent
    tauri_conf_path = project_root / "src-tauri" / "tauri.conf.json"

    assert tauri_conf_path.exists(), "src-tauri/tauri.conf.json must exist"
    with open(tauri_conf_path, "r", encoding="utf-8") as f:
        conf = json.load(f)

    csp = conf.get("app", {}).get("security", {}).get("csp")
    assert csp is not None, "security.csp must not be null"
    assert isinstance(csp, str) and len(csp) > 20, "security.csp must be a configured policy string"

    directives = [d.strip() for d in csp.split(";") if d.strip()]
    parsed_csp = {}
    for d in directives:
        parts = d.split()
        if parts:
            parsed_csp[parts[0]] = parts[1:]

    # 1. default-src
    assert "default-src" in parsed_csp
    assert "'self'" in parsed_csp["default-src"]

    # 2. script-src (Strict, no unsafe-eval, no wildcard)
    assert "script-src" in parsed_csp
    assert "'self'" in parsed_csp["script-src"]
    assert "'unsafe-eval'" not in parsed_csp["script-src"]
    assert "*" not in parsed_csp["script-src"]

    # 3. connect-src (Only self and local backend)
    assert "connect-src" in parsed_csp
    connect_src = parsed_csp["connect-src"]
    assert "'self'" in connect_src
    assert "http://127.0.0.1:8000" in connect_src
    assert "http://localhost:8000" in connect_src
    assert "https://*" not in connect_src

    # 4. img-src (self, data:, blob:)
    assert "img-src" in parsed_csp
    img_src = parsed_csp["img-src"]
    assert "'self'" in img_src
    assert "data:" in img_src
    assert "blob:" in img_src

    # 5. style-src
    assert "style-src" in parsed_csp
    assert "'self'" in parsed_csp["style-src"]

    # 6. font-src
    assert "font-src" in parsed_csp
    assert "'self'" in parsed_csp["font-src"]

    # 7. object-src (disallow plugins)
    assert "object-src" in parsed_csp
    assert "'none'" in parsed_csp["object-src"]

    # 8. frame-ancestors (clickjacking prevention)
    assert "frame-ancestors" in parsed_csp
    assert "'none'" in parsed_csp["frame-ancestors"]
