# CRM Email Verifier Tool

This workspace also includes a production-ready Streamlit CRM-style Email Verifier Tool.

## Email Verifier Features

- Username/password login with PBKDF2-SHA256 password hashing.
- Protected dashboard so only logged-in users can upload and verify files.
- CSV and XLSX uploads.
- Flexible column detection for `Name`, `Company Name`, and `Email` using aliases such as `full_name`, `contact_name`, `company_name`, `organization`, `email_address`, and `work_email`.
- Email format validation with `email-validator`.
- DNS checks with `dnspython` for domain existence, MX, SPF, and DMARC.
- Safe handling for DNS timeout, NXDOMAIN, NoAnswer, nameserver, and generic DNS errors.
- LinkedIn Google search URL generation only. The app does not scrape LinkedIn.
- Verification scoring from 0 to 100 with human-readable notes.
- Downloadable CSV output with the requested CRM verification columns.

## Email Verifier Files

```text
app.py
verifier.py
utils.py
requirements.txt
README.md
```

## Email Verifier Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
streamlit run app.py
```

4. Log in with the local default credentials:

```text
Username: admin
Password: admin123
```

## Production Credentials

Before exposing the app to users, set these environment variables instead of using the local defaults:

```powershell
$env:EMAIL_VERIFIER_USERNAME = "your_admin_username"
$env:EMAIL_VERIFIER_PASSWORD_SALT = "replace-with-a-long-random-salt"
$env:EMAIL_VERIFIER_PASSWORD_HASH = "generated_pbkdf2_hash"
```

Generate a password hash with:

```bash
python -c "from utils import hash_password; print(hash_password('your-password', 'replace-with-a-long-random-salt'))"
```

## Email Verifier Input Format

Upload a CSV or XLSX file containing columns for name, company, and email. Accepted examples include:

- Name columns: `name`, `full_name`, `contact_name`
- Company columns: `company`, `company_name`, `organization`
- Email columns: `email`, `email_address`, `work_email`

## Email Verifier Output Columns

The downloaded CSV contains:

- `Name`
- `Company Name`
- `Email`
- `Domain`
- `MX Status`
- `SPF Status`
- `DMARC Status`
- `Email Format Valid/Invalid`
- `LinkedIn Search URL`
- `Verification Score`
- `Notes`

# SafeBooks Global AI Lead Generation + Sales Outreach Agent Automation

This package converts the SafeBooks Global lead-generation workflow into a reusable AI agent operating system.

## What this automation does

1. Researches SafeBooks Global positioning from official sites.
2. Finds public/permitted B2B leads from websites, directories, Google/company profiles, and permitted sales tools.
3. Cleans, deduplicates, verifies, and scores leads.
4. Produces CSV-ready lead sheets grouped by High / Medium / Low priority.
5. Generates personalized cold email, LinkedIn, call, discovery, objection-handling, and meeting-booking assets.
6. Maintains a campaign learning memory for scoring/source/template improvement.

## Official SafeBooks source summary

Official sites researched:

- https://safebooksglobal.com
- https://www.safebooksglobal.au

SafeBooks Global offers remote accounting and outsourcing support for CPAs, EAs, accountants, Australian CPA/accounting firms, bookkeepers, finance professionals, and businesses.

Verified service areas from public websites:

- Remote bookkeeping
- Tax preparation support
- Sales tax / SALT support
- Audit support
- Back-office support
- Bookkeeping and accounting
- AR/AP and software implementation/support
- Payroll and compliance
- Back-office taxation
- BAS & ATO support
- SMSF support
- FTE engagement model

Verified positioning / benefits from public websites:

- Scale accounting teams without hiring in-house.
- Trained accounting professionals aligned with U.S. standards.
- Support for CPAs, EAs, accountants, bookkeepers, CAs, and finance professionals.
- Reduced operating cost; U.S. site claims cost reduction up to 60%.
- Increased productivity and seasonal scalability.
- Work inside client systems, timelines, workflows, and SOPs.
- Tool familiarity: QuickBooks, Xero, Lacerte, MYOB, Sage, NetSuite, and other accounting platforms mentioned on the sites.
- Security claims include controlled/encrypted access, VPN-only access, role-based permissions, audit logs, daily backups, and secure file portals on the U.S. site; AU site states ISO 27001 certification.

Pricing / engagement style:

- Do not invent fixed prices.
- Use consultative phrasing: pricing depends on scope, service mix, volume, turnaround, software, and engagement model.
- AU site references full-time/hourly outsourcing and FTE engagement model.

## Folder contents

```text
SafeBooks_Global_AI_Agent_Automation/
  README.md
  prompts/
    SafeBooks_Global_Master_Agent_Prompt.md
    RUN_PROMPT.txt
  templates/
    lead_output_template.csv
    safebooks_agent_memory_template.json
    outreach_playbook.md
    scoring_rules.md
  scripts/
    score_and_clean_leads.py
    sample_input_leads.csv
  reports/
