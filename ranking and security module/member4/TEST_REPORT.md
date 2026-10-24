# Test Report — Member 4 Module

## Test Execution
- Command: `npm test`
- Test framework: Node.js built-in test runner
- Total tests: 11
- Passed: 11
- Failed: 0

## Train Ranking Tests
- Selects the cheapest verified eligible train.
- Rejects unverified availability.
- Handles an empty train list.
- Rejects invalid input.
- Rejects missing and invalid fares.
- Rejects incorrect route or quota.
- Uses shorter duration when fares are equal.

## Security Tests
- Redacts passwords and passenger names.
- Redacts sensitive fields in nested objects.
- Preserves the original input object.
- Redacts common sensitive field names.

## Status
All 11 automated tests passed locally.

**Note:** These results validate the utility functions using test data. Live IRCTC integration and end-to-end booking have not been verified by these tests.