---
name: implement-ticket
description: "Standard workflow for implementing one Kanban ticket from docs/KANBAN.md. Use whenever starting, continuing, or completing a backlog ticket (e.g. 'implement E1', 'work the next ticket', 'do A2'). Ensures rules are read, acceptance criteria are met, tests are written, and progress is updated."
---

# Skill: Implement a Kanban ticket

Follow this every time you pick up a ticket.

1. **Load the ticket.** Open `docs/KANBAN.md`, find the ticket by ID. Confirm all its
   dependencies are `Done` in `docs/PROGRESS.md`. If not, stop and surface the blocker.
2. **Load context.** Read the matching rule file(s) in `.claude/rules/` and any ADR the
   ticket references in `docs/adr/`. Skim the relevant HLD/LLD sections.
3. **Restate the plan.** Briefly list the files you will add/change and how you will meet
   each acceptance criterion. If two viable designs exist, present both and ask.
4. **Implement.** Minimal, focused changes. Respect the invariants in `CLAUDE.md`
   (especially: rules decide, Python stateless, prefetch=1, decisions versioned).
5. **Test.** Add/adjust unit tests per `.claude/rules/testing-and-commits.md`. Run them.
6. **Update progress.** Check the box for this ticket in `docs/PROGRESS.md`; add a one-line
   note of anything learned or any follow-up ticket discovered.
7. **Commit.** One logical commit, conventional style, referencing the ticket ID.
8. **ADR check.** If you made or changed a durable design decision, add/update an ADR.
