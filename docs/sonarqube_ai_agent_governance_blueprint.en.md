**[한국어](sonarqube_ai_agent_governance_blueprint.md)** | English

# SonarQube + AI Agent Governance Blueprint
## Enterprise-Grade Defect Resolution, Test Code Ownership & Operational Process

---

## 1. Executive Summary

This document defines the **Ownership, R&R, and Process** for AI-agent-driven defect resolution and test code generation when adopting SonarQube, grounded in industry De Facto Standards and Best Practices.

### Golden Rule

> **"The person who commits the code is fully responsible for that code — regardless of who (human/AI) authored it."**
> — Enterprise AI Coding Policy Template 2026, DORA 2025

This principle is the **industry standard (De Facto)**, and SonarSource, Google DORA, GitHub, and GitLab all take the same position.

---

## 2. Industry De Facto: SonarQube's "Clean as You Code" Policy

### 2.1 Core Concept

**Clean as You Code**, officially recommended by SonarQube, means the following:

| Category | Policy |
|------|------|
| **New Code** | Newly written or modified code must pass the Quality Gate |
| **Old Code** | No separate obligation to fix existing code. Improve only when touched as part of work |
| **Issue Assignment** | Automatically assigned to the last commit author of the line (issue author) |
| **Quality Gate** | Pass/Fail is judged based on new code only |

### 2.2 Why This Matters

- The **"burden of having to fix the entire legacy codebase"** that development teams worry about **does not occur**
- According to Sonar research, the cost of technical debt: **$306,000 per year per 1 million lines of code (approximately 5,500 developer-hours)**
- Clean as You Code is a strategy to incrementally improve overall quality **without a separate debt-resolution sprint**

### 2.3 Response to the Development Team's "Lack of Resources" Concern

```
Development team claim: "Cannot adopt SonarQube due to insufficient resources for defect resolution"

Counterargument (De Facto based):
1. Clean as You Code = no obligation to fix legacy code
2. New code only = minimal additional resources
3. AI Agent + Quality Gate = automation reduces developer burden
4. SonarLint IDE integration = real-time feedback at coding time (Shift-Left)
```

---

## 3. AI Agent Intervention Model: Industry Reference Architecture

### 3.1 SonarQube Official Remediation Agent Workflow

SonarQube itself released the **Remediation Agent** in 2025. This is the standard workflow recognized by the industry:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SonarQube Remediation Agent Flow              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Developer → Create PR (write new code)                       │
│                    │                                            │
│  2. SonarQube → Run PR analysis                                 │
│                    │                                            │
│  3. Detect Quality Gate violation issues                         │
│                    │                                            │
│  4. AI Agent → Generate automatic fix code                       │
│                    │                                            │
│  5. Sandbox → Re-verify fix code (check for newly introduced vulns)│
│                    │                                            │
│  6. AI Agent → Create Fix PR (submit to Developer)               │
│                    │                                            │
│  7. Developer → Review & Approve & Merge                        │
│         ▲                                                       │
│         │                                                       │
│    [Human-in-the-Loop: final responsibility always with Developer]│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Core Design Principle: "Architecture of Trust"

The **"Architecture of Trust"** pattern named by SonarSource:

1. **AI Suggests, and humans Decide**
2. **AI fixes are re-verified in the Sandbox before merge**
3. **They are automatically discarded if re-verification fails**
4. **A Developer-in-the-Loop is mandatory**

---

## 4. RACI Matrix: Clear Definition of Roles and Responsibilities

### 4.1 Overall RACI

| Activity | Dev Team (Dev) | Quality Team (QA/QE) | AI Agent | Notes |
|------|:---:|:---:|:---:|------|
| Write new code | **R/A** | I | - | Developer's core work |
| Configure SonarQube rules/profiles | C | **R/A** | - | Quality team manages standards |
| Establish Quality Gate criteria | C | **R/A** | - | Quality team is the gatekeeper |
| Fix new code defects | **R/A** | I | **R** | Dev has final responsibility, AI drafts |
| Fix legacy code defects | C | **A** | **R** | AI fixes, quality team manages |
| Review AI fix code | **R/A** | C | - | The committing Dev has full responsibility |
| Generate test code | **R/A** | C | **R** | AI drafts, Dev does final verification |
| Operate/manage AI Agent | C | **R/A** | - | Quality team operates the agent |
| Monitor AI Agent performance | I | **R/A** | - | Quality team measures effectiveness |
| Tune False Positives | C | **R/A** | - | Quality team manages noise |
| Integrate CI/CD pipeline | **R** | **A** | - | Dev implements, quality team verifies |

