"use strict";

const form = document.querySelector("#contact-form");
const tokenInput = document.querySelector("#contact-token");
const errorPanel = document.querySelector("#contact-errors");
const resultPanel = document.querySelector("#contact-result");
const downloadButton = document.querySelector("#download-contact");

let generatedPayload = null;

const TOKEN_PATTERN = /^[A-Za-z0-9_.:-]{3,120}$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_PATTERN = /^\+?[0-9 ()-]{7,25}$/;

function selectedValue(name) {
  const input = document.querySelector(`input[name="${name}"]:checked`);
  return input ? input.value : "";
}

function showErrors(errors) {
  errorPanel.textContent = "";
  if (errors.length === 0) {
    errorPanel.hidden = true;
    return;
  }

  const list = document.createElement("ul");
  for (const error of errors) {
    const item = document.createElement("li");
    item.textContent = error;
    list.appendChild(item);
  }
  errorPanel.appendChild(list);
  errorPanel.hidden = false;
}

function readTokenFromFragment() {
  const fragment = window.location.hash.replace(/^#/, "");
  const parameters = new URLSearchParams(fragment);
  const token = parameters.get("participant_token") || "";
  if (TOKEN_PATTERN.test(token)) {
    tokenInput.value = token;
  }
  window.history.replaceState(null, "", "contact.html");
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

readTokenFromFragment();

form.addEventListener("submit", (event) => {
  event.preventDefault();
  resultPanel.hidden = true;

  const errors = [];
  if (!form.checkValidity()) {
    errors.push("Complete all required fields and the contact-consent checkbox.");
  }

  const participantToken = tokenInput.value.trim();
  const method = selectedValue("contact_method");
  const contactValue = document.querySelector("#contact-value").value.trim();

  if (!TOKEN_PATTERN.test(participantToken)) {
    errors.push("Enter a valid participant token.");
  }
  if (method === "email" && !EMAIL_PATTERN.test(contactValue)) {
    errors.push("Enter a valid email address.");
  }
  if (method === "phone" && !PHONE_PATTERN.test(contactValue)) {
    errors.push("Enter a valid phone number.");
  }

  if (errors.length > 0) {
    showErrors(errors);
    return;
  }

  showErrors([]);

  generatedPayload = {
    staging_only: true,
    stage4g_research_capture_allowed: false,
    participant_token: participantToken,
    contact_name: document.querySelector("#contact-name").value.trim(),
    contact_method: method,
    contact_value: contactValue,
    requested_action: document.querySelector("#requested-action").value,
    consent_to_contact: true,
    captured_at: new Date().toISOString(),
  };

  resultPanel.hidden = false;
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
});

downloadButton.addEventListener("click", () => {
  if (!generatedPayload) {
    return;
  }
  downloadJson(
    `${generatedPayload.participant_token}-preview-contact.json`,
    generatedPayload
  );
});
