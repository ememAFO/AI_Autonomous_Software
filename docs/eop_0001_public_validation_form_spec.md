# EOP-0001 Public Validation Form Specification

## Purpose

Collect broad, structured first-party signals from UK electricians, small
electrical contractors, other trade owners, and customers without requiring
names, email addresses, phone numbers, postal addresses, IP addresses, or raw
transcripts.

The form is evidence collection, not marketing consent, sales outreach, or a
promise that software will be built.

## Consent text

> I understand that my anonymised responses may be used to evaluate whether
> quote follow-up and outcome tracking are meaningful problems for small trade
> businesses. I will not include names, contact details, client identities, or
> confidential job information. I understand that submitting this form does not
> join a marketing list unless I separately choose the waitlist action.

Consent version: `EOP-FPV-CONSENT-0.1`

## Core questions

1. Which best describes you?
   - electrician or electrical contractor owner;
   - employee or administrator in an electrical contractor;
   - customer who has requested trade quotations;
   - owner of another trade business.
2. During the last 30 days, approximately how many quotations or price enquiries
   did the business handle?
3. How are outstanding quotations currently tracked?
4. What usually happens when a customer does not respond?
5. Which outcome categories can the business currently distinguish: accepted,
   declined, postponed, price concern, competitor selected, scope unclear, not
   received, or unknown?
6. Describe one recent example without names, contact details, addresses, or
   confidential job details.
7. What would make a follow-up process unhelpful, annoying, risky, or too time
   consuming?
8. Would the respondent take a concrete waitlist action to test a simple manual
   tracker?
9. Would the respondent take a concrete price-intent action for the proposed
   £7 tracker? A hypothetical “yes” without an action must not be recorded as
   willingness-to-pay evidence.

## Evidence handling

A normal free-text form response is captured as `structured_response`. The
current validation taxonomy has no survey-response evidence type, so it is
**hold-only** and cannot be imported as a customer interview.

The following can become importable candidates after human review:

- an explicit waitlist action → `waitlist_signup`;
- a concrete recorded price-intent action → `willingness_to_pay`;
- aggregate landing-page measurements → `landing_page_result`;
- a separately conducted direct interview → `customer_interview`;
- a direct participant or pilot risk observation → `risk_finding`.

Do not convert ordinary survey answers into interview, waitlist, or payment
evidence merely to satisfy the validation gate.
