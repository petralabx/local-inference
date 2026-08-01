# Brief → Quote — Reference

Detailed methodology behind `SKILL.md`. Read the section you need.

## Cost model (the math)

All in one place. Work in **CAD** (PLX base), present in the brief's currency.

| Symbol | Meaning | Source |
|---|---|---|
| `m_i` | material i cost ($/kg) | `Product.unitCost` (DB) or market |
| `p_i` | material i % in formula | brief |
| `waste` | raw-material adjustment / waste factor | `RateSettings.rawMaterialsAdjustmentRate` (default 10%; PLX has used 5%) |
| `fill` | product fill weight (kg) | brief (mL → kg via density; oils ≈ 0.91 g/mL) |
| `conv` | conversion cost/unit (labour + OH + PLX-supplied packaging) | line economics or `RateSettings` |
| `margin` | gross margin | default 0.30 (no `RateSettings` margin field) |
| `FX` | CAD per USD | web search (was ~1.42) |

```
bulk_per_kg       = Σ(p_i/100 × m_i)
bulk_per_kg_adj   = bulk_per_kg × (1 + waste)
bulk_price_per_kg = bulk_per_kg_adj / (1 − margin)   # ALWAYS quote this — PLX prices bulk by the kg
unit_cost         = bulk_per_kg_adj × fill + conv + packaging_PLX
unit_price        = unit_cost / (1 − margin)
margin_at(P)      = (P − unit_cost) / P
max_bulk_per_kg   = ((target × (1 − margin)) − conv) / (1 + waste) / fill   # KG ceiling
```

**Bulk price = the KG price.** PLX always quotes bulk by the kilogram, so
`bulk_price_per_kg` is a first-class deliverable on every quote — it's the price
of the compounded formula per kg (drums/totes), independent of fill or packaging.
A finished per-unit price is the bulk cost carried at `fill` kg plus conversion and
packaging; the bulk KG price stands on its own when the customer buys bulk.

### Conversion cost from real line economics

```
units_per_shift = units_per_min × 60 × uptime_hrs
labour_per_unit = (operators × paid_hrs × wage) / units_per_shift
oh_per_unit     = (oh_per_hr × paid_hrs) / units_per_shift     # OH over the full paid shift = conservative
conv            = labour_per_unit + oh_per_unit + master_box_per_unit
```

If line economics are unknown, fall back to `RateSettings`
(`batchingQuotingLaborRate`, `assemblyQuotingLaborRate`, `overheadPerProductionHour`)
and state the assumption. Small/changeover-heavy runs raise `conv`; high-volume
single-SKU runs approach the steady-state above.

### Currency handling (important)

`Product.unitCost` mirrors each item's primary-supplier number **without
normalizing currency** — it is a mix of CAD and USD. For a firm quote, normalize
each line using `SupplierProduct.currency`. For an indicative quote, treat
ambiguous lines conservatively (e.g. as USD if pricing in USD, or convert
CAD-native lines at FX) and say so. Convert the final cost to the target
currency: `cost_target = cost_CAD / FX` for USD.

## Database recipe

- **Tables (Prisma / PascalCase models → snake_case tables):**
  `app_product` (`product_type`, `unit_cost`, `inci_name`, `is_active`, `blocked`,
  `code`, `name`, `uom`), `app_supplier_product` (`product_id`, `system_cost`,
  `unit_cost`, `currency`, `is_preferred`, `is_active`), `app_rate_settings`.
  **Never** use FM lowercase tables (`raw`, `rawsupp`, …).
- **DB password** lives in AWS Secrets Manager: `plx/staging/postgres/admin`
  (fallback `plx/uat/postgres/admin`). Hosts + branch↔DB map: `scripts/db-targets.json`.
  Staging has the freshest FM-synced costs (every 30 min); UAT is on-demand.
- The secrets loader (`~/.secrets-env.staging.ps1`) does **not** set
  `DATABASE_URL` — build it from the AWS secret (see SKILL.md snippet).
- The puller uses raw `pg` against `app_*` tables, so it has no dependency on the
  generated Prisma client — but bare node deps (`pg`) only resolve from `portal/`,
  so copy it into `portal/tmp/` and run with `npx tsx` from `portal/`.

## Reformulation strategy (hitting a price target)

The cheap base (e.g. grapeseed ≈ $4.5 USD/kg) leaves a small "active budget"
above it = `max_bulk_per_kg − base`. To reach a low target:

1. Reduce premium-oil inclusion (e.g. 10% → 4–5%).
2. Cut or substitute the expensive active (e.g. Sytenol® A → generic bakuchiol;
   THD ascorbate 2% → 0.5% or drop; drop neat squalane).
3. Raise the cheap base %.
4. Recompute; if marketing claims suffer, offer it as a **tier**, not the only option.

Present three tiers per SKU:
- **Value** — reduced actives, priced at the target.
- **Enhanced** — more actives, priced to hold the standard margin (modest premium).
- **Full** — exactly as briefed (premium tier when its actives are costly).

Auto-recommend per SKU: if Full price ≤ target + a "modest premium" threshold,
ship Full; else recommend Enhanced; else hold Value and sell Full as premium.

