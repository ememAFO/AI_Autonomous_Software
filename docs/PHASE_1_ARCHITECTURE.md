# Phase 1 Architecture

## Runtime choice

- Agent Zero: execution/orchestration layer for controlled coding, testing, and tool use.
- Hermes: research/intelligence layer for opportunity discovery, memory, and trend analysis.
- Factory governance: custom workflow engine, policy engine, audit log, approval gate, and sandbox runner.

The governance layer is intentionally independent from Agent Zero and Hermes. This means any agent must pass through the same controls.

## Phase 1 components

1. Workflow Engine
   - Enforces stage order.
   - Fails closed when a stage fails.

2. Policy Engine
   - Blocks protected-file edits.
   - Blocks production deployment by default.
   - Blocks auth/billing modification without approval.
   - Blocks insecure defaults and secret exposure.

3. Permission Policy
   - Keeps agent edits inside approved folders only.
   - Blocks path traversal outside the project.
   - Blocks protected governance files.

4. Protected File Integrity
   - Builds hashes for protected files.
   - Detects missing, added, or changed protected files.

5. Approval Gate
   - Creates human approval requests.
   - Requires explicit approval before sensitive actions.

6. Sandbox Runner
   - Allows only safe testing/scanning commands.
   - Blocks sudo, chown, chmod, curl, wget, ssh, and destructive commands.

7. Audit Log
   - Writes append-only JSONL events for policy decisions and future agent actions.

## Security rule

Agent Zero and Hermes must never receive unrestricted host access, root access, sudo access, production secrets, or direct production deployment rights.
