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

    p_commercial = sub.add_parser(
        "commercial-demo",
        help="Run the deterministic commercial discovery demo.",
    )
    p_commercial.add_argument(
        "--output-dir",
        default="artifacts/commercial",
        help="Commercial demo artifact directory (default: artifacts/commercial).",
    )
    p_commercial.add_argument(
        "--run-id",
        default="commercial-demo",
        help="Run identifier (default: commercial-demo).",
    )
    p_commercial.add_argument(
        "--use-llm",
        action="store_true",
        help="Optionally call NVIDIA MiniMax M3 first and OpenRouter fallback.",
    )

    p_rag = sub.add_parser(
        "rag-benchmark",
        help="Run the offline three-stage embedding-backed RAG benchmark.",
    )
    p_rag.add_argument(
        "--output-dir",
        default="artifacts/evaluation",
        help="Evaluation artifact directory (default: artifacts/evaluation).",
    )
    p_rag.add_argument(
        "--run-id",
        default="rag-seed-benchmark",
        help="Run identifier (default: rag-seed-benchmark).",
    )
    p_rag.add_argument(
        "--manifest",
        default="data/evaluation/rag_seed/manifest.json",
        help="RAG dataset manifest path.",
    )
    p_rag.add_argument(
        "--model",
        default=None,
        help="Sentence Transformers model name (uses the portfolio default when omitted).",
    )
    p_rag.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of retrieved documents used for ranking/context metrics.",
    )

    p_llm_rag = sub.add_parser(
        "rag-llm-benchmark",
        help="Run the opt-in RAG benchmark with NVIDIA first and OpenRouter fallback.",
    )
    p_llm_rag.add_argument("--output-dir", default="artifacts/evaluation")
    p_llm_rag.add_argument("--run-id", default="rag-llm-benchmark")
    p_llm_rag.add_argument("--manifest", default="data/evaluation/rag_seed/manifest.json")
    p_llm_rag.add_argument("--model", default=None)
    p_llm_rag.add_argument("--top-k", type=int, default=3)
    p_llm_rag.add_argument(
        "--no-paid-fallback",
        action="store_true",
        help="Do not call the paid OpenRouter provider if NVIDIA fails.",
    )

    p_replay = sub.add_parser(
        "trace-replay",
        help="Replay an evaluation trace as JSON or human-readable text.",
    )
    p_replay.add_argument("trace", help="Path to trace.jsonl")
    p_replay.add_argument("--case-id", default=None)
    p_replay.add_argument("--json", action="store_true", dest="as_json")

    p_proof = sub.add_parser(
        "proof-explain",
        help="Replay and explain one proof ledger entry.",
    )
    p_proof.add_argument("proof_id")
    p_proof.add_argument("--storage", default=".quimera_cli_proofs")
    p_proof.add_argument("--json", action="store_true", dest="as_json")

    p_showcase = sub.add_parser(
        "showcase",
        help="Run the offline portfolio showcase without API keys.",
    )
    p_showcase.add_argument(
        "--output-dir",
        default="artifacts/showcase",
        help="Showcase artifact directory (default: artifacts/showcase).",
    )
    p_showcase.add_argument(
        "--run-id",
        default="portfolio-showcase",
        help="Run identifier (default: portfolio-showcase).",
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

    if args.command == "commercial-demo":
        from .evaluation import run_commercial_demo

        run_dir = run_commercial_demo(
            output_dir=args.output_dir,
            run_id=args.run_id,
            use_llm=args.use_llm,
        )
        _print_json({"run_dir": str(run_dir)})
        return 0

    if args.command == "rag-benchmark":
        from .evaluation import run_rag_benchmark

        kwargs = {
            "manifest_path": args.manifest,
            "output_dir": args.output_dir,
            "run_id": args.run_id,
            "top_k": args.top_k,
        }
        if args.model:
            kwargs["model_name"] = args.model
        run_dir = run_rag_benchmark(**kwargs)
        _print_json({"run_dir": str(run_dir), "llm_api_key_required": False})
        return 0

    if args.command == "rag-llm-benchmark":
        from .evaluation import SentenceTransformerEmbedding, run_llm_rag_benchmark

        kwargs = {
            "manifest_path": args.manifest,
            "output_dir": args.output_dir,
            "run_id": args.run_id,
            "top_k": args.top_k,
            "allow_paid_fallback": not args.no_paid_fallback,
            "embedder": SentenceTransformerEmbedding(model_name=args.model)
            if args.model
            else SentenceTransformerEmbedding(),
        }
        run_dir = run_llm_rag_benchmark(**kwargs)
        _print_json({"run_dir": str(run_dir), "llm_api_key_required": True})
        return 0

    if args.command == "trace-replay":
        from .evaluation import explain_trace, replay_trace

        if args.as_json:
            _print_json(replay_trace(args.trace, case_id=args.case_id))
        else:
            sys.stdout.write(explain_trace(args.trace, case_id=args.case_id) + "\n")
        return 0

    if args.command == "proof-explain":
        from .evaluation import explain_proof, replay_proof

        if args.as_json:
            _print_json(replay_proof(args.storage, args.proof_id))
        else:
            sys.stdout.write(explain_proof(args.storage, args.proof_id) + "\n")
        return 0

    if args.command == "showcase":
        from .evaluation import run_showcase

        run_dir = run_showcase(output_dir=args.output_dir, run_id=args.run_id)
        _print_json({"run_dir": str(run_dir), "llm_api_key_required": False})
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
