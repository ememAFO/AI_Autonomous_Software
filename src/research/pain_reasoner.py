from src.research.pain_analysis import (
    CommercialSignal,
    PainAnalysis,
    PainCategory,
    PainDecision,
    ProcessMap,
)


class PainReasoner:
    """
    Structured pain reasoning layer.

    Purpose:
    - identify gaps between current and desired state
    - distinguish weak complaints from business pain
    - classify pain type
    - infer possible root causes
    - produce process-map style reasoning

    This does not:
    - fetch external data
    - write files
    - execute commands
    - create opportunities directly
    """

    ECONOMIC_TERMS = {
        "revenue",
        "sales",
        "lead",
        "leads",
        "deal",
        "deals",
        "quote",
        "quotes",
        "invoice",
        "invoices",
        "payment",
        "payments",
        "cost",
        "expensive",
        "pricing",
        "paywall",
        "paywalls",
        "churn",
        "retention",
        "customers leave",
    }

    WORKFLOW_TERMS = {
        "manual",
        "repetitive",
        "spreadsheet",
        "duplicate",
        "duplicates",
        "workflow",
        "process",
        "tracking",
        "follow up",
        "follow-up",
        "chasing",
        "too many steps",
    }

    TIME_TERMS = {
        "slow",
        "delay",
        "delayed",
        "takes too long",
        "time consuming",
        "waiting",
        "backlog",
    }

    INTEGRATION_TERMS = {
        "integration",
        "integrations",
        "sync",
        "duplicate contacts",
        "data entry",
        "connect",
        "connected",
        "api",
    }

    SUPPORT_TERMS = {
        "support",
        "customer service",
        "unresolved",
        "escalated",
        "not resolved",
        "slow to respond",
        "less helpful",
    }

    ONBOARDING_TERMS = {
        "onboarding",
        "training",
        "learning curve",
        "hard to learn",
        "setup",
        "configure",
        "configuration",
    }

    UX_TERMS = {
        "confusing",
        "hard to use",
        "not intuitive",
        "clunky",
        "overwhelming",
        "difficult",
        "limited flexibility",
        "limited",
    }

    COMPLIANCE_TERMS = {
        "compliance",
        "audit",
        "regulation",
        "policy",
        "legal",
        "risk",
    }

    COMMUNICATION_TERMS = {
        "reply",
        "replying",
        "message",
        "messages",
        "email",
        "reminder",
        "reminders",
        "communication",
    }

    WEAK_PREFERENCE_TERMS = {
        "colour",
        "color",
        "font",
        "theme",
        "nice",
        "beautiful",
        "looks good",
    }

    NEGATED_ECONOMIC_TERMS = {
        "no revenue issue",
        "no revenue impact",
        "not affecting revenue",
        "no sales impact",
        "no lost deals",
        "no payment issue",
        "no customer loss",
        "no client loss",
    }

    def analyze(self, text: str, *, industry: str = "unknown") -> PainAnalysis:
        clean_text = self._clean_text(text)
        lowered = clean_text.lower()

        if not clean_text:
            return self._reject_empty()

        category = self._classify_category(lowered)
        evidence = self._extract_evidence(clean_text)

        has_gap = self._has_gap_signal(lowered)
        has_consequence = self._has_consequence_signal(lowered)
        has_workflow = self._contains_any(lowered, self.WORKFLOW_TERMS)
        has_economic = self._has_valid_economic_signal(lowered)
        weak_preference_only = self._is_weak_preference_only(lowered)

        commercial_signal = self._commercial_signal(
            has_economic=has_economic,
            has_consequence=has_consequence,
            has_workflow=has_workflow,
            category=category,
        )

        decision = self._decision(
            weak_preference_only=weak_preference_only,
            has_gap=has_gap,
            has_consequence=has_consequence,
            has_economic=has_economic,
            has_workflow=has_workflow,
            category=category,
            evidence=evidence,
        )

        confidence = self._confidence(
            decision=decision,
            has_gap=has_gap,
            has_consequence=has_consequence,
            has_economic=has_economic,
            has_workflow=has_workflow,
            evidence_count=len(evidence),
        )

        return PainAnalysis(
            is_pain=decision == PainDecision.ACCEPT,
            decision=decision,
            confidence=confidence,
            pain_category=category,
            commercial_signal=commercial_signal,
            current_state=self._current_state(category, clean_text),
            desired_state=self._desired_state(category, industry),
            gap=self._gap(category),
            consequence=self._consequence(category, has_economic),
            symptom=self._symptom(clean_text),
            possible_root_causes=self._root_causes(category, lowered),
            evidence=evidence,
            process_map=self._process_map(category, clean_text),
            notes=self._notes(decision, category, commercial_signal),
        )

    def _reject_empty(self) -> PainAnalysis:
        return PainAnalysis(
            is_pain=False,
            decision=PainDecision.REJECT,
            confidence=0.0,
            pain_category=PainCategory.UNCLEAR,
            commercial_signal=CommercialSignal.WEAK,
            current_state="No feedback text provided.",
            desired_state="A clear feedback statement is required.",
            gap="No analyzable gap.",
            consequence="No consequence identified.",
            symptom="No symptom identified.",
            possible_root_causes=[],
            evidence=[],
            process_map=None,
            notes=["Empty input was rejected."],
        )

    def _clean_text(self, text: str) -> str:
        return " ".join(str(text or "").replace("\n", " ").split()).strip()

    def _classify_category(self, text: str) -> PainCategory:
        if self._contains_any(text, self.COMPLIANCE_TERMS):
            return PainCategory.COMPLIANCE_RISK

        if self._contains_any(text, self.INTEGRATION_TERMS):
            return PainCategory.INTEGRATION

        if self._contains_any(text, self.SUPPORT_TERMS):
            return PainCategory.SUPPORT

        if self._contains_any(text, self.ONBOARDING_TERMS):
            return PainCategory.ONBOARDING

        if self._contains_any(text, self.WORKFLOW_TERMS):
            return PainCategory.WORKFLOW

        if self._has_valid_economic_signal(text):
            return PainCategory.ECONOMIC

        if self._contains_any(text, self.TIME_TERMS):
            return PainCategory.TIME

        if self._contains_any(text, self.COMMUNICATION_TERMS):
            return PainCategory.COMMUNICATION

        if self._contains_any(text, self.UX_TERMS):
            return PainCategory.UX_FRICTION

        return PainCategory.UNCLEAR

    def _extract_evidence(self, text: str) -> list[str]:
        lowered = text.lower()

        evidence_terms = [
            *self.ECONOMIC_TERMS,
            *self.WORKFLOW_TERMS,
            *self.TIME_TERMS,
            *self.INTEGRATION_TERMS,
            *self.SUPPORT_TERMS,
            *self.ONBOARDING_TERMS,
            *self.UX_TERMS,
            *self.COMMUNICATION_TERMS,
            *self.COMPLIANCE_TERMS,
        ]

        evidence = []

        for term in evidence_terms:
            if term in lowered:
                evidence.append(term)

        return list(dict.fromkeys(evidence))[:12]

    def _has_gap_signal(self, text: str) -> bool:
        gap_terms = {
            "but",
            "however",
            "although",
            "struggle",
            "struggled",
            "cannot",
            "can't",
            "couldn't",
            "doesn't",
            "does not",
            "limited",
            "missing",
            "hard to",
            "difficult",
            "takes too long",
            "not resolved",
            "slow",
            "expensive",
        }

        return self._contains_any(text, gap_terms)

    def _has_consequence_signal(self, text: str) -> bool:
        consequence_terms = {
            "lose",
            "losing",
            "lost",
            "churn",
            "delay",
            "delayed",
            "takes too long",
            "slow",
            "duplicate",
            "duplicates",
            "unresolved",
            "not resolved",
            "customers stop",
            "customers leave",
            "limited",
            "expensive",
            "paywall",
            "paywalls",
            "difficult to resolve",
        }

        return self._contains_any(text, consequence_terms)

    def _has_valid_economic_signal(self, text: str) -> bool:
        if self._contains_any(text, self.NEGATED_ECONOMIC_TERMS):
            return False

        return self._contains_any(text, self.ECONOMIC_TERMS)

    def _is_weak_preference_only(self, text: str) -> bool:
        has_preference = self._contains_any(text, self.WEAK_PREFERENCE_TERMS)
        has_commercial = self._has_valid_economic_signal(text)
        has_consequence = self._has_consequence_signal(text)
        has_workflow = self._contains_any(text, self.WORKFLOW_TERMS)

        return has_preference and not has_commercial and not has_consequence and not has_workflow

    def _commercial_signal(
        self,
        *,
        has_economic: bool,
        has_consequence: bool,
        has_workflow: bool,
        category: PainCategory,
    ) -> CommercialSignal:
        if has_economic and (has_consequence or has_workflow):
            return CommercialSignal.STRONG

        if category in {
            PainCategory.INTEGRATION,
            PainCategory.SUPPORT,
            PainCategory.ONBOARDING,
            PainCategory.WORKFLOW,
        } and has_consequence:
            return CommercialSignal.MODERATE

        if has_economic:
            return CommercialSignal.MODERATE

        return CommercialSignal.WEAK

    def _decision(
        self,
        *,
        weak_preference_only: bool,
        has_gap: bool,
        has_consequence: bool,
        has_economic: bool,
        has_workflow: bool,
        category: PainCategory,
        evidence: list[str],
    ) -> PainDecision:
        if weak_preference_only:
            return PainDecision.REJECT

        if category == PainCategory.UNCLEAR and len(evidence) < 2:
            return PainDecision.REJECT

        if has_gap and (has_consequence or has_economic or has_workflow):
            return PainDecision.ACCEPT

        if has_consequence and (has_economic or has_workflow):
            return PainDecision.ACCEPT

        if category in {
            PainCategory.INTEGRATION,
            PainCategory.SUPPORT,
            PainCategory.ONBOARDING,
            PainCategory.COMPLIANCE_RISK,
        } and len(evidence) >= 2:
            return PainDecision.ACCEPT

        if len(evidence) >= 2:
            return PainDecision.WEAK_PAIN

        return PainDecision.REJECT

    def _confidence(
        self,
        *,
        decision: PainDecision,
        has_gap: bool,
        has_consequence: bool,
        has_economic: bool,
        has_workflow: bool,
        evidence_count: int,
    ) -> float:
        score = 0.15

        if decision == PainDecision.ACCEPT:
            score += 0.25

        if has_gap:
            score += 0.15

        if has_consequence:
            score += 0.15

        if has_economic:
            score += 0.15

        if has_workflow:
            score += 0.10

        score += min(evidence_count * 0.03, 0.15)

        return round(min(score, 0.95), 2)

    def _current_state(self, category: PainCategory, text: str) -> str:
        if category == PainCategory.INTEGRATION:
            return "Users experience friction connecting tools, syncing data, or managing duplicate records."

        if category == PainCategory.SUPPORT:
            return "Users depend on support or escalation to resolve product issues."

        if category == PainCategory.ONBOARDING:
            return "Users need training, setup, or onboarding before they can get full value."

        if category == PainCategory.WORKFLOW:
            return "Users rely on manual or inefficient workflow steps."

        if category == PainCategory.ECONOMIC:
            return "Users experience cost, revenue, payment, or commercial pressure."

        if category == PainCategory.UX_FRICTION:
            return "Users experience usability friction or confusion."

        return f"Users report a problem: {text[:160]}"

    def _desired_state(self, category: PainCategory, industry: str) -> str:
        if category == PainCategory.INTEGRATION:
            return f"{industry} users want tools and data to work together reliably."

        if category == PainCategory.SUPPORT:
            return f"{industry} users want issues resolved quickly without weak escalation."

        if category == PainCategory.ONBOARDING:
            return f"{industry} users want fast setup and clear adoption support."

        if category == PainCategory.WORKFLOW:
            return f"{industry} users want the workflow to be faster, easier, and less manual."

        if category == PainCategory.ECONOMIC:
            return f"{industry} users want lower cost, better ROI, or less revenue leakage."

        if category == PainCategory.UX_FRICTION:
            return f"{industry} users want a simpler and clearer user experience."

        return f"{industry} users want the stated problem removed or reduced."

    def _gap(self, category: PainCategory) -> str:
        gap_map = {
            PainCategory.INTEGRATION: "Current tools do not connect or sync as expected.",
            PainCategory.SUPPORT: "Support does not resolve issues quickly or reliably enough.",
            PainCategory.ONBOARDING: "Users need more guidance than the product currently provides.",
            PainCategory.WORKFLOW: "The current workflow requires too much manual effort or repetition.",
            PainCategory.ECONOMIC: "The current solution creates cost, revenue, or ROI pressure.",
            PainCategory.TIME: "The current process takes longer than users expect.",
            PainCategory.UX_FRICTION: "The current experience is harder to use than expected.",
            PainCategory.COMPLIANCE_RISK: "Current process may expose users to policy, audit, or legal risk.",
            PainCategory.COMMUNICATION: "Messages, reminders, or updates are not reliable enough.",
            PainCategory.RETENTION: "The current experience may cause users or customers to leave.",
            PainCategory.UNCLEAR: "The gap is not clear enough yet.",
        }

        return gap_map[category]

    def _consequence(self, category: PainCategory, has_economic: bool) -> str:
        if has_economic:
            return "The gap may create revenue loss, cost pressure, churn risk, or weak ROI."

        consequence_map = {
            PainCategory.INTEGRATION: "Users may waste time on duplicate work or manual data fixes.",
            PainCategory.SUPPORT: "Unresolved issues may slow users down and reduce trust.",
            PainCategory.ONBOARDING: "Users may fail to adopt the product fully.",
            PainCategory.WORKFLOW: "Users may waste time and miss important tasks.",
            PainCategory.TIME: "Users may experience delays and reduced productivity.",
            PainCategory.UX_FRICTION: "Users may avoid features or need extra help.",
            PainCategory.COMPLIANCE_RISK: "Users may face audit, legal, policy, or security exposure.",
            PainCategory.COMMUNICATION: "Users may miss important updates or follow-ups.",
            PainCategory.RETENTION: "Users or customers may leave.",
            PainCategory.UNCLEAR: "The consequence is not clear enough yet.",
        }

        return consequence_map[category]

    def _symptom(self, text: str) -> str:
        return text[:220]

    def _root_causes(self, category: PainCategory, text: str) -> list[str]:
        root_causes = {
            PainCategory.INTEGRATION: [
                "Missing or weak integration design.",
                "Data synchronization gaps.",
                "Manual workaround replacing product capability.",
            ],
            PainCategory.SUPPORT: [
                "Escalation process may be weak.",
                "Product complexity may create avoidable support demand.",
                "Support capacity may not match user needs.",
            ],
            PainCategory.ONBOARDING: [
                "Training material may be insufficient.",
                "Setup flow may be too complex.",
                "Product value may not be obvious early enough.",
            ],
            PainCategory.WORKFLOW: [
                "Workflow ownership may be unclear.",
                "Manual steps have not been automated.",
                "Users may be relying on spreadsheets or memory.",
            ],
            PainCategory.ECONOMIC: [
                "Pricing may not match perceived value.",
                "Users may not see enough ROI.",
                "The product may create hidden operating costs.",
            ],
            PainCategory.UX_FRICTION: [
                "Interface may not match user mental model.",
                "Important actions may require too many steps.",
                "Information architecture may be unclear.",
            ],
        }

        causes = root_causes.get(
            category,
            ["Root cause is unclear and needs further validation."],
        )

        if "paywall" in text or "paywalls" in text:
            causes.append("Key functionality may be locked behind pricing tiers.")

        if "duplicate" in text or "duplicates" in text:
            causes.append("Record matching or deduplication may be weak.")

        return causes

    def _process_map(self, category: PainCategory, text: str) -> ProcessMap:
        return ProcessMap(
            trigger="User attempts to complete the task described in the feedback.",
            action=self._current_state(category, text),
            friction=self._gap(category),
            consequence=self._consequence(
                category,
                has_economic=self._has_valid_economic_signal(text.lower()),
            ),
            workaround=self._workaround(text.lower()),
        )

    def _workaround(self, text: str) -> str | None:
        if "spreadsheet" in text:
            return "Users may be using spreadsheets as a workaround."

        if "manual" in text:
            return "Users may be relying on manual workarounds."

        if "support" in text or "customer service" in text:
            return "Users may depend on support teams to resolve product friction."

        if "community" in text:
            return "Users may rely on community forums to find answers."

        return None

    def _notes(
        self,
        decision: PainDecision,
        category: PainCategory,
        commercial_signal: CommercialSignal,
    ) -> list[str]:
        notes = [
            f"Decision: {decision.value}",
            f"Pain category: {category.value}",
            f"Commercial signal: {commercial_signal.value}",
        ]

        if decision == PainDecision.WEAK_PAIN:
            notes.append("Pain exists but needs stronger consequence evidence.")

        if decision == PainDecision.REJECT:
            notes.append("Rejected because the text lacks a clear business pain gap.")

        return notes

    def _contains_any(self, text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)
