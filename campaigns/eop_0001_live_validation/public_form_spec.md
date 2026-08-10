# Provider-Neutral Public Validation Form Specification

## Form purpose

Collect structured discovery evidence from UK electricians and electrical
contractors without collecting direct identifiers in the research response.

The form must run on a provider selected by the project owner. It must not
depend on Google Forms.

## Privacy architecture

The research form and contact form must be separate.

### Research form

Must not collect:

- name;
- email;
- phone number;
- business address;
- customer information;
- postcode;
- IP address where avoidable;
- quotation documents;
- free-text transcripts;
- recordings.

### Optional contact form

May collect contact details only after the participant deliberately chooses to
continue. It must store those details separately and use a generated
participant token to link the opt-in to the research response.

Stage 4G research capture must receive the participant token, not the contact
details.

## Introduction text

> We are researching how UK electricians and small electrical contractors
> manage quotation outcomes. This form is for product discovery and does not
> provide legal, financial or business advice. Do not enter your name, email,
> phone number, customer details, addresses or quotation documents. Responses
> may be used in anonymised research summaries. Participation is voluntary.

## Questions

### Q1. Which description best matches your role?

Single choice:

- Electrical business owner
- Self-employed electrician
- Estimator or surveyor
- Office or administration staff managing quotations
- Operations or contracts manager
- Other electrical-trade role
- None of these

`None of these` should be screened out of primary target analysis.

### Q2. Where do you mainly work?

Single choice:

- England
- Scotland
- Wales
- Northern Ireland
- Across multiple UK nations
- Outside the UK

No postcode or precise location.

### Q3. Approximately how many people work in the business?

Single choice:

- 1
- 2–4
- 5–9
- 10–19
- 20 or more
- Prefer not to say

### Q4. Roughly how many quotations does the business send in a typical month?

Single choice:

- 0–4
- 5–10
- 11–25
- 26–50
- More than 50
- Unsure

### Q5. Which quotation outcomes do you currently record?

Multiple choice:

- Accepted
- Declined
- Deferred or postponed
- Customer chose another contractor
- Price objection
- Scope or timing issue
- Expired
- No response or unclassified
- We do not record outcomes consistently
- Other bounded category

### Q6. In a typical month, roughly what share of quotations finish without a clear recorded outcome?

Single choice:

- None
- Less than 10%
- 10–24%
- 25–49%
- Half or more
- Unsure

### Q7. How is quotation follow-up currently handled?

Multiple choice:

- No regular follow-up
- Personal reminder or diary
- Spreadsheet
- Existing trade or job-management software
- Accounting software
- Email templates
- SMS or messaging
- Office staff
- Other bounded category

### Q8. What most often prevents consistent follow-up or outcome recording?

Choose up to three:

- Too busy delivering work
- Unsure when to follow up
- Do not want to annoy customers
- Quotes are spread across different systems
- No easy way to record outcomes
- Customers rarely explain their decision
- Existing software is not configured
- Follow-up feels low value
- Someone else handles it
- Not a meaningful problem
- Other bounded category

### Q9. Which information would be most useful when deciding whether to follow up?

Choose up to four:

- Confirmation that the quote was received
- Quote age
- Quote value band
- Job urgency
- Planned start date
- Previous customer relationship
- Lead source
- Customer questions or change requests
- Quote expiry
- Previous follow-up attempts
- Likely reason for delay
- None of these

### Q10. Which outcome would be most valuable?

Single choice:

- More accepted quotations
- Faster decisions
- Fewer unclassified quotations
- Better reasons for lost work
- Less manual follow-up
- Avoiding unnecessary messages
- Better forecasting
- No meaningful benefit

### Q11. What would you be willing to do next?

Single choice:

- Complete a short direct research interview
- Join a small no-automation pilot
- Share anonymised baseline counts
- Join a waitlist only
- Review a proposed workflow
- Nothing further

This answer is an expression of interest, not a completed waitlist action. A
separate opt-in action is required.

### Q12. Optional bounded comment

Prompt:

> In one or two sentences, describe the last time a quotation remained open or
> unclear. Do not include names, contact details, addresses, customer details or
> quotation documents.

Maximum 300 characters. The implementation must scan for direct identifiers
before Stage 4G capture.

## Consent

Required checkbox:

> I understand the research purpose, I have not included direct identifiers or
> customer details, and I agree that my anonymised response may be reviewed for
> product-discovery research.

The consent version must match the active Stage 4G campaign policy.

## Completion screen

Provide:

- a generated response token;
- a brief explanation that the response is not automatically treated as
  validated customer evidence;
- a separate optional link for interview or pilot contact;
- a warning not to paste the token into public comments.