> **R** = Responsible (executes), **A** = Accountable (final responsibility), **C** = Consulted, **I** = Informed

### 4.2 Concrete Responsibilities by Role

#### Development Team
```
Responsibilities:
  ✓ Pass the Quality Gate for code they wrote/modified
  ✓ Review & approve fix code and test code generated by the AI Agent
  ✓ Final ownership of all committed code (Golden Rule)
  ✓ Real-time defect prevention at the IDE stage via SonarLint

Exemptions:
  ✗ No obligation to fix the entire legacy codebase
  ✗ No obligation to operate/manage the AI Agent
  ✗ No obligation to configure SonarQube rules
```

#### Quality/QE Team
```
Responsibilities:
  ✓ Configure/maintain SonarQube Quality Profiles and Quality Gates
  ✓ Operate, monitor, and measure the performance of the AI Agent
  ✓ Manage False Positives and tune rules
  ✓ Manage the legacy code technical-debt resolution roadmap (using the AI Agent)
  ✓ Operate and report the quality-metrics dashboard

Exemptions:
  ✗ No final responsibility for defects in code committed by developers
  ✗ No direct modification of production code
```

#### AI Agent
```
Role:
  ✓ Generate draft fix code for SonarQube issues
  ✓ Generate draft test code
  ✓ Self-verify within the Sandbox (re-analysis)
  ✓ Automatically create Fix PRs

Restrictions:
  ✗ No direct merge authority (Human Review always required)
  ✗ No authority to change Quality Gate criteria
  ✗ Cannot push directly to the production branch
```

---

## 5. Operational Process: AI Agent Intervention Points and Workflow

### 5.1 Dual-Track Process

The industry Best Practice is a dual-track operation that separates **new code** and **legacy code**:

```
═══════════════════════════════════════════════════════════════════
  Track 1: New Code (Clean as You Code)
  Owner: Dev Team | AI intervention: automatic at PR time | Cadence: every PR
═══════════════════════════════════════════════════════════════════

  Developer                    AI Agent              SonarQube
     │                            │                      │
     ├── Write code ──────────────┤                      │
     │   (SonarLint real-time check)│                    │
     │                            │                      │
     ├── Create PR ───────────────┼──── Request analysis ─→│
     │                            │                      │
     │                            │←── Detect issues ────┤
     │                            │                      │
     │                            ├── Generate fix code   │
     │                            ├── Sandbox verify      │
     │                            ├── Create Fix PR       │
     │                            │                      │
     │←── Deliver Fix PR ─────────┤                      │
     │                            │                      │
     ├── Review & Approve (or reject)│                   │
     ├── Merge ───────────────────┤                      │
     │                            │                      │
  [Final ownership: Developer]    │                      │

═══════════════════════════════════════════════════════════════════
  Track 2: Legacy Code (Technical Debt Reduction)
  Owner: Quality Team | AI intervention: batch schedule | Cadence: per sprint
═══════════════════════════════════════════════════════════════════

  Quality Team                 AI Agent              SonarQube
     │                            │                      │
     ├── Prioritize technical debt ┤                     │
     │   (Severity: Critical/     │                      │
     │    Blocker first)          │                      │
     │                            │                      │
     ├── Batch-assign to AI Agent ─→│                    │
     │                            │                      │
     │                            ├── Generate fix code   │
     │                            ├── Generate test code  │
     │                            ├── Sandbox verify      │
     │                            ├── Create Fix PR       │
     │                            │                      │
     │←── Deliver Fix PR ─────────┤                      │
     │                            │                      │
     ├── Request review → Dev Team ┤                     │
     │                            │                      │
  [Dev team reviews & merges]     │                      │
  [Final ownership: the Developer who merged]│           │
```

### 5.2 AI Agent Intervention Points in Detail

| Stage | Timing | Trigger | AI Action | Human Action |
|------|------|--------|---------|------------|
| **Pre-commit** | While coding | SonarLint warning | Real-time fix suggestions in the IDE | Developer applies immediately |
| **PR creation** | At PR open | SonarQube PR analysis | Auto-create fix PR for Quality Gate violation issues | Developer reviews then merges |
| **Post-merge** | After merge | Branch analysis | Detect missed issues and create follow-up PR | Developer reviews then merges |
| **Scheduled Batch** | Periodic | Schedule (weekly) | Batch-fix legacy code technical debt | Quality team manages, dev team reviews |

### 5.3 Quality Gate Configuration Criteria (De Facto Standard)

