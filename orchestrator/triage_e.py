"""Full strategy E (triage_review) 러너 — git worktree 격리 실행용.

도구의 _triage_then_review를 그대로 호출한다: (1) judge가 사전 triage →
(2) fixer가 TRUE_POSITIVE만 실제 fix(worktree 파일 수정) → (3) judge가 결과
(적용된 fix 또는 FP skip)를 사후 review. 서버 재스캔은 하지 않으므로 원격
프로젝트 측정값은 보존되고, fix는 전달한 worktree 안에서만 일어난다.
원본 체크아웃은 별도 worktree라 건드리지 않는다.
"""
import os, sys, json, argparse, subprocess

sys.path.insert(0, os.path.dirname(__file__))
from src.config import AppConfig
from src.orchestrator import SonarQubeOrchestrator


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config-remote.yml")
    ap.add_argument("--project-key", required=True)
    ap.add_argument("--worktree", required=True,
                    help="격리된 worktree 경로 (fix가 여기에만 적용됨)")
    ap.add_argument("--types", default="BUG,VULNERABILITY")
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--judge-type", default=None)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--out", default="/tmp/triage_e_result.json")
    args = ap.parse_args()

    cfg = AppConfig.load(args.config)
    cfg.assessment.strategy = "triage_review"
    if args.judge_type is not None:
        cfg.agent.judge_type = args.judge_type
    if args.judge_model is not None:
        cfg.agent.judge_model = args.judge_model
    orch = SonarQubeOrchestrator(cfg)
    wd = os.path.expanduser(args.worktree)

    issues = orch._sonar.get_open_issues(
        args.project_key, issue_types=args.types.split(","),
        max_results=args.max,
    )
    print(f"[E] {args.project_key}: {len(issues)}개 이슈 ({args.types}) — "
          f"strategy=triage_review, fixer={orch._agent.name()}, "
          f"judge={orch._judge.name()}, worktree={wd}", flush=True)

    # 도구의 strategy E 그대로: 사전 triage → TP fix → 사후 review
    fixes, skipped = orch._triage_then_review(issues, wd)

    rows = []
    for fr in fixes:
        rows.append({
            "kind": "TP_FIXED" if fr.success else "TP_NOFIX",
            "key": fr.issue_key, "file": fr.file_path,
            "fix_confidence": fr.fix_confidence,
            "explanation": fr.explanation,
        })
    for iss, tr in skipped:
        rows.append({
            "kind": "FP_SKIPPED", "key": iss.key, "rule": iss.rule,
            "file": iss.file_path, "line": iss.line,
            "confidence": tr.confidence, "reason": tr.reason,
        })
    json.dump(rows, open(args.out, "w"), ensure_ascii=False, indent=2)

    diff = subprocess.run(["git", "-C", wd, "diff", "--stat"],
                          capture_output=True, text=True).stdout
    tp_fixed = sum(1 for r in rows if r["kind"] == "TP_FIXED")
    tp_nofix = sum(1 for r in rows if r["kind"] == "TP_NOFIX")
    fp = sum(1 for r in rows if r["kind"] == "FP_SKIPPED")
    print(f"\n[E] 완료: TP_fix적용={tp_fixed}  TP_fix실패={tp_nofix}  "
          f"FP_skip={fp}  → {args.out}")
    print(f"\n[E] worktree 변경 (원본 아님):\n{diff}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
