"""Read-only FP triage 러너: sonarqube-ai-agent의 triage 엔진(judge agent +
rule-doc 주입 + 소스 컨텍스트)만 호출하고 fix 단계는 부르지 않는다.

--review 를 주면 triage_review(E)의 read-only 부분을 흉내낸다: 1차 triage가
FALSE_POSITIVE로 본 건에 대해 judge가 FP 주장을 독립 재검토(AGREE_FALSE_POSITIVE/
DISAGREE)한다. fixer는 호출하지 않으므로 원본 코드는 수정되지 않는다.
"""
import os, sys, json, argparse

sys.path.insert(0, os.path.dirname(__file__))
from src.config import AppConfig
from src.orchestrator import SonarQubeOrchestrator


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config-remote.yml")
    ap.add_argument("--project-key", required=True)
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--types", default="BUG,VULNERABILITY")
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--review", action="store_true",
                    help="FP 1차 판정건을 judge가 사후 재검토(read-only)")
    ap.add_argument("--judge-type", default=None,
                    help="config의 judge_type 오버라이드 (''=fixer와 동일)")
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--out", default="/tmp/triage_result.json")
    args = ap.parse_args()

    cfg = AppConfig.load(args.config)
    if args.judge_type is not None:
        cfg.agent.judge_type = args.judge_type
    if args.judge_model is not None:
        cfg.agent.judge_model = args.judge_model
    orch = SonarQubeOrchestrator(cfg)
    wd = os.path.expanduser(args.project_dir)

    issues = orch._sonar.get_open_issues(
        args.project_key,
        issue_types=args.types.split(","),
        max_results=args.max,
    )
    mode = "triage+FP재검토(2패스)" if args.review else "단일 triage(1패스)"
    print(f"[triage] {args.project_key}: {len(issues)}개 이슈 ({args.types}) "
          f"— {mode}, judge={orch._judge.name()}", flush=True)

    rows = []
    for n, iss in enumerate(issues, 1):
        tr = orch._triage_issue(iss, wd)
        row = {
            "key": iss.key, "rule": iss.rule, "severity": iss.severity,
            "file": iss.file_path, "line": iss.line, "message": iss.message,
            "verdict1": tr.verdict, "confidence1": tr.confidence,
            "reason1": tr.reason,
            "verdict2": None, "confidence2": None, "reason2": None,
            "final": tr.verdict,
        }
        if args.review and tr.verdict == "FALSE_POSITIVE":
            src = orch._get_source_context(iss, wd)
            prompt = orch._judge.build_fp_review_prompt(
                issue_rule=iss.rule, issue_message=iss.message,
                file_path=iss.file_path, line=iss.line,
                source_context=src, claim_reason=tr.reason,
                rule_exceptions=orch._rule_doc(iss)["exceptions"],
            )
            rr = orch._review_outcome(
                prompt, iss, wd, ("AGREE_FALSE_POSITIVE", "DISAGREE"))
            row["verdict2"] = rr.verdict
            row["confidence2"] = rr.confidence
            row["reason2"] = rr.reason
            # 2차가 동의해야 FP 확정; DISAGREE/UNKNOWN이면 FP 기각(사람 검토)
            row["final"] = ("FALSE_POSITIVE"
                            if rr.verdict == "AGREE_FALSE_POSITIVE"
                            else "NEEDS_REVIEW")
        rows.append(row)
        extra = (f"  →2차 {row['verdict2']}" if row["verdict2"] else "")
        print(f"  [{n}/{len(issues)}] 1차 {tr.verdict:15}{extra}  "
              f"최종={row['final']:14} {iss.rule} "
              f"{iss.file_path.split('/')[-1]}:{iss.line}", flush=True)

    json.dump(rows, open(args.out, "w"), ensure_ascii=False, indent=2)
    fp = sum(1 for r in rows if r["final"] == "FALSE_POSITIVE")
    nr = sum(1 for r in rows if r["final"] == "NEEDS_REVIEW")
    tp = len(rows) - fp - nr
    print(f"\n[triage] 완료: TP={tp}  FP(확정)={fp}  NEEDS_REVIEW={nr}  "
          f"→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
