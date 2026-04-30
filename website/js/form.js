/**
 * Accessory Masters — Contact Form Handler
 *
 * Submits to the Cloudflare Worker proxy at /api/form-submit,
 * which forwards to GoHighLevel with server-side auth.
 */

const FORM_CONFIG = {
  apiUrl: "/api/form-submit",
};

/**
 * Attach handlers once DOM is ready.
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("contactForm");
  if (!form) return;

  form.addEventListener("submit", handleSubmit);
});

/* ---------- Validation helpers ---------- */

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showError(input, message) {
  clearError(input);
  input.classList.add("border-red-400");
  const span = document.createElement("span");
  span.className = "form-error text-red-400 text-xs mt-1 block";
  span.textContent = message;
  input.parentNode.appendChild(span);
}

function clearError(input) {
  input.classList.remove("border-red-400");
  const existing = input.parentNode.querySelector(".form-error");
  if (existing) existing.remove();
}

function clearAllErrors(form) {
  form.querySelectorAll(".form-error").forEach((el) => el.remove());
  form
    .querySelectorAll(".border-red-400")
    .forEach((el) => el.classList.remove("border-red-400"));
}

/* ---------- Submit handler ---------- */

async function handleSubmit(e) {
  e.preventDefault();
  const form = e.target;

  clearAllErrors(form);

  const firstName = form.querySelector('[name="firstName"]');
  const lastName = form.querySelector('[name="lastName"]');
  const email = form.querySelector('[name="email"]');
  const phone = form.querySelector('[name="phone"]');

  let valid = true;

  if (!firstName.value.trim()) {
    showError(firstName, "First name is required.");
    valid = false;
  }
  if (!lastName.value.trim()) {
    showError(lastName, "Last name is required.");
    valid = false;
  }
  if (!email.value.trim()) {
    showError(email, "Email is required.");
    valid = false;
  } else if (!isValidEmail(email.value.trim())) {
    showError(email, "Enter a valid email address.");
    valid = false;
  }

  if (!valid) return;

  const submitBtn = form.querySelector('[type="submit"]');
  const originalText = submitBtn.textContent;

  // Loading state
  submitBtn.disabled = true;
  submitBtn.textContent = "Sending…";
  submitBtn.classList.add("opacity-60", "cursor-not-allowed");

  const payload = {
    name: `${firstName.value.trim()} ${lastName.value.trim()}`,
    email: email.value.trim(),
    phone: phone.value.trim(),
  };

  try {
    await submitForm(payload);
    showSuccess(form);
  } catch (err) {
    console.error("Form submission error:", err);
    showFormError(form);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = originalText;
    submitBtn.classList.remove("opacity-60", "cursor-not-allowed");
  }
}

/* ---------- API call ---------- */

async function submitForm(payload) {
  const response = await fetch(FORM_CONFIG.apiUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/* ---------- UI feedback ---------- */

function showSuccess(form) {
  const msg = form.querySelector("#formSuccess");
  const err = form.querySelector("#formError");
  if (err) err.classList.add("hidden");
  if (msg) msg.classList.remove("hidden");
  form.reset();
}

function showFormError(form) {
  const msg = form.querySelector("#formError");
  const suc = form.querySelector("#formSuccess");
  if (suc) suc.classList.add("hidden");
  if (msg) msg.classList.remove("hidden");
}
