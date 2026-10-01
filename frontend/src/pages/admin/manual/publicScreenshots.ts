export const publicScreenshots = {
  'public-find-care-start': [{
    src: '/manual/public-find-care-start.webp',
    alt: 'EquiConnected homepage with the member and provider starting points and Find a provider navigation.',
    caption: 'Start here: choose the member directory or the provider-registration journey. Public content does not disclose member-only provider contact details.',
  }],
  'public-contact-equiconnected': [{
    src: '/manual/public-contact-equiconnected.webp',
    alt: 'Contact EquiConnected form filled with a clearly labelled sample visitor name, reserved example.test email, enquiry type, and sample message.',
    caption: 'Contact the team: select your enquiry type and choose Send message. Phone is optional; this is not a provider conversation or emergency request.',
  }, {
    src: '/manual/public-contact-equiconnected-result.webp',
    alt: 'The real contact form confirmation says Thank you for reaching out after an isolated sample submission.',
    caption: 'Expected result: the enquiry is accepted and the page explains that the team will respond by email. This demonstration sent no email.',
  }],
  'public-subscribe-updates': [{
    src: '/manual/public-subscribe-updates.webp',
    alt: 'Get EquiConnected updates form with a sample role choice and reserved example.test subscriber email.',
    caption: 'Get updates: choose Your role, enter an email, then choose Keep me posted. A subscription is not a member account.',
  }, {
    src: '/manual/public-subscribe-updates-result.webp',
    alt: 'The updates form is replaced by its real success state after a synthetic subscription.',
    caption: 'Expected result: a successful updates request replaces the form with confirmation. This sample did not create a subscriber or deliver an email.',
  }],
} satisfies Record<string, {src: string; alt: string; caption: string}[]>;