## Canvas (presentation) pattern

Read the `canvas` skill first. The price-ladder canvas (see the PRESSE example
`canvases/PRESSE-pricing-ladder.canvas.tsx`) uses:

- `useCanvasState` number levers via −/+ steppers (SDK has no slider): line rate,
  OH, operators, wage, paid/uptime hrs, fill, waste %, box, FX, target, margin,
  modest-premium threshold.
- Per-SKU `Card` + `Table` with rows **Value / Enhanced / Full** and columns
  Bulk CAD/kg · Cost USD · Customer price · Margin · vs-target, plus a
  recommendation `Pill`.
- A `Stat` summary strip and one `BarChart` (full-active price by SKU with a
  reference line at the target). Tones: success/warning/danger by margin.

## Report (PDF/Word) structure

Author HTML (best PDF fidelity) or Markdown, then run the `report-export` skill.
Recommended sections: executive summary → production economics → price ladder
(Value/Enhanced/Full) → original-vs-target feasibility → reformulation formulas →
secondary programs → assumptions & raw-material cost basis. Mark
**"Confidential — Indicative Pricing · not a binding quote"**.

## Brief types, density & QC

- **Commercial brief** (SKUs + volumes + target price + packaging terms) → full
  per-unit model + value/enhanced/full price ladder + canvas.
- **Formula sheet / bespoke** (one product, full %-w/w formula, no
  volumes/target/fill) → deliver **bulk $/kg + ranked cost drivers**, request the
  commercial inputs (fill size, volume, target, who supplies packaging), then
  price cost-plus. Do not build a tier ladder for a single bespoke SKU.
- **Ingredient → search terms:** expand each line to its INCI and any trade name.
  The puller matches `name` OR `inci_name`; trade names alone miss catalog items
  (e.g. `grapeseed` → 0, `vitis vinifera` → `R-0494`). Briefs that list INCI make
  this easy — feed the INCI column.
- **Density (fill mL → kg):** oils ~0.91; water-based emulsions/gels/scrubs ~1.0;
  butters/waxes ~0.95. State the value used.
- **QC checks:** formula %-w/w sums to ~100 (flag if not); `q.s.` lines (pH
  adjusters, etc.) get a small nominal allowance; `count: 0` from the puller means
  market-research the line. Call out the top 5–8 cost-driver lines — useful for
  value engineering even with no target.

## Worked example — PRESSE / DERMEA (2026-06)

- Brief: PRESSE = 5 grapeseed-base body oils (6 oz), target **$2.00 USD**,
  customer-supplies-all-packaging; DERMEA = 4 pre-soaked oil-pad jars.
- Real costs pulled from DB: squalane ~$65, rosehip ~$80 CAD, jojoba ~$36 CAD,
  argan ~$74 CAD, THD ascorbate ~$287 USD, caffeine ~$34 CAD, mica ~$51.
  Market gaps: grapeseed ~$4.5, marula ~$30, guarana ~$40 (USD).
- Line economics: 30/min, 6.5 h uptime, $200/h OH, 4 ops × 7.5 h × $25 →
  conversion ≈ **$0.25 CAD ($0.18 USD)/unit**.
- Result: at $2.00 with customer packaging, 5/5 SKUs viable in a Value formula
  (32–42% margin); 2 carry full actives at ~$2.00–2.26; GLOW UP (THD ascorbate)
  and NIGHT SHIFT (Sytenol® A) need reformulation or a premium tier. DERMEA $2.00
  N/A (oil fill alone $4–11/jar).
- Deliverables: interactive canvas + a PDF/Word report shared to OneDrive CursorInbox.

## Worked example — KS001REV Scalp Scrub (formula-only)

- Brief: a single bespoke product — a medium-viscosity rinse-off emulsion scrub
  (client Klaudia Siwak), full 22-line %-w/w formula, jar packaging, pH 4.5–5.0.
  **No fill size, volumes, target price, or packaging-responsibility** → treat as
  a formula-sheet brief.
- Costs from DB (cheapest sensible match): Olivem 1000 ~$30 USD, decyl glucoside
  ~$7.8 CAD, cetearyl alcohol ~$4.3 CAD, grapeseed (via INCI Vitis Vinifera)
  ~$8.25 CAD, pumice ~$1.3 CAD. Market gaps: tamanu oil, grapefruit seed extract,
  sweet orange EO. Density ~1.0 (emulsion).
- Result: **bulk cost ≈ $6.25 CAD/kg ($4.40 USD/kg)** material; **$6.87 CAD/kg
  with 10% waste**. **Bulk price (the KG quote) ≈ $9.82 CAD/kg ($6.91 USD/kg) at
  30% margin.** Top driver = Olivem 1000 emulsifier (~34% of bulk). Per-jar bulk:
  ~$1.38 CAD (200 g) / ~$1.72 CAD (250 g). Per-jar all-in price pending fill +
  volume + packaging responsibility.
- Lesson: this run is why the skill now (a) searches by INCI, (b) writes puller
  output to a file, (c) branches on brief type, and (d) sets density by product.
