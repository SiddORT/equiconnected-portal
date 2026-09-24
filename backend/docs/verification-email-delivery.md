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

The development runtime also has the default `PUBLIC_APP_URL` of
`http://localhost:5000`; that is a verification-link destination mismatch for
emails sent from a remotely accessed app, independent of SMTP handoff. Check
the deployed environment's public app URL separately before shipping; the
development configuration does not establish production configuration.

Future delivery attempts record only allow-listed categories: connection,
TLS negotiation, authentication, sender rejection, recipient rejection,
handoff, missing host, or message-logo load. The admin email history displays
these categories without raw server responses, credentials, or token URLs.
If SMTP accepted a message but final outcome recording failed, an unresolved
pending attempt remains rather than a fabricated failure.