```

## Quick start

1. Put raw lead exports into a CSV using the template columns in `templates/lead_output_template.csv`.
2. Run the cleaner/scorer:

```bash
python scripts/score_and_clean_leads.py scripts/sample_input_leads.csv reports/sample_scored_leads.csv
```

3. Use `prompts/RUN_PROMPT.txt` to run a new AI lead campaign.
4. Use `prompts/SafeBooks_Global_Master_Agent_Prompt.md` as the master system/developer prompt for the lead-generation agent.

## Compliance guardrails

- Use public or permitted business data only.
- Do not bypass logins, paywalls, robots restrictions, or platform rules.
- Do not guess or fabricate emails, phone numbers, LinkedIn URLs, pricing, testimonials, or certifications.
- Do not automatically send bulk outreach unless SafeBooks has connected permitted sending tools and approved the campaign.
- Add opt-out language to cold email and respect unsubscribe/do-not-contact requests.
- Keep outreach professional, relevant, and low-pressure.

## All-in-one automatic lead generation

Use the new all-in-one launcher when you want leads generated automatically, not only scored from an existing CSV:

```bash
python safebooks_all_in_one_tool.py generate-leads
```

Windows double-click launcher:

```text
GENERATE_AUTOMATIC_LEADS.bat
```

Menu launcher:

```text
RUN_ALL_IN_ONE_TOOL.bat
```

Outputs are written under `reports/all_in_one_auto_generated_leads_*`.



## Latest automatic lead file

After `generate-leads` finishes, the newest generated leads are also copied here for easy access:

```text
LATEST_AUTOMATIC_LEADS.csv
LATEST_AUTOMATIC_LEADS_REPORT.md
```

The full timestamped report folder remains under `reports/all_in_one_auto_generated_leads_*`.


The command prints progress such as `Progress: checked 10/100 lead sources...`; keep the window open until it says `Automatic lead generation complete`.


## LinkedIn / Sales Navigator / Live AI setup

Connector status:

```bash
python safebooks_all_in_one_tool.py connectors
```

Edit local keys safely:

```text
EDIT_LIVE_KEYS.bat
```

NVIDIA live AI uses `.env.local` and the web dashboard `/api/agent` proxy. Do not put keys in `public/` files.

LinkedIn/Sales Navigator supported connection methods:

1. `csv_export` — recommended. Export permitted Sales Navigator lists manually, then run:
   ```bash
   python safebooks_all_in_one_tool.py sales-nav --input "C:\path\to\sn-leads.csv" --region auto
   ```
2. `official_api` — requires an approved LinkedIn developer app/access token.
3. `manual_review` — retain URLs and verify from official company websites/public snippets.

Auth-bypass LinkedIn/Sales Navigator scraping is not supported.

Full guide:

```text
CONNECT_LINKEDIN_SALES_NAVIGATOR.md
```