```
Quality Gate: "Sonar Way" (default) + recommended reinforcements

New code criteria:
  ┌──────────────────────────────────┬───────────────┐
  │ Metric                           │ Threshold     │
  ├──────────────────────────────────┼───────────────┤
  │ New Bugs                         │ 0             │
  │ New Vulnerabilities              │ 0             │
  │ New Security Hotspots Reviewed   │ 100%          │
  │ New Code Coverage                │ ≥ 80%         │
  │ New Duplicated Lines             │ ≤ 3%          │
  │ Reliability Rating               │ A             │
  │ Security Rating                  │ A             │
  │ Maintainability Rating           │ A             │
  └──────────────────────────────────┴───────────────┘

AI-generated code reinforced criteria (recommended):
  ┌──────────────────────────────────┬───────────────┐
  │ PR with AI code ratio > 60%      │ Senior review │
  │ AI-generated code coverage       │ ≥ 90%         │
  │ AI code security scan            │ Mandatory     │
  └──────────────────────────────────┴───────────────┘
```

---

## 6. Ownership Model: "Committer Responsibility Principle" in Detail

### 6.1 Industry Consensus (2025-2026 De Facto)

```
┌─────────────────────────────────────────────────────────────┐
│                   Code Ownership Model                       │
│                                                             │
│   ┌─────────┐  generate  ┌──────────┐                       │
│   │AI Agent │──────────→│ Fix Code │                        │
│   └─────────┘           └────┬─────┘                        │
│                              │                              │
│                       Review & Approve                       │
│                              │                              │
│                              ▼                              │
│   ┌──────────┐   commit   ┌──────────┐                      │
│   │Developer │←─────────│ Approved │                        │
│   └────┬─────┘          └──────────┘                        │
│        │                                                    │
│        ▼                                                    │
│   ┌──────────────────────────────────┐                      │
│   │  From the moment of commit,        │                      │
│   │  full ownership of that code       │                      │
│   │  belongs to the Developer          │                      │
│   │                                   │                      │
│   │  → On a bug: Developer responsible │                      │
│   │  → Maintenance: Developer          │                      │
│   │  → Security issues: Developer      │                      │
│   └──────────────────────────────────┘                      │
│                                                             │
│   Basis: Enterprise AI Coding Policy 2026                    │
│         "The Golden Rule — the developer who commits         │
│          is fully responsible for its logic,                 │
│          regardless of authorship."                          │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Ownership Transition Flow

| Stage | Code State | Ownership | Legal/Organizational Responsibility |
|------|-----------|--------|------------------|
| Right after AI generation | Draft | None (tool output) | None |
| Passed Sandbox verification | Verified suggestion | AI Agent (quality team managed) | Quality team operational responsibility |
| Fix PR created | Awaiting review | Undetermined | None |
| Developer review approved | Approved | **Developer** | Developer |
| Merge & commit | Production code | **Developer (fully attributed)** | Developer |

---

## 7. DORA 2025 Research Basis: AI is an Amplifier

### 7.1 Key Findings

The key conclusion of the Google DORA 2025 report:

> **"AI amplifies an organization's existing strengths and weaknesses."**

- Organizations with a strong testing culture → AI acts as a **powerful collaborator**
- Organizations with a weak testing culture → AI **generates technical debt even faster**

### 7.2 Implications

```
┌─────────────────────────────────────────────────────────┐
│  Prerequisites that must precede AI Agent adoption:      │
│                                                         │
│  1. Automated test pipeline (test stage within CI/CD)   │
│  2. Clear Quality Gate criteria established              │
│  3. An established code-review culture                  │
│  4. RACI-based role/responsibility agreement            │
│                                                         │
│  Adopting only the AI Agent without these conditions:    │
│  → becomes "a tool that produces technical debt faster" │
└─────────────────────────────────────────────────────────┘
```

### 7.3 Optimistic / Pessimistic Scenarios

#### Optimistic Scenario (Well-Governed)
- AI Agent reduces defect-resolution time by **60-70%**
- Test coverage rapidly improves from **30% → 80%**
- Development team achieves **90%+** Quality Gate pass rate
- Legacy technical debt gradually decreases by **20-30% per year**

#### Pessimistic Scenario (Poorly-Governed)
- **45% of AI-generated code falls short of security standards** (2026 industry statistic)
- Developers uncritically accept AI code → introducing new types of defects
- Unclear ownership → responsibility avoidance when defects occur ("but it's AI-generated code")
- Alert Fatigue: lack of False Positive management → team indifference within weeks

---

## 8. Phased Adoption Roadmap

### Phase 1: Foundation (1-2 months)

```
Goal: Reach consensus and build infrastructure

 Week 1-2: Stakeholder workshop
   ├── R&R agreement based on this RACI matrix
   ├── Quality Gate criteria agreement
   └── Share Clean as You Code policy → resolve dev team concerns

 Week 3-4: Technical infrastructure
   ├── Build SonarQube server (integrate with existing CI/CD)
   ├── Deploy SonarLint IDE plugin to everyone
   └── Initial Quality Profile setup (based on Sonar Way)

 Week 5-8: Pilot
   ├── Select 1-2 pilot projects
   ├── Quality Gate: Warning Only mode (no blocking)
   └── Measure metric baseline
