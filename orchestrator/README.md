# sonarqube-ai-agent (orchestrator)

LLM-agnostic orchestrator that auto-fixes SonarQube issues and triages
false positives.

This is the installable Python package. For full documentation —
operating modes, the false-positive assessment strategies (C/D/E),
configuration reference, and benchmarks — see the repository README:

- English: https://github.com/baekchangjoon/sonarqube-ai-agent/blob/main/README.en.md
- 한국어: https://github.com/baekchangjoon/sonarqube-ai-agent/blob/main/README.md

## Install

```bash
pipx install "git+https://github.com/baekchangjoon/sonarqube-ai-agent.git#subdirectory=orchestrator"
# or, from a checkout:
pip install -e ./orchestrator
```

## Usage

```bash
sonar-ai-agent --config config.yml pr-premerge \
  --repo owner/repo --pr-number 42 --project-dir . --cleanup
```
