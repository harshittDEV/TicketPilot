
import test from "node:test";
import assert from "node:assert/strict";
import { rankTrains } from "../src/trainRanker.js";

const sampleTrains = [
  {
    trainNumber: "12001",
    origin: "Roorkee",
    destination: "Haridwar",
    quota: "TATKAL",
    eligible: true,
    availabilityVerified: true,
    totalFare: 450,
    durationMinutes: 45
  },
  {
    trainNumber: "12002",
    origin: "Roorkee",
    destination: "Haridwar",
    quota: "TATKAL",
    eligible: true,
    availabilityVerified: true,
    totalFare: 380,
    durationMinutes: 60
  },
  {
    trainNumber: "12003",
    origin: "Roorkee",
    destination: "Haridwar",
    quota: "TATKAL",
    eligible: true,
    availabilityVerified: false,
    totalFare: 200,
    durationMinutes: 40
  }
];

test("selects cheapest verified eligible train", () => {
  const result = rankTrains(sampleTrains);

  assert.equal(result.status, "OPTIONS_FOUND");
  assert.equal(result.selected.trainNumber, "12002");
  assert.equal(result.selected.totalFare, 380);
});

test("rejects unverified availability", () => {
  const result = rankTrains([sampleTrains[2]]);

  assert.equal(result.selected, null);
  assert.equal(result.status, "NO_VERIFIED_OPTIONS");
});

test("handles empty train list", () => {
  const result = rankTrains([]);

  assert.equal(result.selected, null);
  assert.equal(result.ranked.length, 0);
});

test("rejects invalid input", () => {
  assert.throws(() => rankTrains(null), TypeError);
});

test("rejects missing and invalid fares", () => {
  const invalidTrains = [
    {
      ...sampleTrains[0],
      trainNumber: "20001",
      totalFare: undefined
    },
    {
      ...sampleTrains[0],
      trainNumber: "20002",
      totalFare: -50
    }
  ];

  const result = rankTrains(invalidTrains);

  assert.equal(result.selected, null);
});

test("rejects trains with the wrong route or quota", () => {
  const wrongRoute = {
    ...sampleTrains[0],
    destination: "Delhi"
  };

  const wrongQuota = {
    ...sampleTrains[1],
    quota: "GENERAL"
  };

  const result = rankTrains([wrongRoute, wrongQuota]);

  assert.equal(result.selected, null);
});

test("uses shorter duration when fares are equal", () => {
  const slower = {
    ...sampleTrains[0],
    trainNumber: "20010",
    totalFare: 400,
    durationMinutes: 90
  };

  const faster = {
    ...sampleTrains[1],
    trainNumber: "20011",
    totalFare: 400,
    durationMinutes: 45
  };

  const result = rankTrains([slower, faster]);

  assert.equal(result.selected.trainNumber, "20011");
});
