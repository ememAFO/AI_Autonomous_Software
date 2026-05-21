# Workflow Rules

Stages:
1. Research
2. Validation
3. Planning
4. Build
5. Testing
6. Security Review
7. Policy Review
8. Human Approval
9. Deployment

Rules:
- No stage may be skipped.
- Failure blocks progression.
- Failed stages restart the workflow.
- Human approval required for deployment.
- Default behavior on uncertainty: STOP.
