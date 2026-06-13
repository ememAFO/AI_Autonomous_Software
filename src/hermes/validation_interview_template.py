from dataclasses import dataclass
from pathlib import Path


class ValidationInterviewTemplateError(Exception):
    pass


@dataclass(frozen=True)
class ValidationInterviewTemplate:
    theme: str
    target_user: str
    objective: str
    screening_questions: list[str]
    discovery_questions: list[str]
    willingness_to_pay_questions: list[str]
    risk_questions: list[str]
    evidence_logging_guidance: list[str]
    warning: str


class ValidationInterviewTemplateGenerator:
    """
    Generates a lightweight interview template for collecting primary validation evidence.

    Purpose:
    - help humans collect real customer evidence consistently
    - avoid leading questions
    - capture both supporting and opposing evidence
    - keep validation separate from build approval

    This does not approve human review or building.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/validation_interviews")

    def generate(
        self,
        *,
        theme: str,
        target_user: str = "small service business owner",
    ) -> ValidationInterviewTemplate:
        if not theme.strip():
            raise ValidationInterviewTemplateError("Theme is required")

        if not target_user.strip():
            raise ValidationInterviewTemplateError("Target user is required")

        if theme.strip().lower() == "lead + follow up":
            return ValidationInterviewTemplate(
                theme=theme.strip(),
                target_user=target_user.strip(),
                objective=(
                    "Understand whether delayed or inconsistent lead follow-up is a "
                    "real recurring problem, how users currently handle it, and whether "
                    "there is willingness to pay for a simple solution."
                ),
                screening_questions=[
                    "What type of business do you run or work in?",
                    "Do you receive new enquiries, leads, bookings, or quote requests?",
                    "Roughly how many new enquiries do you handle in a normal week?",
                    "Who is responsible for following up with those leads?",
                ],
                discovery_questions=[
                    "Can you walk me through what happens when a new lead comes in?",
                    "How do you currently remember who to follow up with?",
                    "What usually causes a lead to be missed or followed up late?",
                    "How often does delayed follow-up happen in a normal month?",
                    "What happens when follow-up is delayed?",
                    "Have you ever lost a booking, sale, or customer because follow-up was late?",
                    "What do you currently use to manage follow-up: notes, spreadsheets, CRM, reminders, WhatsApp, email, or something else?",
                    "What is frustrating about your current process?",
                ],
                willingness_to_pay_questions=[
                    "Have you paid for any tool that helps with leads, reminders, CRM, or automation?",
                    "If a simple tool helped you avoid missed follow-ups, would you consider paying for it?",
                    "What price would feel reasonable for a small business like yours?",
                    "What would make you say no, even if the tool worked?",
                    "Would you prefer a standalone tool or something that connects to what you already use?",
                ],
                risk_questions=[
                    "Would automatic follow-up feel helpful or annoying to your customers?",
                    "Are there privacy, consent, or spam concerns with follow-up messages?",
                    "Which channels would be acceptable: email, SMS, WhatsApp, phone reminders, or CRM tasks?",
                    "What would make this solution too complicated for you?",
                    "Do your current tools already solve this well enough?",
                ],
                evidence_logging_guidance=[
                    "Log exact quotes where possible.",
                    "Record whether the evidence supports or weakens the theme.",
                    "Record signal strength as strong, medium, weak, or negative.",
                    "Mark willingness-to-pay separately if the person discusses payment.",
                    "Do not treat polite interest as proof of demand.",
                    "Do not move to human review unless enough real evidence is collected.",
                ],
                warning=(
                    "Avoid leading the interviewee. Do not ask 'Wouldn't this be useful?' "
                    "Ask what they currently do, what fails, and whether the problem costs "
                    "time, money, or lost customers."
                ),
            )

        return ValidationInterviewTemplate(
            theme=theme.strip(),
            target_user=target_user.strip(),
            objective=(
                "Understand whether this theme represents a real recurring problem, "
                "how users currently solve it, and whether the problem is urgent enough "
                "to justify further validation."
            ),
            screening_questions=[
                "What type of work or business do you do?",
                "How often do you experience this problem area?",
                "Who is responsible for dealing with it?",
            ],
            discovery_questions=[
                "Can you describe the last time this problem happened?",
                "What caused it?",
                "How did you solve it?",
                "What was frustrating about the process?",
                "What did it cost in time, money, or missed opportunities?",
                "What tools or workarounds do you currently use?",
            ],
            willingness_to_pay_questions=[
                "Have you paid for a tool to solve this problem before?",
                "Would you consider paying if a solution clearly saved time or money?",
                "What would make the solution worth paying for?",
                "What would make you reject it?",
            ],
            risk_questions=[
                "What existing tools already solve part of this?",
                "What would make this solution too risky or too complicated?",
                "Is this a frequent problem or only an occasional annoyance?",
            ],
            evidence_logging_guidance=[
                "Capture exact quotes.",
                "Separate real pain from polite interest.",
                "Record counter-evidence clearly.",
                "Do not move forward without repeated evidence.",
            ],
            warning="Do not lead the interviewee. Let the user describe the problem in their own words.",
        )

    def format_markdown(self, template: ValidationInterviewTemplate) -> str:
        return f"""# Validation Interview Template: {template.theme}

## Target User

{template.target_user}

## Objective

{template.objective}

## Warning

{template.warning}

## Screening Questions

{self._format_list(template.screening_questions)}

## Discovery Questions

{self._format_list(template.discovery_questions)}

## Willingness-To-Pay Questions

{self._format_list(template.willingness_to_pay_questions)}

## Risk / Counter-Evidence Questions

{self._format_list(template.risk_questions)}

## Evidence Logging Guidance

{self._format_list(template.evidence_logging_guidance)}

## Governance Note

This interview template does not approve human review or build planning. It only helps collect primary validation evidence that can later be logged and assessed by the ValidationGate.
"""

    def write_markdown(
        self,
        *,
        theme: str,
        target_user: str,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        self._validate_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        template = self.generate(theme=theme, target_user=target_user)
        path.write_text(self.format_markdown(template), encoding="utf-8")

        return path

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None."

        return "\n".join(f"- {value}" for value in values)

    def _validate_output_path(self, output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationInterviewTemplateError(
                "Validation interview template must be written inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValidationInterviewTemplateError(
                "Validation interview template must be a Markdown file"
            )
