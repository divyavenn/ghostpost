## Core Rules section

— Before making any changes, use a task agent to explore the current architecture: which files handle the pipeline, what data structures are used, and what the entry points are. Report back before proposing any code changes.

- When modifying code, do NOT add features, functionality, or refactors that were not explicitly requested. If you think something extra would be helpful, ask first — do not implement it.

- When modifying code, do NOT add features, functionality, or refactors that were not explicitly requested. If you think something extra would be helpful, ask first — do not implement it.


- When the user corrects your approach or rejects a change, do NOT re-introduce similar patterns. Stick to the user's stated preference for the rest of the session.

-  This is a multi-language project: Rust is the primary CLI/entry point, Python handles backend/automation/LLM tasks, TypeScript is used for the browser extension and frontend. Rust spawns Python subprocesses — not the other way around.

- When debugging, make ONE targeted fix at a time and verify it works before moving on. Do not bundle multiple speculative fixes together.

- Keep data formats simple. Do not over-engineer data structures (e.g., storing full JSON objects where simple IDs are expected). When refactoring data formats, preserve backward compatibility unless explicitly told otherwise.

