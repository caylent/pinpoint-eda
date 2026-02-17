# Pinpoint EDA - Migration Assessment CLI

Migration complexity assessment tool for **Amazon Pinpoint** end-of-support (October 30, 2026).

Scans all Pinpoint resources across regions and accounts, scores migration complexity, and generates a detailed report with migration target recommendations.

## Installation

```bash
# With uv (recommended)
uv tool install pinpoint-eda

# Or with pip
pip install pinpoint-eda
```

## Quick Start

```bash
# Interactive wizard (no args)
pinpoint-eda

# Direct scan with a profile
pinpoint-eda scan --profile my-profile

# Specific region
pinpoint-eda scan --profile my-profile --region us-east-1

# Multi-account (each profile is scanned separately)
pinpoint-eda scan --profile prod --profile staging

# Cross-account role assumption
pinpoint-eda scan --role-arn arn:aws:iam::123456789012:role/PinpointReadOnly

# Role assumption using a specific profile as the base session
pinpoint-eda scan --profile hub --role-arn arn:aws:iam::123456789012:role/PinpointReadOnly

# Dry run (discover apps without scanning)
pinpoint-eda scan --profile my-profile --dry-run
```

## Commands

| Command | Description |
|---------|-------------|
| `pinpoint-eda` | Interactive configurator wizard |
| `pinpoint-eda scan` | Run a migration assessment scan |
| `pinpoint-eda report <file>` | Re-render a JSON report |
| `pinpoint-eda export <file>` | Export JSON report to CSV files |
| `pinpoint-eda list-scanners` | Show available scanners |

## Scan Options

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` / `-p` | env/default | AWS profile (repeatable) |
| `--region` / `-r` | auto-discover | AWS region (repeatable) |
| `--role-arn` | none | IAM role ARN for cross-account (repeatable) |
| `--external-id` | none | External ID for role assumption |
| `--app-id` / `-a` | all | Specific app IDs (repeatable) |
| `--scanner` / `-s` | all | Specific scanners (repeatable) |
| `--max-workers` / `-w` | 5 | Parallel threads |
| `--kpi-days` | 90 | KPI history window |
| `--output` / `-o` | ./pinpoint-eda-output | Output directory |
| `--resume` | false | Resume interrupted scan |
| `--fresh` | false | Discard checkpoint |
| `--json-only` | false | No Rich output (for CI) |
| `--verbose` / `-v` | false | Debug logging |
| `--no-sms-voice-v2` | false | Skip SMS Voice V2 |
| `--dry-run` | false | Show what would be scanned without scanning |

## What It Scans

Per application:
- **Applications** - metadata, ARN, tags
- **Settings** - limits, quiet time, hooks
- **Channels** - Email, SMS, Voice, APNS, GCM, Baidu, ADM (9 types)
- **Segments** - with version counts and type classification
- **Campaigns** - with versions and state breakdown
- **Journeys** - with activities and execution metrics
- **Event Streams** - Kinesis configuration
- **Import/Export Jobs** - historical records
- **KPIs** - application/campaign/journey metrics

Account-level:
- **Templates** - Email, SMS, Push, In-App, Voice
- **Recommenders** - ML configurations
- **SMS Voice V2** - phone numbers, pools, sender IDs, registrations

## Complexity Scoring

The tool assigns a heuristic complexity score to each Pinpoint application to help prioritize migration planning. Scores are **relative estimates**, not precise time predictions -- they indicate which applications will require more effort compared to others.

| Resource | Points | How It's Calculated |
|----------|--------|---------------------|
| Journeys | varies | State (active=5, completed=3, draft=1) + activities + 2/branch + 3/integration |
| Campaigns | 3/active, 1/other | Active campaigns need careful cutover |
| Segments | 1 + 3/dynamic + 2/imported | Dynamic segments must be re-implemented in the target service |
| Active channels | 2 each | Per enabled channel type (Email, SMS, Push, etc.) |
| Push + campaigns | +5 | Push channels with active campaigns (no Connect outbound equivalent) |
| Event streams | 3-5 | 5 if app has recent activity, 3 otherwise |
| Campaign hooks | 5 | Lambda integration needs re-wiring |
| Import jobs | 2 | External data pipeline may need redirecting |
| Templates | 1 each, in-app=8 | In-app messaging templates have no AWS equivalent |
| Recommenders | 5 each | Custom ML integrations via Amazon Personalize |
| SMS/Voice V2 | 2/phone, 2/pool, 3/reg | Phone numbers, pools, and registrations |

**Levels:** LOW (0-9) | MEDIUM (10-29) | HIGH (30-69) | VERY HIGH (70+)

> **Important:** These scores are heuristic estimates to help prioritize migration planning. They are not a substitute for a detailed migration plan. Actual effort depends on your team's familiarity with the target AWS services (Amazon Connect, SES, SNS, etc.), the complexity of your business logic, and how tightly your applications are integrated with Pinpoint-specific features like journeys and in-app messaging. Use these scores as a starting point for conversation, not as a commitment.

## Features

- **Multi-region auto-discovery** - probes all Pinpoint regions in parallel
- **Multi-account** - scan multiple profiles or cross-account roles
- **Checkpoint/resume** - ctrl+c saves progress, `--resume` continues
- **Rate limiting** - token-bucket with exponential backoff
- **Rich progress display** - hierarchical progress bars, live stats
- **Migration mapping** - each resource type mapped to replacement AWS service

## Output

- `pinpoint-eda-output/pinpoint-eda-report.json` - full JSON report
- Rich console summary with complexity badges, scoring guide, tables, and migration tree

### CSV Export

```bash
# Export to CSV files (same directory as report)
pinpoint-eda export ./pinpoint-eda-output/pinpoint-eda-report.json

