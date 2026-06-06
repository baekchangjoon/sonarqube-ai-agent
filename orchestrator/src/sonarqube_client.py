import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

import requests

from src.config import SonarQubeConfig

logger = logging.getLogger(__name__)


@dataclass
class SonarIssue:
    key: str
    rule: str
    severity: str
    component: str
    line: int
    message: str
    issue_type: str
    effort: str = ""
    file_path: str = ""

    @staticmethod
    def from_api(data: dict) -> "SonarIssue":
        component = data.get("component", "")
        file_path = component.split(":")[-1] if ":" in component else component
        return SonarIssue(
            key=data.get("key", ""),
            rule=data.get("rule", ""),
            severity=data.get("severity", ""),
            component=component,
            line=data.get("line", 0),
            message=data.get("message", ""),
            issue_type=data.get("type", ""),
            effort=data.get("effort", ""),
            file_path=file_path,
        )


class SonarQubeClient:
    """SonarQube Community Edition REST API client."""

    def __init__(self, config: SonarQubeConfig):
        self._url = config.url.rstrip("/")
        self._token = config.token
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
        })

    def is_healthy(self) -> bool:
        try:
            resp = self._get("/api/system/status")
            return resp.get("status") == "UP"
        except Exception:
            return False

    # ── Project Management ───────────────────

    def create_project(self, project_key: str,
                       project_name: str) -> bool:
        try:
            self._post("/api/projects/create", data={
                "project": project_key,
                "name": project_name,
            })
            logger.info("Created project: %s", project_key)
            return True
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                logger.info("Project already exists: %s", project_key)
                return True
            raise

    def delete_project(self, project_key: str) -> bool:
        try:
            self._post("/api/projects/delete", data={
                "project": project_key,
            })
            logger.info("Deleted project: %s", project_key)
            return True
        except requests.HTTPError:
            logger.warning("Failed to delete project: %s", project_key)
            return False

    def project_exists(self, project_key: str) -> bool:
        resp = self._get("/api/projects/search", params={
            "projects": project_key,
        })
        components = resp.get("components", [])
        return any(c.get("key") == project_key for c in components)

    # ── Issue Retrieval ──────────────────────

    def get_open_issues(self, project_key: str,
                        issue_types: Optional[list] = None,
                        severities: Optional[list] = None,
                        max_results: int = 100,
                        pull_request: Optional[str] = None) -> list[SonarIssue]:
        params = {
            "componentKeys": project_key,
            "statuses": "OPEN,CONFIRMED",
            "ps": min(max_results, 500),
        }
        if issue_types:
            params["types"] = ",".join(issue_types)
        if severities:
            params["severities"] = ",".join(severities)
        if pull_request:
            params["pullRequest"] = pull_request

        resp = self._get("/api/issues/search", params=params)
        raw_issues = resp.get("issues", [])
        return [SonarIssue.from_api(i) for i in raw_issues]

    def get_new_issues(self, project_key: str,
                       max_results: int = 100) -> list[SonarIssue]:
        params = {
            "componentKeys": project_key,
            "statuses": "OPEN,CONFIRMED",
            "sinceLeakPeriod": "true",
            "ps": min(max_results, 500),
        }
        resp = self._get("/api/issues/search", params=params)
        return [SonarIssue.from_api(i) for i in resp.get("issues", [])]

    def get_issue_count(self, project_key: str) -> int:
        resp = self._get("/api/issues/search", params={
            "componentKeys": project_key,
            "statuses": "OPEN,CONFIRMED",
            "ps": 1,
        })
        return resp.get("total", 0)

    # ── Quality Gate ─────────────────────────

    def get_quality_gate_status(self, project_key: str,
                                pull_request: Optional[str] = None) -> str:
        params = {"projectKey": project_key}
        if pull_request:
            params["pullRequest"] = pull_request
        resp = self._get("/api/qualitygates/project_status", params=params)
        return resp.get("projectStatus", {}).get("status", "UNKNOWN")

    # ── Measures ─────────────────────────────

    def get_measures(self, project_key: str) -> dict:
        metrics = (
            "bugs,vulnerabilities,code_smells,coverage,"
            "duplicated_lines_density,ncloc"
        )
        resp = self._get("/api/measures/component", params={
            "component": project_key,
            "metricKeys": metrics,
        })
        measures = resp.get("component", {}).get("measures", [])
        return {m["metric"]: m.get("value", "0") for m in measures}

    # ── Source Code ──────────────────────────

    def get_source_lines(self, component_key: str,
                         from_line: int, to_line: int) -> list[str]:
        try:
            resp = self._get("/api/sources/raw", params={
                "key": component_key,
            })
            if isinstance(resp, str):
                lines = resp.splitlines()
                start = max(0, from_line - 1)
                end = min(len(lines), to_line)
                return lines[start:end]
        except Exception:
            logger.warning("Failed to fetch source: %s", component_key)
        return []

    # ── Scanner Execution ────────────────────

    @staticmethod
    def run_scanner(project_dir: str, project_key: str,
                    sonar_url: str, sonar_token: str,
                    project_name: Optional[str] = None,
                    extra_args: Optional[list] = None) -> bool:
        cmd = _build_scanner_cmd(
            project_dir, project_key, sonar_url, sonar_token,
            project_name, extra_args,
        )
        logger.info("Running sonar-scanner for %s", project_key)
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("Scanner failed: %s", result.stderr[-500:])
            return False
        logger.info("Scanner completed for %s", project_key)
        return True

    # ── Private HTTP Methods ─────────────────

    def _get(self, path: str, params: dict = None):
        url = f"{self._url}{path}"
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return resp.text

    def _post(self, path: str, data: dict = None):
        url = f"{self._url}{path}"
        resp = self._session.post(url, data=data, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return resp.text


def _build_scanner_cmd(project_dir: str, project_key: str,
                       sonar_url: str, sonar_token: str,
                       project_name: str = None,
                       extra_args: list = None) -> list[str]:
    cmd = [
        "docker", "run", "--rm",
        "-e", f"SONAR_HOST_URL={_docker_reachable_url(sonar_url)}",
        "-e", f"SONAR_TOKEN={sonar_token}",
        "-v", f"{project_dir}:/usr/src",
        "sonarsource/sonar-scanner-cli",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectName={project_name or project_key}",
        "-Dsonar.sources=src/main/java",
        "-Dsonar.tests=src/test/java",
        "-Dsonar.java.binaries=target/classes",
        "-Dsonar.java.test.binaries=target/test-classes",
        "-Dsonar.java.libraries=",
        "-Dsonar.coverage.jacoco.xmlReportPaths="
        "target/site/jacoco/jacoco.xml",
        "-Dsonar.sourceEncoding=UTF-8",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _docker_reachable_url(sonar_url: str) -> str:
    """Map localhost URLs to an address reachable from inside the
    scanner container; pass remote URLs through unchanged."""
    if "localhost" not in sonar_url and "127.0.0.1" not in sonar_url:
        return sonar_url
    import platform
    host = ("host.docker.internal" if platform.system() == "Darwin"
            else "172.17.0.1")
    return (sonar_url.replace("localhost", host)
            .replace("127.0.0.1", host))
