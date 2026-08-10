# Baseline and Intervention Measurement Plan

## Primary operational metric

Unclassified quotation rate:

`unclassified quotations / eligible quotations issued`

Report the count and percentage. Never report the percentage without the
denominator.

## Secondary metrics

- accepted rate;
- declined rate;
- deferred rate;
- expired rate;
- median time to recorded decision;
- number of quotations with a known loss reason;
- follow-up attempts per quotation;
- estimated staff minutes per quotation;
- unnecessary follow-ups avoided;
- high-value quotations left unclassified;
- participant-reported workflow burden.

## Required periods

- baseline start and end;
- intervention start;
- observation end;
- persistence check date.

## Required context

- participant role;
- business-size band;
- quotation-volume band;
- main job categories;
- lead-source mix;
- repeat versus new-customer mix;
- existing software;
- staffing or workload changes;
- holiday periods;
- major pricing changes;
- unusual marketing campaigns;
- changes to quotation format;
- other known confounders.

## Comparison rules

Prefer within-business comparison using the same inclusion rules.

Do not compare:

- different quotation populations without disclosure;
- raw totals when the number of quotations changed materially;
- periods with known operational disruption without caveat;
- accepted revenue without considering quote value and job mix.

## Effect reporting

Every report must state:

- outcome before;
- outcome after;
- absolute change;
- percentage-point change where applicable;
- direction;
- denominator;
- persistence period;
- confidence level as a qualitative judgement;
- known confounders;
- whether the result is observational or supports a stronger inference.

## Example bounded interpretation

> Unclassified outcomes fell from 8 of 19 quotations during baseline to 4 of 21
> during the intervention, a reduction of approximately 23 percentage points.
> The intervention period contained a larger share of repeat customers, so the
> result is promising but observational. The workflow was still in use at the
> day-30 check.

## Required claim boundary

All Stage 4G v0.2 operational measurements must retain:

- `taxonomy_status: separate_operational_measurement`
- `validation_log_import_allowed: false`
- `claim_boundary: observational_not_causal`

## Negative-result treatment

A null or negative result must be retained. Examples:

- no reduction in unclassified outcomes;
- more staff time required;
- customers reacted poorly;
- the contractor stopped using the workflow;
- existing software was already sufficient;
- improvement disappeared after support ended.