# Export to a specific directory
pinpoint-eda export ./pinpoint-eda-output/pinpoint-eda-report.json -o ./csv-reports
```

Produces three CSV files:
- **applications.csv** -- one row per app with complexity scores, levels, and migration notes
- **inventory.csv** -- one row per app+scanner with resource counts and flattened metadata
- **account_resources.csv** -- account-level resources (templates, recommenders, SMS/Voice V2) per region

## IAM Permissions

This tool is **read-only** -- it never creates, modifies, or deletes any AWS resources. It requires a minimal set of IAM permissions to scan Pinpoint resources across your account.

### Minimum IAM Policy

A ready-to-use IAM policy file is provided at [`iam-policy.json`](iam-policy.json). You can attach it as an inline policy or create a managed policy from it.

The policy includes three groups of permissions:

| Service | Actions | Purpose |
|---------|---------|---------|
| STS | `sts:GetCallerIdentity` | Resolve the AWS account ID |
| Pinpoint (`mobiletargeting`) | 31 read-only `Get*`/`List*` actions | Scan applications, channels, segments, campaigns, journeys, templates, KPIs, jobs, event streams, recommenders, and tags |
| Pinpoint SMS Voice V2 (`sms-voice`) | 7 `Describe*` actions | Scan phone numbers, pools, sender IDs, opt-out lists, registrations, configuration sets, and keywords |

<details>
<summary>Full inline policy JSON</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PinpointEDASTSIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    },
    {
      "Sid": "PinpointEDAReadOnly",
      "Effect": "Allow",
      "Action": [
        "mobiletargeting:GetApp",
        "mobiletargeting:GetApps",
        "mobiletargeting:GetApplicationSettings",
        "mobiletargeting:GetApplicationDateRangeKpi",
        "mobiletargeting:GetSegments",
        "mobiletargeting:GetSegmentVersions",
        "mobiletargeting:GetCampaigns",
        "mobiletargeting:GetCampaignVersions",
        "mobiletargeting:ListJourneys",
        "mobiletargeting:GetJourney",
        "mobiletargeting:GetJourneyExecutionMetrics",
        "mobiletargeting:GetEmailChannel",
        "mobiletargeting:GetSmsChannel",
        "mobiletargeting:GetVoiceChannel",
        "mobiletargeting:GetApnsChannel",
        "mobiletargeting:GetApnsSandboxChannel",
        "mobiletargeting:GetApnsVoipChannel",
        "mobiletargeting:GetApnsVoipSandboxChannel",
        "mobiletargeting:GetGcmChannel",
        "mobiletargeting:GetBaiduChannel",
        "mobiletargeting:GetAdmChannel",
        "mobiletargeting:ListTemplates",
        "mobiletargeting:GetEmailTemplate",
        "mobiletargeting:GetSmsTemplate",
        "mobiletargeting:GetPushTemplate",
        "mobiletargeting:GetInAppTemplate",
        "mobiletargeting:GetVoiceTemplate",
        "mobiletargeting:GetEventStream",
        "mobiletargeting:GetImportJobs",
        "mobiletargeting:GetExportJobs",
        "mobiletargeting:GetRecommenderConfigurations",
        "mobiletargeting:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PinpointEDASMSVoiceV2ReadOnly",
      "Effect": "Allow",
      "Action": [
        "sms-voice:DescribePhoneNumbers",
        "sms-voice:DescribePools",
        "sms-voice:DescribeSenderIds",
        "sms-voice:DescribeOptOutLists",
        "sms-voice:DescribeRegistrations",
        "sms-voice:DescribeConfigurationSets",
        "sms-voice:DescribeKeywords"
      ],
      "Resource": "*"
    }
  ]
}
```

