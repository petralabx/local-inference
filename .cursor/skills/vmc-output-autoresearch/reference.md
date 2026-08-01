# VMC Output AutoResearch Reference

## Run Contract

Each run declares:

```yaml
archetype: growth-site
mode: report-only | produce-with-approval | iterate-to-gate
goal: string
audience: string[]
constraints: string[]
evidence_sources:
  - vmc_autoresearch
  - web
  - repo
  - user_material
success_gates:
  - gate_id
stop_after_polish_loops: 2
human_gates:
  - launch_approval
```

## General Output Template

```markdown
## Summary
<What was produced or researched>

## Archetype
<archetype> / <mode>

## Evidence
- <source and why it matters>

## Output
- <files, artifacts, or recommendations>

## Eval Results
- <gate>: <pass/fail/not run> — <evidence>

## Risks
- <remaining risk or blocker>

## Next Action
<one concrete next step>
```

## `growth-site` Schema

Use this archetype for public marketing experiences.

```yaml
required_pages:
  - home
  - about
  - capabilities
  - blog_or_insights
  - contact_or_lead_capture
research_lanes:
  customer_intent:
    output: persona_map
  seo_keywords:
    output: keyword_cluster_map
  competitor_teardown:
    output: comparison_matrix
  conversion_strategy:
    output: objection_cta_map
  claim_safety:
    output: grounded_claim_register
evals:
  route_integrity:
    hard_gate: true
  seo_metadata:
    hard_gate: true
  structured_data:
    hard_gate: false
  accessibility_basics:
    hard_gate: true
  responsive_visual_qa:
    hard_gate: true
  performance:
    hard_gate: true
  conversion_rubric:
    hard_gate: false
  claim_safety:
    hard_gate: true
```

### Growth-Site Rubric

Score each category 0-3. A polished output should score at least 2 in every
category and 3 in the categories tied to the user's explicit goal.

| Category | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Positioning | Generic | Clear but common | Distinct and credible | Category-defining |
| SEO | Missing basics | Basic metadata | Intent-led structure | Keyword cluster and schema aligned |
| Conversion | Weak CTA | CTA exists | Objections handled | Funnel feels inevitable |
| Visual craft | Broken/plain | Acceptable | Premium | Memorable and polished |
| Trust | Unsupported | Some proof | Strong proof | Proof woven throughout |
| Accessibility | Risky | Partial | Good basics | Deliberate inclusive design |
| Performance | Unknown | Heavy | Acceptable | Fast and resilient |

## `technical-architecture` Schema

```yaml
required_outputs:
  - current_state
  - target_state
  - data_flow
  - tradeoffs
  - risks
  - rollout_plan
  - rollback_plan
evals:
  evidence_grounding:
    hard_gate: true
  boundary_clarity:
    hard_gate: true
  security_review:
    hard_gate: true
  migration_safety:
    hard_gate: true
  verification_plan:
    hard_gate: true
```

## `content-engine` Schema

```yaml
required_outputs:
  - audience_map
  - topic_clusters
  - pillar_pages
  - supporting_articles
  - internal_linking_plan
  - metadata_plan
evals:
  search_intent_coverage:
    hard_gate: true
  editorial_coherence:
    hard_gate: true
  claim_safety:
    hard_gate: true
```

## `competitive-intel` Schema

```yaml
required_outputs:
  - competitor_set
  - comparison_dimensions
  - source_log
  - opportunity_map
  - recommended_moves
evals:
  source_quality:
    hard_gate: true
  consistent_comparison:
    hard_gate: true
  actionability:
    hard_gate: true
```

## VMC Report-Only AutoResearch Adapter

When using VMC report-only AutoResearch:

1. Confirm the target project and research scope.
2. Use existing reports if fresh enough for the task.
3. If a new report is needed, run or dispatch the VMC report-only pipeline.
4. Treat the report as advisory evidence, not automatic authority.
5. Cite report paths or dispatch IDs in the handoff.

The report-only pipeline should never edit code directly. It produces briefs
that the output loop can apply after plan approval.

## Iteration Rules

1. Keep each polish loop scoped to failed or weak gates.
2. Do not rewrite passed areas unless the next gate depends on it.
3. Stop after two loops without measurable improvement.
4. For subjective gates, record the rubric delta rather than claiming proof.
5. Human launch approval is non-waivable for public brand surfaces.
