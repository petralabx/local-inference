---
name: brief-to-quote
description: >-
  Turn a customer or product brief into a costed price quote plus a shareable
  report and presentation for PLX contract manufacturing. Use when a customer
  brief, formula/SKU list, or a "what would this cost", "what's the KG price",
  "is $X per unit achievable", or "price these at these volumes" request comes
  in. Covers brief intake, pulling REAL PLX raw-material costs from the database,
  market research for catalog gaps, building the bulk $/kg + per-unit cost model
  (fill, waste factor, labour/overhead, margin), back-solving price/margin and
  reformulations, and producing an interactive canvas + PDF/Word report shared to
  OneDrive. Pairs with the report-export skill.
---

# Brief → Quote

Convert a brief into a defensible, costed quote grounded in **real PLX costs**,
then package it as an interactive canvas + a shareable PDF/Word report. Costs
come from the database, never guessed; gaps are filled with cited market
research; every price is a transparent build-up the operator can flex.

## When to use

- A customer/brand brief arrives with products, SKUs, formulas (with active %),
  fill sizes, volumes, and/or a target unit price.
- "What's the KG price?" · "Can we hit $X/unit?" · "Price these at 5k/10k/20k."
- A reformulation-to-a-price-target or two-tier (value vs premium) pricing ask.

## When NOT to use

- A firm, contractual quote (this produces *indicative* pricing; firm quotes
  need locked formulas, confirmed pack specs, and supplier re-quotes at volume).
- Pure data lookups with no costing (query the DB directly).

## Workflow

```text
Brief → Quote Progress
- [ ] 0) Frame: deliverables + report-only vs produce; confirm target price & currency
- [ ] 1) Intake: parse products, SKUs, formulas (active %), fill size, who supplies packaging, volumes, target
- [ ] 2) Real costs: pull PLX raw-material costs from the DB (see "Pull real costs")
- [ ] 3) Gaps: market-research materials not in the catalog (cite sources)
- [ ] 4) Model: bulk $/kg → per-unit cost (fill, waste, labour/OH, packaging, margin)
- [ ] 5) Analyze: KG-cost ceiling for the target, reformulations, volume tiers
- [ ] 6) Deliver: interactive canvas (price ladder) + PDF/Word via report-export + share
- [ ] 7) Handoff: assumptions, currency note, residual risks, what to confirm
```

### 1) Intake — what to extract from the brief

