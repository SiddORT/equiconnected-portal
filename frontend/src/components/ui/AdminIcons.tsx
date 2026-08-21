import type { SVGProps } from 'react';

export interface AdminIconProps extends SVGProps<SVGSVGElement> {
  name: string;
}

function Icon({ name, children, ...props }: AdminIconProps & { children: React.ReactNode }) {
  return (
    <svg
      {...props}
      data-icon={name}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export function MoreHorizontalIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="more-horizontal" {...props}>
      <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function ViewIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="view" {...props}>
      <path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.5" />
    </Icon>
  );
}

export function EditIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="edit" {...props}>
      <path d="m14.5 5.5 4 4" />
      <path d="M4 20h4l10.8-10.8a2.8 2.8 0 0 0-4-4L4 16v4Z" />
    </Icon>
  );
}

export function ActivateIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="activate" {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12 2.3 2.3 4.7-5" />
    </Icon>
  );
}

export function DeactivateIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="deactivate" {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.5 12h7" />
    </Icon>
  );
}

export function PublishIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="publish" {...props}>
      <path d="M5 19h14" />
      <path d="M12 16V5" />
      <path d="m7.5 9.5 4.5-4.5 4.5 4.5" />
    </Icon>
  );
}

export function UnpublishIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="unpublish" {...props}>
      <path d="M5 19h14" />
      <path d="M12 5v11" />
      <path d="m7.5 12.5 4.5 4.5 4.5-4.5" />
    </Icon>
  );
}

export function SendIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="send" {...props}>
      <path d="m21 3-7.2 18-3.2-7.6L3 10.2 21 3Z" />
      <path d="M10.6 13.4 21 3" />
    </Icon>
  );
}

export function ResendIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="resend" {...props}>
      <path d="M20 11a8 8 0 0 0-14.7-4L3 10" />
      <path d="M3 5v5h5" />
      <path d="M4 13a8 8 0 0 0 14.7 4L21 14" />
      <path d="M21 19v-5h-5" />
    </Icon>
  );
}

export function CancelIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="cancel" {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </Icon>
  );
}

export function CopyLinkIcon(props: Omit<AdminIconProps, 'name'>) {
  return (
    <Icon name="copy-link" {...props}>
      <path d="M9 15 7.8 16.2a3.4 3.4 0 0 1-4.8-4.8l3-3a3.4 3.4 0 0 1 4.8 0" />
      <path d="m15 9 1.2-1.2a3.4 3.4 0 0 1 4.8 4.8l-3 3a3.4 3.4 0 0 1-4.8 0" />
      <path d="m8 12 8-0.1" />
    </Icon>
  );
}