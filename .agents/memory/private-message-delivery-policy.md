---
name: Private message delivery policy
description: Why private-message notification recovery treats uncertain SMTP handoffs differently from safe pre-send failures.
---

Recover pending notification intents only when no SMTP handoff was attempted.
Never automatically retry a claimed notification with an unknown handoff
outcome; leave its outcome unresolved for an operator to investigate.

**Why:** Retrying after a lost SMTP result can repeat acknowledgements even
when message submission itself is correctly deduplicated. Message acceptance
must not depend on SMTP or delivery accounting, so notification ambiguity is
separate from a failed message send.

**How to apply:** Preserve durable notification intent in the message
transaction, claim delivery before SMTP, and retry only failures known to
precede SMTP. Do not advise participants to resend a saved message to repair
email delivery.