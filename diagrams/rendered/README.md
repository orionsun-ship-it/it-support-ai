# Rendered diagrams

Pre-rendered SVGs of every mermaid block in this directory. Useful for
reviewers who open the markdown in a viewer that doesn't render
mermaid (some PDF exporters, plain text viewers, IDE previewers).

If you edit the source markdown, regenerate these with:

```bash
# from repo root
npx -p @mermaid-js/mermaid-cli@latest -- mmdc \
  -i diagrams/architecture.md -o diagrams/rendered/architecture.svg
# (mmdc supports rendering all blocks from a single .md, or you can
#  do it block-by-block as the helper script in CONTRIBUTING shows)
```

The mapping of file → source block:

| File                               | Source                                      |
| ---------------------------------- | ------------------------------------------- |
| `01-architecture-system.svg`       | `architecture.md` block 1 (system topology) |
| `02-architecture-routing.svg`      | `architecture.md` block 2 (routing detail)  |
| `03-workflow-overview.svg`         | `workflow.md` §1                            |
| `04-workflow-pathA-knowledge.svg`  | `workflow.md` §2 (knowledge-only)           |
| `05-workflow-pathB-automation.svg` | `workflow.md` §3 (simulated automation)     |
| `06-workflow-pathC-escalation.svg` | `workflow.md` §4 (urgent escalation)        |
| `07-workflow-pathD-stuck.svg`      | `workflow.md` §5 (weak match + stuck)       |
| `08-workflow-pathE-nonsupport.svg` | `workflow.md` §6 (non-support)              |
| `09-workflow-state-lifecycle.svg`  | `workflow.md` §7 (state lifecycle)          |
| `10-workflow-cross-transport.svg`  | `workflow.md` §8 (cross-transport)          |

`wireframes.md` is ASCII only — no mermaid blocks, so nothing to render.