Products & SKUs; per-SKU **formula with active %** (and grade, e.g. Sytenol® A vs
generic); **fill size** (mL/oz → kg via density); **who supplies packaging** (PLX
vs customer — this dominates the unit cost); **volume tiers**; **target unit price
+ currency**. Flag anything missing (it's a cost lever).

**Detect the brief type.** A *commercial* brief has SKUs, volumes, a target price,
and packaging terms → produce the full price ladder. A *formula sheet / bespoke*
brief (one product with a full %-w/w formula but no volumes/target/fill — common
for R&D) → still deliver **bulk $/kg + cost drivers**, then request the commercial
inputs; skip the value/enhanced/full ladder and price cost-plus once fill + volume
are known. **Density by type:** oils ~0.91, water-based emulsions/gels ~1.0 g/mL.
**QC:** confirm the formula sums to ~100% w/w and treat `q.s.` lines as a small
nominal allowance.

### 2) Pull real costs (PLX database)

The cost basis is `Product.unitCost` ($/kg) for `RAW_MATERIAL` items, plus
`SupplierProduct.systemCost`/`currency` and the `RateSettings` rates. Do not use
FM lowercase tables. Set up the connection, then run the puller:

```powershell
# Windows — load secrets and resolve the staging/UAT DB password from AWS Secrets Manager
. $HOME/.secrets-env.staging.ps1
$aws="C:\Program Files\Amazon\AWSCLIV2\aws.exe"; $h="plx-postgres-staging.c2b8m8isksqt.us-east-1.rds.amazonaws.com"; $sid="plx/staging/postgres/admin"
$raw = & $aws secretsmanager get-secret-value --region us-east-1 --secret-id $sid --query SecretString --output text 2>$null
if (-not $raw) { $sid="plx/uat/postgres/admin"; $h="plx-postgres-uat.c2b8m8isksqt.us-east-1.rds.amazonaws.com"; $raw = & $aws secretsmanager get-secret-value --region us-east-1 --secret-id $sid --query SecretString --output text 2>$null }
$sec=$raw|ConvertFrom-Json; $pw=$sec.password; $enc=[uri]::EscapeDataString([string]$pw)
$env:DATABASE_URL = "postgresql://plxadmin:$enc@${h}:5432/plxportal?sslmode=require"
# Copy the puller into portal/tmp so node deps resolve, then run from portal/
Copy-Item ".cursor/skills/brief-to-quote/scripts/pull-raw-costs.ts" portal/tmp/ -Force
cd portal; npx tsx tmp/pull-raw-costs.ts "squalane,jojoba,rosehip,grapeseed,argan,marula,bakuchiol,tetrahexyldecyl,tocopherol,caffeine,mica,fragrance"
```

Pass the brief's materials as a comma-separated list — **use INCI names, not just
trade names** (briefs usually list INCI; the puller matches `name` OR `inci_name`).
Trade/common names miss items stored by INCI: e.g. `grapeseed` returns 0 but
`vitis vinifera` finds it (`R-0494`). The script writes full detail to
`raw-costs.json` and prints a compact per-term summary (count, min/median,
cheapest match + currency) plus the `RateSettings`. Budget **one** DB pass.
Staging has the freshest FM-synced costs; UAT is the fallback. `count: 0` = not
in catalog → market-research it (phase 3).

### 3) Market research for gaps

For materials NOT in the catalog (count = 0), get a current bulk `$/kg` via web
search (cosmetic-grade, volume pricing) and **cite it**. Also fetch the current
**USD/CAD FX** rate. See `reference.md` for the materials that were missing
before (e.g. grapeseed, marula, guarana) and typical ranges.

### 4) Build the cost model

Full formulas in [reference.md](reference.md). Essentials:

- `bulk cost $/kg = Σ(pct/100 × material $/kg)`, then `× (1 + wasteFactor)`.
- **Bulk price is ALWAYS quoted per KG.** `bulk price $/kg = bulk cost $/kg / (1 − margin)`.
  Always produce this KG price — it is the canonical PLX bulk quote (the price for
  the compounded formula by the kilogram, before any fill/packaging). Report it for
  every quote, even when a finished per-unit price is also requested.
- **Finished unit** (only when filling/packaging applies):
  `unit cost = bulk cost $/kg × fill_kg + conversion + (packaging PLX supplies)`;
  `unit price = unit cost / (1 − margin)`.
- `conversion/unit` from real line economics:
  `(operators×paidHrs×wage + OH/hr×paidHrs) / (units_per_min×60×uptime_hrs) + box`.
  Fall back to `RateSettings` rates when line economics are unknown.
- default margin 30% (`RateSettings` has no margin field).
- **Currency:** model in CAD (PLX base); convert USD-sourced lines at FX; present
  the price in the brief's currency. `Product.unitCost` mixes CAD/USD per supplier —
  treat ambiguous lines conservatively and say so.

### 5) Analyze

- **KG-cost ceiling** to hit the target: `max bulk $/kg = ((target × (1−margin)) − conversion) / (1+waste) / fill`.
- **Reformulations**: cut/reduce expensive actives, lower premium-oil %, raise the
  cheap base; recompute. Offer a **value / enhanced / full** tier ladder.
- **Volume tiers**: conversion drops with volume (setup/changeover amortization).

### 6) Deliver

- **Interactive canvas** (`.canvas.tsx`) — the price-ladder pattern (per-SKU
  Value/Enhanced/Full with live sliders for fill, waste, FX, line rate, margin,
  target). Read the `canvas` skill; pattern + columns in `reference.md`.
- **PDF + Word report** — author a clean HTML/Markdown report and run the
  **report-export** skill (`report-export/scripts/export-report.ps1 -InputPath … -Share`).
- **Share to cloud** so it's available immediately (no OneDrive sync lag):
  `scripts/upload-to-cursorinbox.ps1 -Files <pdf>,<html> -Folder <name>`.

### 7) Handoff

State: cost basis (DB + market), assumptions (fill weight, waste %, line rates),
the currency/FX note, residual risks, and exactly what the operator must confirm
for a firm quote.

## Guardrails

- Indicative pricing, not a binding quote — label reports "Confidential — Indicative".
- Use Prisma tables only (`app_product`, `app_supplier_product`, `app_rate_settings`);
  never query FM lowercase tables.
- Respect the staging-only DB policy; both `plx-postgres-staging` and `-uat` are readable.

## Resources

- Cost model, DB recipe, currency handling, reformulation + canvas/report patterns,
  and the PRESSE worked example: [reference.md](reference.md)
- Cost puller: [scripts/pull-raw-costs.ts](scripts/pull-raw-costs.ts)
- Cloud share helper: [scripts/upload-to-cursorinbox.ps1](scripts/upload-to-cursorinbox.ps1)
- Export to PDF/Word: the `report-export` skill. Presentation: the `canvas` skill.
