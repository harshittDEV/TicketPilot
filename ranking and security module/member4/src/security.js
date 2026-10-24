
const SENSITIVE_KEYS = [
  "password",
  "otp",
  "token",
  "authorization",
  "cookie",
  "cardnumber",
  "cvv",
  "upiid",
  "passengername",
  "phonenumber",
  "phone",
  "email",
  "dateofbirth",
  "passport"
];

export function redactSensitiveData(value) {
  if (Array.isArray(value)) {
    return value.map(redactSensitiveData);
  }

  if (value === null || typeof value !== "object") {
    return value;
  }

  const safe = {};

  for (const [key, item] of Object.entries(value)) {
    const normalizedKey = key.toLowerCase().replace(/[^a-z0-9]/g, "");

    if (SENSITIVE_KEYS.some((s) => normalizedKey.includes(s))) {
      safe[key] = "[REDACTED]";
    } else {
      safe[key] = redactSensitiveData(item);
    }
  }

  return safe;
}
