# Pre-Plan Recalibrator Reference

This reference captures the research basis for the skill. Keep `SKILL.md` concise; read this file when source rationale or technique selection matters.

## Source Synthesis

The shared 2026 theme across the provided sources is that effective prompt engineering is context engineering plus iteration and evaluation. The skill should therefore improve the inputs to planning: intent, context, constraints, examples, output contract, risk, and verification.

## Source Notes

- Lakera, "The Ultimate Guide to Prompt Engineering in 2026": emphasizes clarity, reliability, model differences, security, and real-world use cases. Skill implication: ask for constraints, risks, and evaluation before planning.
- IBM, "The 2026 Guide to Prompt Engineering": frames prompt engineering as a practical discipline with tools, examples, and structured methods across skill levels. Skill implication: keep the workflow teachable and explicit.
- Thomas Wiegold, "Prompt Engineering Best Practices 2026": recommends starting simple, iterating, treating prompts like code, using few-shot examples when useful, and using XML or structured sections for Claude-style models. Skill implication: ask fewer better questions and produce a structured brief.
- K2View, "Prompt Engineering Techniques: Top 6 for 2026": summarizes zero-shot, few-shot, chain-of-thought, meta-prompting, and related techniques. Skill implication: choose techniques conditionally rather than forcing every method into every task.
- Promptitude and Erlin.ai 2026 guides: emphasize adaptive, multimodal, and context-aware prompt workflows, with frameworks around role, task, context, constraints, examples, and format. Skill implication: collect these fields before plan-writing.
- PromptingGuide.ai techniques: catalogues common methods including chain-of-thought, ReAct, tree-of-thought, retrieval, and self-consistency. Skill implication: expose plan-relevant summaries and verification, not hidden reasoning.
- X discussions from Alex Prompter, Bilgin Ibryam, and broader 2026 discourse: reinforce the shift from prompt tricks to AI workflow, context management, integration, and reliability. Skill implication: make the skill a planning checkpoint, not a copy-paste prompt library.

## Technique Mapping

Use this mapping when deciding what to ask.

- **Zero-shot**: suitable for simple, well-scoped tasks. Ask only for success criteria if missing.
- **Few-shot**: use when the desired result depends on style, tone, UI taste, report shape, or examples of correct behavior.
- **Prompt chaining**: use when work naturally breaks into discovery, plan, implementation, verification, and rollout.
- **ReAct / tool-using workflows**: use when planning depends on repo inspection, browser evidence, API checks, logs, or external systems.
- **Self-critique / plan review**: use when the plan is high-risk, multi-system, security-sensitive, or migration-heavy.
- **Retrieval/context engineering**: use when there are canonical docs, prior decisions, examples, specs, or source files that should anchor the plan.
- **Evaluation-first prompting**: use when success can be expressed as tests, acceptance criteria, metrics, screenshots, or operator signoff.

## When To Recommend The Skill

Recommend, but do not force, the skill when at least one condition is true:

- The user and agent have deliberated for several turns and are about to plan.
- The request is ambiguous enough that multiple valid plans would diverge.
- The task touches production, data, auth, migrations, external integrations, customer-visible UI, or cross-module contracts.
- The success criteria are unstated.
- The plan will create work for other agents or future sessions.
- The user asks for prompt engineering, task framing, plan prep, calibration, or a better agent prompt.

Do not recommend it for trivial edits, direct answers, or when the user explicitly asks to skip questions.

## Quality Bar

A strong Calibration Brief should:

- Fit on one screen when possible.
- Separate known facts from assumptions.
- Name non-goals so scope cannot silently expand.
- Define verification before implementation begins.
- Turn user intent into an agent-executable planning input.
- Preserve unresolved blockers instead of guessing.

## Source Caveats

The research pass reported direct access to Lakera, Thomas Wiegold, K2View, Promptitude, Erlin.ai, and PromptingGuide.ai. IBM's exact 2026 page timed out during direct fetch, but related IBM prompt engineering materials and snippets were available. X.com direct fetch may be restricted; thread takeaways should be treated as directional rather than canonical.
