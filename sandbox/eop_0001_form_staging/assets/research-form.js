"use strict";

const form = document.querySelector("#research-form");
const comment = document.querySelector("#bounded-comment");
const commentCount = document.querySelector("#comment-count");
const errorPanel = document.querySelector("#form-errors");
const resultPanel = document.querySelector("#research-result");
const tokenOutput = document.querySelector("#participant-token");
const downloadButton = document.querySelector("#download-research");
const contactLink = document.querySelector("#contact-link");

let generatedPayload = null;

const EMAIL_PATTERN = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i;
const PHONE_PATTERN = /(?:\+?\d[\s().-]*){10,15}/;
const ADDRESS_MARKERS = /\b(postcode|postal code|street|road|avenue|drive|lane|close|court|house number|customer name)\b/i;

function selectedValue(name) {
  const input = document.querySelector(`input[name="${name}"]:checked`);
  return input ? input.value : "";
}

function selectedCheckboxes(groupName) {
  return Array.from(
    document.querySelectorAll(
      `[data-group="${groupName}"] input[type="checkbox"]:checked`
    )
  ).map((input) => input.value);
}

function randomToken(prefix) {
  const bytes = new Uint8Array(12);
  window.crypto.getRandomValues(bytes);
  const value = Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return `${prefix}-${value}`;
}

function utcTimestamp() {
  return new Date().toISOString();
}

function showErrors(errors) {
  errorPanel.textContent = "";
  if (errors.length === 0) {
    errorPanel.hidden = true;
    return;
  }

  const title = document.createElement("strong");
  title.textContent = "Please correct the following:";
  errorPanel.appendChild(title);

  const list = document.createElement("ul");
  for (const error of errors) {
    const item = document.createElement("li");
    item.textContent = error;
    list.appendChild(item);
  }
  errorPanel.appendChild(list);
  errorPanel.hidden = false;
  errorPanel.focus();
}

function validateComment(value) {
  const errors = [];
  if (EMAIL_PATTERN.test(value)) {
    errors.push("Remove the email address from the optional comment.");
  }
  if (PHONE_PATTERN.test(value)) {
    errors.push("Remove the phone number from the optional comment.");
  }
  if (ADDRESS_MARKERS.test(value)) {
    errors.push(
      "Remove possible address or customer-identifying information from the optional comment."
    );
  }
  return errors;
}

function enforceGroupLimit(event) {
  const group = event.currentTarget;
  const limit = Number(group.dataset.limit);
  const checked = group.querySelectorAll('input[type="checkbox"]:checked');
  if (checked.length <= limit) {
    return;
  }
  event.target.checked = false;
  window.alert(`Choose no more than ${limit} options.`);
}


function enforceExclusiveChoice(event) {
  const group = event.currentTarget;
  const exclusiveValue = group.dataset.exclusiveValue;
  const changed = event.target;
  if (!(changed instanceof HTMLInputElement) || changed.type !== "checkbox") {
    return;
  }

  const boxes = Array.from(
    group.querySelectorAll('input[type="checkbox"]')
  );
  const exclusive = boxes.find((box) => box.value === exclusiveValue);
  if (!exclusive) {
    return;
  }

  if (changed.value === exclusiveValue && changed.checked) {
    for (const box of boxes) {
      if (box !== exclusive) {
        box.checked = false;
      }
    }
    return;
  }

  if (changed.checked) {
    exclusive.checked = false;
  }
}

function buildSummary(data) {
  const parts = [
    `role=${data.participant_role}`,
    `uk_region=${data.uk_region}`,
    `business_size=${data.business_size}`,
    `monthly_quotes=${data.monthly_quotes}`,
    `recorded_outcomes=${data.recorded_outcomes.join("|") || "none_selected"}`,
    `unclassified_share=${data.unclassified_share}`,
    `follow_up_methods=${data.follow_up_methods.join("|") || "none_selected"}`,
    `barriers=${data.barriers.join("|") || "none_selected"}`,
    `decision_inputs=${data.decision_inputs.join("|") || "none_selected"}`,
    `most_valuable_outcome=${data.most_valuable_outcome}`,
    `next_action_interest=${data.next_action_interest}`,
  ];

  if (data.bounded_comment) {
    parts.push(`bounded_comment=${data.bounded_comment}`);
  }
  return parts.join("; ");
}

function downloadJson(filename, payload) {
  const blob = new Blob(
    [JSON.stringify(payload, null, 2) + "\n"],
    { type: "application/json" }
  );
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

comment.addEventListener("input", () => {
  commentCount.textContent = String(comment.value.length);
});

for (const group of document.querySelectorAll(".limited-group")) {
  group.addEventListener("change", enforceGroupLimit);
}

for (const group of document.querySelectorAll(".exclusive-group")) {
  group.addEventListener("change", enforceExclusiveChoice);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  resultPanel.hidden = true;

  const errors = [];
  if (!form.checkValidity()) {
    errors.push("Complete all required questions and the consent checkbox.");
  }

  const participantRole = selectedValue("participant_role");
  if (participantRole === "not_target_market") {
    errors.push(
      "This preview response is outside the intended participant group."
    );
  }

  const boundedComment = comment.value.trim();
  errors.push(...validateComment(boundedComment));

  if (errors.length > 0) {
    showErrors(errors);
    return;
  }

  showErrors([]);

  const participantToken = randomToken("FPVPT");
  const submissionId = randomToken("FPVS");
  const sourceReference = randomToken("public-form");

  const structuredResponse = {
    participant_role: participantRole,
    uk_region: document.querySelector("#uk-region").value,
    business_size: document.querySelector("#business-size").value,
    monthly_quotes: document.querySelector("#monthly-quotes").value,
    recorded_outcomes: selectedCheckboxes("recorded_outcomes"),
    unclassified_share: document.querySelector("#unclassified-share").value,
    follow_up_methods: selectedCheckboxes("follow_up_methods"),
    barriers: selectedCheckboxes("barriers"),
    decision_inputs: selectedCheckboxes("decision_inputs"),
    most_valuable_outcome: document.querySelector(
      "#most-valuable-outcome"
    ).value,
    next_action_interest: document.querySelector("#next-action-interest").value,
    bounded_comment: boundedComment,
  };

  generatedPayload = {
    staging_only: true,
    live_evidence_eligible: false,
    campaign_id: document.querySelector("#campaign-id").value,
    submission_id: submissionId,
    participant_token: participantToken,
    participant_role: participantRole,
    capture_method: "public_form",
    evidence_kind: "structured_public_response",
    attestation_basis: "participant_self_attested",
    evidence_summary: buildSummary(structuredResponse),
    source_reference: sourceReference,
    consent_to_research: true,
    consent_version: document.querySelector("#consent-version").value,
    question_set_version: document.querySelector(
      "#question-set-version"
    ).value,
    signal_strength: "weak",
    supports_validation: false,
    self_submission: false,
    synthetic_submission: true,
    captured_at: utcTimestamp(),
    structured_response: structuredResponse,
  };

  tokenOutput.textContent = participantToken;
  contactLink.href = `contact.html#participant_token=${encodeURIComponent(
    participantToken
  )}`;
  resultPanel.hidden = false;
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
});

downloadButton.addEventListener("click", () => {
  if (!generatedPayload) {
    return;
  }
  downloadJson(
    `${generatedPayload.submission_id}-preview-research.json`,
    generatedPayload
  );
});
