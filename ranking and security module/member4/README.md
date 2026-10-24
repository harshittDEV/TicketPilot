# Member 4 — Train Ranking & Security Module

## Overview
This module provides train-option ranking and sensitive-data redaction utilities for the Tatkal booking agent project.

## Features
- Filters train options by route, Tatkal quota, eligibility, and verified availability.
- Ranks eligible options by total fare, then duration.
- Redacts sensitive fields from logs or structured data.
- Includes automated tests using Node.js's built-in test runner.

## Setup
Requirements: Node.js installed.

```bash
npm test
```

## Test Results
- Total tests: 11
- Passed: 11
- Failed: 0

## Integration Notes
The main agent must supply verified train data and correctly set eligibility and availability fields based on actual observations.

This module does not log in to IRCTC, handle CAPTCHA, process payments, or complete bookings by itself. Live integration must be tested separately.

## Security
See `SECURITY.md` for security and privacy guidelines.