</details>

> **Note:** `Resource: "*"` is required because Amazon Pinpoint does not support resource-level permissions for most read operations. If you skip the SMS Voice V2 scanner (`--no-sms-voice-v2`), you can omit the `PinpointEDASMSVoiceV2ReadOnly` statement.

### Cross-Account Scanning

To scan a different AWS account, create an IAM role in the target account with the policy above and a trust relationship that allows your source account to assume it.

#### 1. Create the role in the target account

Attach the [`iam-policy.json`](iam-policy.json) policy to a new IAM role (e.g., `PinpointEDAReadOnly`), then add this trust policy -- replace `111111111111` with your source account ID:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::111111111111:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "pinpoint-eda"
        }
      }
    }
  ]
}
```

> You can tighten the `Principal` to a specific user or role ARN instead of the account root.

#### 2. Grant `sts:AssumeRole` in the source account

The IAM identity running pinpoint-eda in the source account needs permission to assume the target role. Add this statement to your source account's policy:

```json
{
  "Sid": "AllowCrossAccountAssume",
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Resource": "arn:aws:iam::222222222222:role/PinpointEDAReadOnly"
}
```

#### 3. Run the scan

```bash
# Single cross-account target (assumes role using default credentials)
pinpoint-eda scan --role-arn arn:aws:iam::222222222222:role/PinpointEDAReadOnly

# With an external ID
pinpoint-eda scan \
  --role-arn arn:aws:iam::222222222222:role/PinpointEDAReadOnly \
  --external-id pinpoint-eda

# Use a specific profile as the base session for role assumption
pinpoint-eda scan \
  --profile hub-account \
  --role-arn arn:aws:iam::222222222222:role/PinpointEDAReadOnly

# Multiple cross-account targets via one base profile
pinpoint-eda scan \
  --profile hub-account \
  --role-arn arn:aws:iam::222222222222:role/PinpointEDAReadOnly \
  --role-arn arn:aws:iam::333333333333:role/PinpointEDAReadOnly
```

## Limitations

- **Read-only** -- this tool never creates, modifies, or deletes any AWS resources. It only reads resource metadata and metrics.
- **Scores are heuristic** -- complexity scores are rough estimates based on resource counts and types. They do not account for custom business logic, downstream integrations outside of AWS, or organizational factors like team size and experience.
- **No endpoint data** -- the tool does not scan individual endpoints (contacts/users). Endpoint counts can significantly affect migration timelines but are not included in the score.
- **Point-in-time snapshot** -- the report reflects the state of your Pinpoint resources at scan time. Resources may change between scanning and migration.
- **KPI data window** -- activity detection uses the `--kpi-days` window (default 90 days). An app with no recent activity may still have active downstream consumers.

## Development

```bash
# Clone and install
git clone https://github.com/caylent/pinpoint-eda.git
cd pinpoint-eda
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Run locally
uv run pinpoint-eda --version
```

## License

MIT
