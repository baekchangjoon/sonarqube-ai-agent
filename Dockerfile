# SonarQube AI Agent orchestrator — single-artifact distribution.
#
#   docker run --rm \
#     -v /var/run/docker.sock:/var/run/docker.sock \   # scanner/rebuild run via docker
#     -v "$PWD":/work -w /work \
#     -e SONAR_TOKEN -e CLAUDE_CODE_USE_BEDROCK=1 -e AWS_REGION \
#     ghcr.io/baekchangjoon/sonarqube-ai-agent \
#     --config config.yml pr-premerge --repo o/r --pr-number 42 --project-dir /work
#
# Bundled: orchestrator (Python), Claude Code CLI (node), docker CLI,
# gh CLI. LLM auth: ANTHROPIC_API_KEY or Bedrock (CLAUDE_CODE_USE_BEDROCK=1
# + AWS credentials); gh auth via GH_TOKEN.

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg git \
    && install -m 0755 -d /etc/apt/keyrings \
    # Node 20 (Claude Code CLI)
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    # docker CLI (scanner + rebuild containers via host socket)
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list \
    # gh CLI (PR comment / Fix PR delivery)
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] \
        https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs docker-ce-cli gh \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

COPY orchestrator /opt/sonarqube-ai-agent
RUN pip install --no-cache-dir /opt/sonarqube-ai-agent

WORKDIR /work
ENTRYPOINT ["sonar-ai-agent"]
CMD ["--help"]
