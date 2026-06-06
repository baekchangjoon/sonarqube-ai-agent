import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.config import AppConfig
from src.orchestrator import SonarQubeOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


class OrchestratorCLI:
    """CLI entry point for the SonarQube AI Agent Orchestrator."""

    def __init__(self):
        self._parser = _build_parser()

    def run(self) -> int:
        args = self._parser.parse_args()
        _load_env()
        config = AppConfig.load(args.config)
        orchestrator = SonarQubeOrchestrator(config)

        if not orchestrator.sonar.is_healthy():
            logger.error("SonarQube is not reachable at %s", config.sonarqube.url)
            return 1

        handler = {
            "pr-premerge": _handle_pr_premerge,
            "post-merge": _handle_post_merge,
            "nightly-batch": _handle_nightly_batch,
            "summary": _handle_summary,
        }
        return handler[args.command](args, orchestrator)


def _load_env() -> None:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _handle_pr_premerge(args, orch: SonarQubeOrchestrator) -> int:
    result = orch.handle_pr_premerge(
        repo=args.repo, pr_number=args.pr_number,
        project_dir=args.project_dir,
        pr_branch=args.pr_branch, pr_base=args.pr_base,
    )
    _print_result(result)
    if args.cleanup:
        orch.cleanup_pr_project(args.pr_number)
    return 0 if result.quality_gate != "ERROR" else 1


def _handle_post_merge(args, orch: SonarQubeOrchestrator) -> int:
    result = orch.handle_post_merge(
        project_dir=getattr(args, "project_dir", None),
    )
    _print_result(result)
    return 0


def _handle_nightly_batch(args, orch: SonarQubeOrchestrator) -> int:
    result = orch.handle_nightly_batch(
        project_dir=getattr(args, "project_dir", None),
    )
    _print_result(result)
    return 0


def _handle_summary(args, orch: SonarQubeOrchestrator) -> int:
    summary = orch.get_project_summary(getattr(args, "project_key", None))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SonarQube AI Agent Orchestrator",
    )
    parser.add_argument("--config", default=None, help="Path to config.yml")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_pr_premerge_cmd(sub)
    _add_post_merge_cmd(sub)
    _add_nightly_batch_cmd(sub)
    _add_summary_cmd(sub)
    return parser


def _add_pr_premerge_cmd(sub) -> None:
    cmd = sub.add_parser("pr-premerge", help="Mode 1: Analyze PR before merge")
    cmd.add_argument("--repo", required=True)
    cmd.add_argument("--pr-number", type=int, required=True)
    cmd.add_argument("--project-dir", required=True)
    cmd.add_argument("--pr-branch", default=None,
                     help="PR branch name (native pr_mode)")
    cmd.add_argument("--pr-base", default="main",
                     help="PR base branch (native pr_mode)")
    cmd.add_argument("--cleanup", action="store_true",
                     help="Delete ephemeral project after analysis")


def _add_post_merge_cmd(sub) -> None:
    cmd = sub.add_parser("post-merge", help="Mode 2: Analyze main after merge")
    cmd.add_argument("--project-dir", default=None)


def _add_nightly_batch_cmd(sub) -> None:
    cmd = sub.add_parser("nightly-batch", help="Mode 3: Nightly tech debt reduction")
    cmd.add_argument("--project-dir", default=None)


def _add_summary_cmd(sub) -> None:
    cmd = sub.add_parser("summary", help="Show project quality summary")
    cmd.add_argument("--project-key", default=None)


def _print_result(result) -> None:
    output = {
        "mode": result.mode,
        "project_key": result.project_key,
        "issues_found": result.issues_found,
        "issues_skipped_as_fp": result.issues_skipped_as_fp,
        "fixes_attempted": result.fixes_attempted,
        "fixes_verified": result.fixes_verified,
        "quality_gate": result.quality_gate,
        "llm_input_tokens": result.llm_input_tokens,
        "llm_output_tokens": result.llm_output_tokens,
        "llm_cost_usd": result.llm_cost_usd,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main() -> int:
    cli = OrchestratorCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
