"""Command line interface for Quimera Semantic Trust Guardrail.

The package exposes two console scripts:

* ``quimera``  -> :func:`main` — quick local checks (version, claim, proof).
* ``quimera-serve`` -> :func:`serve_main` — start the optional FastAPI runtime.

Both entry points intentionally avoid hard dependencies on FastAPI at
import time: the FastAPI-based server only fails if the user actually
asks for it and the optional ``[fastapi]`` extra is not installed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from . import __version__
from .runtime import SemanticTrustRuntime
from .adapters import SimpleKnowledgeAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quimera",
        description="Quimera Semantic Trust Guardrail command line interface.",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("version", help="Print the installed version and exit.")

    p_claim = sub.add_parser("claim", help="Run a one-off claim check.")
    p_claim.add_argument("text", help="The claim text to validate.")
    p_claim.add_argument(
        "--tenant",
        default="cli-tenant",
        help="Tenant ID (default: cli-tenant).",
    )

    p_serve = sub.add_parser("serve", help="Start the FastAPI HTTP runtime.")
    p_serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default: 127.0.0.1).",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port (default: 8000).",
    )
    p_serve.add_argument(
        "--proof-storage",
        default=".quimera_cli_proofs",
        help="Proof storage path (default: .quimera_cli_proofs).",
    )
    p_serve.add_argument(
        "--ontology-storage",
        default=".quimera_cli_ontologies",
        help="Ontology storage path (default: .quimera_cli_ontologies).",
    )

    p_science = sub.add_parser(
        "scientific-baseline",
        help="Run the deterministic scientific seed baseline.",
    )
    p_science.add_argument(
        "--output-dir",
        default="artifacts/evaluation",
        help="Evaluation artifact directory (default: artifacts/evaluation).",
    )
    p_science.add_argument(
        "--run-id",
        default="scientific-seed-baseline",
        help="Run identifier (default: scientific-seed-baseline).",
    )
    p_science.add_argument(
        "--manifest",
        default="data/evaluation/scientific_seed/manifest.json",
        help="Dataset manifest path.",
    )

    return parser


def _print_json(payload: Dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


async def _run_claim(tenant: str, text: str) -> Dict[str, Any]:
    runtime = SemanticTrustRuntime(tenant_id=tenant)
    adapter = SimpleKnowledgeAdapter()
    adapter.add_fact(
        "Refunds are available within 30 days.",
        source="cli-default",
        keywords=["refunds"],
    )
    runtime.knowledge_adapter = adapter
    result = await runtime.claim_check(text)
    return {
        "decision": result.decision.value,
        "recommended_action": result.recommended_action.value,
        "confidence": result.confidence,
        "status": result.status.value,
        "proof_id": result.proof.proof_id,
        "decision_path": result.proof.decision_path,
    }


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the ``quimera`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None or args.command == "version":
        _print_json({"name": "quimera-semantic-trust-guardrail", "version": __version__})
        return 0

    if args.command == "claim":
        payload = asyncio.run(_run_claim(args.tenant, args.text))
        _print_json(payload)
        return 0

    if args.command == "serve":
        return serve_main(
            host=args.host,
            port=args.port,
            proof_storage=args.proof_storage,
            ontology_storage=args.ontology_storage,
        )

    if args.command == "scientific-baseline":
        from .evaluation import run_scientific_baseline

        run_dir = run_scientific_baseline(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
        _print_json({"run_dir": str(run_dir)})
        return 0

    parser.print_help()
    return 1


def serve_main(
    host: str = "127.0.0.1",
    port: int = 8000,
    proof_storage: str = ".quimera_cli_proofs",
    ontology_storage: str = ".quimera_cli_ontologies",
) -> int:
    """Entry point for the ``quimera-serve`` console script.

    Imports the FastAPI app lazily so that the base package can be used
    without the optional ``[fastapi]`` extra installed.
    """
    try:
        import uvicorn  # type: ignore
    except ImportError as exc:  # pragma: no cover - requires optional extra
        sys.stderr.write(
            "FastAPI runtime requires the [fastapi] extra. "
            "Install with: pip install 'quimera-semantic-trust-guardrail[fastapi]'\n"
        )
        sys.stderr.write(f"Original error: {exc}\n")
        return 1

    from .fastapi_app import create_app  # lazy import: depends on fastapi

    app = create_app(
        proof_storage_path=proof_storage,
        ontology_storage_path=ontology_storage,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
