
import test from "node:test";
import assert from "node:assert/strict";
import { redactSensitiveData } from "../src/security.js";

test("redacts passwords and passenger names", () => {
  const result = redactSensitiveData({
    action: "login",
    password: "secret123",
    passengerName: "Test User"
  });

  assert.equal(result.action, "login");
  assert.equal(result.password, "[REDACTED]");
  assert.equal(result.passengerName, "[REDACTED]");
});

test("redacts sensitive fields in nested objects", () => {
  const result = redactSensitiveData({
    event: "booking",
    details: {
      otp: "123456",
      trainNumber: "12001"
    }
  });

  assert.equal(result.details.otp, "[REDACTED]");
  assert.equal(result.details.trainNumber, "12001");
});

test("does not modify the original object", () => {
  const input = { password: "secret123" };
  redactSensitiveData(input);

  assert.equal(input.password, "secret123");
});

test("redacts common sensitive field names", () => {
  const result = redactSensitiveData({
    phone: "9999999999",
    email: "test@example.com",
    token: "secret-token",
    cookie: "session-cookie",
    paymentDetails: {
      cardNumber: "4111111111111111",
      cvv: "123"
    },
    trainNumber: "12001"
  });

  assert.equal(result.phone, "[REDACTED]");
  assert.equal(result.email, "[REDACTED]");
  assert.equal(result.token, "[REDACTED]");
  assert.equal(result.cookie, "[REDACTED]");
  assert.equal(result.paymentDetails.cardNumber, "[REDACTED]");
  assert.equal(result.paymentDetails.cvv, "[REDACTED]");
  assert.equal(result.trainNumber, "12001");
});