```

### Phase 2: AI Agent Integration (2-3 months)

```
Goal: Adopt AI Agent and automate Track 1 (new code)

 Month 3: AI Agent development/adoption
   ├── SonarQube API integration
   ├── Build Fix PR auto-generation pipeline
   └── Configure Sandbox verification environment

 Month 4: Activate Track 1
   ├── Run PR analysis → AI auto-fix suggestion pipeline
   ├── Quality Gate: switch to Enforced mode (PR blocking)
   └── Collect dev team feedback & tune

 Month 5: Expansion
   ├── Expand Track 1 to all projects
   └── Stabilize False Positive tuning
```

### Phase 3: Full Operation (3-6 months)

```
Goal: Full operation including Track 2 (legacy)

 Month 6-8: Activate Track 2
   ├── Prioritize legacy code technical debt
   ├── Begin AI Agent batch fixes (Critical/Blocker first)
   └── Run quality-team-led legacy debt reduction roadmap

 Month 9-12: Optimization
   ├── Measure AI Agent effectiveness based on metrics
   ├── Integrate DORA metrics (deployment frequency, change failure rate, etc.)
   └── Establish a process-improvement cycle
```

---

## 9. Official Responses to Each Stakeholder's Concerns

### 9.1 Dev Team: "Cannot adopt SonarQube due to lack of resources"

| Concern | Response | Basis |
|------|------|------|
| Need to fix all legacy? | **No.** Clean as You Code = new code only | SonarSource official policy |
| Additional workload? | **Minimal.** AI Agent creates Fix PRs, developers only review | SonarQube Remediation Agent |
| Who writes test code? | **AI Agent generates drafts** → developer verifies | Industry Best Practice |
| Need to change IDE? | Just install SonarLint (takes 2 minutes) | Keep existing IDE |

### 9.2 Quality Team: "Need clarity on R&R, ownership, and process"

| Concern | Response | Basis |
|------|------|------|
| Who uses the AI Agent? | **Track 1:** automatic (at PR time), **Track 2:** quality-team-led | RACI in this document |
| AI code ownership? | **Fully attributed to the committing Developer** (Golden Rule) | Enterprise AI Policy 2026 |
| AI intervention points? | **4 stages:** Pre-commit, PR, Post-merge, Batch | Section 5.2 of this document |
| Quality team's role? | **Gate Keeper + Agent Operator + Metrics Owner** | RACI in this document |

---

## 10. References

1. **SonarSource** — "Clean as You Code" (https://docs.sonarsource.com/sonarqube-server/latest/core-concepts/clean-as-you-code/introduction/)
2. **SonarSource** — "SonarQube Remediation Agent" (https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/with-ai-features/sonarqube-remediation-agent)
3. **SonarSource** — "AI CodeFix" (https://docs.sonarsource.com/sonarqube-server/2025.1/ai-capabilities/ai-fix-suggestions)
4. **Google DORA 2025** — "State of AI-assisted Software Development" (https://dora.dev/research/2025/dora-report/)
5. **DORA 2025** — "Balancing AI Tensions" (https://dora.dev/insights/balancing-ai-tensions/)
6. **Enterprise AI Coding Policy Template 2026** (https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html)
7. **Sonar Research** — "Cost of Technical Debt" (https://www.sonarsource.com/blog/new-research-from-sonar-on-cost-of-technical-debt)
8. **Enterprise AI Governance Framework** (https://blog.exceeds.ai/enterprise-ai-code-governance-framework)
9. **Augment Code** — "Static Code Analysis Best Practices" (https://www.augmentcode.com/guides/static-code-analysis-best-practices-enterprise)
10. **SonarSource** — "Claude Code + SonarQube MCP" (https://www.sonarsource.com/blog/claude-code-sonarqube-mcp-building-an-autonomous-code-review-workflow/)

---

*Document Version: 1.0 | Created: 2026-03-21 | Classification: Internal*
