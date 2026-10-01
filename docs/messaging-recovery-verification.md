# Development messaging recovery verification

Verified on 2026-10-01. This report concerns the development preview only.

## Configuration and existing history

- Before provisioning, effective development settings lacked both dedicated
  messaging values and the encryption validator rejected configuration.
- Aggregate development database inspection found zero conversations and zero
  messages. No historical messaging keys needed recovery.
- After protected-secret correction, the existing encryption validator passed.
  The development backend was restarted and came up cleanly.
- Read-only eligibility inspection found three published, active providers with
  unambiguous eligible account links. No real account/link/approval state changed.
  The exact provider in the original screenshot was not individually identified;
  provider eligibility remains independent of encryption configuration.

## Verification

- Existing messaging, edge, and notification regression suites: 39 backend tests
  passed using an isolated test schema and isolated SMTP.
- Existing provider-profile and private-message UI suites: 29 frontend tests
  passed with constrained test workers.
- The isolated browser/API smoke check passed using the protected development
  messaging settings and the real shipped frontend.
- A labelled synthetic verified member saw **Message provider**, reviewed their
  contact preview, and had to consent before sending. The API independently
  rejected a consent-free request without persisting a conversation.
- The intended, explicitly linked synthetic provider received the message,
  viewed the consented contact snapshot, and replied. Both participants' inboxes
  and the member's receipt of the reply were checked.
- Two message bodies and the contact snapshot were stored as encrypted
  envelopes, not plaintext. A fresh backend process reopened both messages and
  the provider's snapshot with the same protected settings.
- An unrelated synthetic member could not read the thread.
- Missing and invalid messaging keys rejected sending, preserved direct-contact
  controls, and persisted no unauthorized conversation.
- Three email notification handoffs were counted by no-op SMTP stubs. No email
  was sent to real or synthetic recipients.
- The disposable schema and processes were removed. Development public tables
  still contained zero conversations and zero messages afterward.

The screenshots in `screenshots/private-messaging-isolated-smoke/` are genuine
captures of the shipped UI using isolated, labelled synthetic data.

## Deployment boundary

Production settings, production data, and deployed behavior were not inspected
or changed. An operator must verify the deployment's own protected keyring and
active ID, recover and retain any keys required by production history, and
separately approve any production restart/deployment. Passing development checks
does not establish production readiness. Preserve a protected recovery copy of
the provisioned keys outside database backups.