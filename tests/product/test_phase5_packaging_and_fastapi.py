"""Phase 5 tests: SDK packaging and FastAPI HTTP runtime."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from quimera_semantic_trust_guardrail import (
    QuimeraGuardrails,
    SimpleKnowledgeAdapter,
    create_fastapi_app,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# P5-T01: SDK packaging metadata
# ---------------------------------------------------------------------------


def test_pyproject_exposes_required_metadata():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[project]" in pyproject
    assert 'name = "quimera-semantic-trust-guardrail"' in pyproject
    assert 'description =' in pyproject
    assert 'requires-python = ">=3.10"' in pyproject
    assert "[project.optional-dependencies]" in pyproject
    assert "fastapi" in pyproject
    assert "uvicorn" in pyproject
    assert "[project.scripts]" in pyproject
    assert "quimera =" in pyproject
    assert "quimera-serve =" in pyproject
    assert "[project.urls]" in pyproject
    assert "Homepage" in pyproject
    # Classifiers
    assert "Development Status" in pyproject
    assert "Topic :: Scientific/Engineering :: Artificial Intelligence" in pyproject
    # Keywords
    assert "guardrail" in pyproject
    assert "trivalent" in pyproject


def test_pyproject_packages_include_vendored_modules():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # Make sure the three package families are discoverable by setuptools.
    assert "quimera_semantic_trust_guardrail" in pyproject
    assert "groundcite" in pyproject
    assert "quimera_legacy" in pyproject


def test_py_typed_marker_exists():
    marker = (
        PROJECT_ROOT
        / "src"
        / "quimera_semantic_trust_guardrail"
        / "py.typed"
    )
    assert marker.exists()
    assert marker.read_text(encoding="utf-8") == ""


def test_console_scripts_module_is_importable():
    """The console script entry point module must be importable without
    triggering the FastAPI import."""
    module = importlib.import_module("quimera_semantic_trust_guardrail.__main__")
    assert hasattr(module, "main")
    assert hasattr(module, "serve_main")
    assert callable(module.main)
    assert callable(module.serve_main)


def test_cli_version_subcommand(capsys):
    from quimera_semantic_trust_guardrail.__main__ import main

    exit_code = main(["version"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["name"] == "quimera-semantic-trust-guardrail"
    assert isinstance(payload["version"], str)
    assert payload["version"]


def test_cli_claim_subcommand_runs_claim_check(capsys):
    from quimera_semantic_trust_guardrail.__main__ import main

    exit_code = main(["claim", "Refunds are available within 30 days."])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] in {"TRUE", "FALSE", "UNDECIDABLE"}
    assert "proof_id" in payload
    assert "adapter:supported" in payload["decision_path"]


def test_cli_serve_subcommand_handles_missing_fastapi(monkeypatch, capsys):
    """When FastAPI is not installed, the ``serve`` subcommand must
    fail gracefully with a clear error message and a non-zero exit code."""
    from quimera_semantic_trust_guardrail import __main__ as cli

    def fake_import_uvicorn(name, *args, **kwargs):
        raise ImportError("simulated missing fastapi extra")

    monkeypatch.setitem(sys.modules, "uvicorn", None)
    # Force ImportError on the `import uvicorn` call inside serve_main
    original_import = cli.__builtins__["__import__"] if isinstance(cli.__builtins__, dict) else cli.__builtins__.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("simulated missing fastapi extra")
        return original_import(name, *args, **kwargs)

    if isinstance(cli.__builtins__, dict):
        cli.__builtins__["__import__"] = guarded_import
    else:
        cli.__builtins__.__import__ = guarded_import

    try:
        exit_code = cli.serve_main(host="127.0.0.1", port=8123)
    finally:
        if isinstance(cli.__builtins__, dict):
            cli.__builtins__["__import__"] = original_import
        else:
            cli.__builtins__.__import__ = original_import

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FastAPI" in captured.err


def test_package_installed_in_editable_mode():
    """The package must be importable as ``quimera_semantic_trust_guardrail``
    from the active Python interpreter. This is a fresh-install smoke
    test that does not depend on PYTHONPATH being set."""
    spec = importlib.util.find_spec("quimera_semantic_trust_guardrail")
    assert spec is not None
    assert spec.origin is not None
    assert "quimera_semantic_trust_guardrail" in spec.origin.replace("\\", "/")


def test_package_metadata_is_accessible():
    module = importlib.import_module("quimera_semantic_trust_guardrail")
    assert isinstance(module.__version__, str)
    assert module.__version__


def test_examples_folder_contains_runnable_scripts():
    examples_dir = PROJECT_ROOT / "examples"
    assert examples_dir.is_dir()
    scripts = sorted(p.name for p in examples_dir.glob("*.py"))
    assert "01_claim_check_basic.py" in scripts
    assert "02_ontology_versioning.py" in scripts
    assert "03_fastapi_server.py" in scripts
    for script in scripts:
        text = (examples_dir / script).read_text(encoding="utf-8")
        # Each example must be importable and runnable as __main__.
        assert "__name__" in text
        assert "__main__" in text or "asyncio.run" in text or "uvicorn.run" in text


def test_example_claim_check_basic_runs(tmp_path):
    """The basic example must run as a regular Python script and return
    a JSON-friendly dict."""

    code = (
        "import asyncio, json, sys, importlib.util, pathlib;"
        "sys.path.insert(0, r'" + str(PROJECT_ROOT / "src") + "');"
        "spec = importlib.util.spec_from_file_location("
        "'example_basic', r'" + str(PROJECT_ROOT / "examples" / "01_claim_check_basic.py") + "');"
        "module = importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(module);"
        "asyncio.run(module.main());"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "decision" in result.stdout
    assert "proof_id" in result.stdout


# ---------------------------------------------------------------------------
# P5-T02: Optional FastAPI runtime
# ---------------------------------------------------------------------------


pytestmark_fastapi = pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="fastapi optional extra not installed",
)


@pytest.fixture
def fastapi_app(tmp_path):
    from fastapi.testclient import TestClient

    app = create_fastapi_app(
        proof_storage_path=str(tmp_path / "proofs"),
        ontology_storage_path=str(tmp_path / "ontologies"),
    )
    client = TestClient(app)
    yield client
    client.close()


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_health_endpoint(fastapi_app):
    response = fastapi_app.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_claim_check_requires_tenant_header(fastapi_app):
    response = fastapi_app.post("/claim-check", json={"claim": "Hello."})
    assert response.status_code == 401
    assert "X-Tenant-ID" in response.json()["detail"]


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_claim_check_supported_path(fastapi_app):
    app = fastapi_app.app
    adapter = SimpleKnowledgeAdapter()
    adapter.add_fact(
        "Refunds are available within 30 days.",
        source="policy",
        keywords=["refunds"],
    )
    guardrails = QuimeraGuardrails(
        tenant_id="acme",
        config=None,
        knowledge_adapter=adapter,
    )
    app.tenant_guardrails = {"acme": guardrails}  # type: ignore[attr-defined]

    response = fastapi_app.post(
        "/claim-check",
        json={"claim": "Refunds are available within 30 days."},
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "TRUE"
    assert body["recommended_action"] == "allow"
    assert body["proof"]["proof_id"]


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_claim_check_unsupported_path(fastapi_app):
    response = fastapi_app.post(
        "/claim-check",
        json={"claim": "An obscure claim with no support anywhere."},
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "UNDECIDABLE"
    assert body["recommended_action"] == "abstain"
    assert any(
        req["requirement_type"] == "evidence"
        for req in body["missing_requirements"]
    )


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_answer_check_decomposes(fastapi_app):
    response = fastapi_app.post(
        "/answer-check",
        json={
            "answer": "Refunds are available within 30 days. "
            "We are headquartered in Berlin."
        },
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] in {"UNDECIDABLE", "FALSE", "TRUE"}
    assert "dependency_graph" in body["proof"]["metadata"]


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_action_check(fastapi_app):
    response = fastapi_app.post(
        "/action-check",
        json={
            "action": "read_pii",
            "actor": "agent_007",
            "resource": "user_profile",
            "purpose": "support_request",
        },
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 200
    body = response.json()
    # Without an explicit permission fact, the runtime must abstain.
    assert body["decision"] == "UNDECIDABLE"
    assert body["recommended_action"] == "escalate"


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_policy_check_blocks_lgpd_pii(fastapi_app):
    response = fastapi_app.post(
        "/policy-check",
        json={
            "text": "The customer CPF 123.456.789-00 must be stored in plain text.",
            "scope": "output",
        },
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "FALSE"
    assert body["recommended_action"] == "block"


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_proof_lookup_and_404(fastapi_app):
    # First create a proof
    claim = fastapi_app.post(
        "/claim-check",
        json={"claim": "An obscure claim with no support anywhere."},
        headers={"X-Tenant-ID": "acme"},
    )
    proof_id = claim.json()["proof"]["proof_id"]
    response = fastapi_app.get(
        f"/proofs/{proof_id}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 200
    assert response.json()["proof_id"] == proof_id

    missing = fastapi_app.get(
        "/proofs/QPR-doesnotexist",
        headers={"X-Tenant-ID": "acme"},
    )
    assert missing.status_code == 404


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_snapshot_and_rollback(fastapi_app):
    snap = fastapi_app.post(
        "/ontologies/snapshots",
        json={"name": "v1"},
        headers={"X-Tenant-ID": "acme"},
    )
    assert snap.status_code == 200
    snap_payload = snap.json()
    assert snap_payload["snapshot_id"]
    assert snap_payload["proof_id"]

    listed = fastapi_app.get(
        "/ontologies/snapshots",
        headers={"X-Tenant-ID": "acme"},
    )
    assert listed.status_code == 200
    assert any(
        item["snapshot_id"] == snap_payload["snapshot_id"]
        for item in listed.json()["snapshots"]
    )

    rollback = fastapi_app.post(
        "/ontologies/rollback",
        json={"snapshot_id": snap_payload["snapshot_id"]},
        headers={"X-Tenant-ID": "acme"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["snapshot_id"] == snap_payload["snapshot_id"]


@pytest.mark.usefixtures("fastapi_app")
def test_fastapi_rollback_unknown_snapshot_returns_404(fastapi_app):
    response = fastapi_app.post(
        "/ontologies/rollback",
        json={"snapshot_id": "snap_doesnotexist"},
        headers={"X-Tenant-ID": "acme"},
    )
    assert response.status_code == 404


def test_fastapi_app_lazy_loads_without_fastapi(monkeypatch):
    """If FastAPI is missing, importing the module must fail clearly
    only when the user calls ``create_app``."""
    from importlib import reload

    # Simulate missing fastapi by injecting a None module.
    sys.modules["fastapi"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(ImportError):
            from quimera_semantic_trust_guardrail import fastapi_app as fapp

            reload(fapp)
    finally:
        # Restore the real fastapi module if it was previously loaded.
        sys.modules.pop("fastapi", None)
        try:
            __import__("fastapi")
        except Exception:
            pass


def test_create_fastapi_app_is_reexported():
    module = importlib.import_module("quimera_semantic_trust_guardrail")
    assert hasattr(module, "create_fastapi_app")
