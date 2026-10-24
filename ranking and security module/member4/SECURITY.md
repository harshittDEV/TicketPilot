
# Security Guidelines — Member 4

## 1. Credential Protection
- Never hardcode passwords, OTPs, API keys or payment details.
- Never expose credentials in source code, screenshots or logs.
- Use environment variables or an approved secure credential store.

## 2. Passenger Data Protection
- Store passenger details only when required and with authorization.
- Restrict access to the authorized team member.
- Never commit passenger details to GitHub.
- Remove unnecessary copies after the task.

## 3. Run Log Safety
- Redact sensitive information before saving logs.
- Check screenshots and recordings for exposed credentials.
- Record actions, timestamps, outcomes and reasons without storing secrets.

## 4. Payment Safety
- Pause for explicit human approval before final payment.
- Never store payment credentials in project files.
- Verify booking status before retrying an uncertain transaction.

## 5. Error Recovery
- Retry temporary errors with bounded backoff.
- Do not blindly repeat a booking or payment.
- If blocked by CAPTCHA or an anti-bot challenge, pause for human assistance.

## 6. Testing
- Use mock data for automated tests.
- Do not use real passenger data in test fixtures.
- Record actual test results in TEST_REPORT.md.
