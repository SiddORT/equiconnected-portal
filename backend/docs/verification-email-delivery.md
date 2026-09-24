# Verification email handoff diagnosis

On September 24, 2026, the development runtime had an SMTP host, port 587,
STARTTLS enabled, a configured username and password, and an explicit sender.
These checks confirm only configuration presence, not connectivity, sender
authorization, or successful login. The existing delivery history contained
five successful verification handoffs and two failed handoffs. Both failures
were stored as the generic “Unable to deliver email.” The available records and
workflow logs do not contain the SMTP stage or a failed request trace, so **the
cause of those two failures cannot be determined retrospectively**. No live
SMTP call or email to an unintended recipient was made for this diagnosis.

The development runtime originally used the default `PUBLIC_APP_URL` of
`http://localhost:5000`, which produced links inaccessible to remote visitors.
The development environment now sets `PUBLIC_APP_URL` to the HTTPS frontend
preview origin. If the preview domain changes, update the development
environment variable as well; localhost remains the default only for a local
non-deployed run.

At the time of this check the project had **no active published deployment**,
so there was no verified production URL to configure or test. After publishing,
retrieve the live primary URL from the deployment details and set
`PUBLIC_APP_URL` in the **production** environment to that exact HTTPS frontend
origin (no path, query, or trailing token). Republish for the setting to take
effect, then check the frontend routes `/verify-email`,
`/provider/invitations/<token>`, and `/provider/setup-password?token=<token>`
using synthetic tokens only. Do not trigger an email to test the destination.
The backend now refuses to start when a deployed runtime (or staging/production
environment) has a localhost or non-HTTPS `PUBLIC_APP_URL`; this guard also
applies if `ENVIRONMENT` was left as `development` in a deployment.

Future delivery attempts record only allow-listed categories: connection,
TLS negotiation, authentication, sender rejection, recipient rejection,
handoff, missing host, or message-logo load. The admin email history displays
these categories without raw server responses, credentials, or token URLs.
If SMTP accepted a message but final outcome recording failed, an unresolved
pending attempt remains rather than a fabricated failure.