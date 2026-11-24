const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}

export const CameraIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M4 7h3l1.5-2h7L17 7h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1Z" />
    <circle cx="12" cy="13" r="3.2" />
  </svg>
)

export const CheckIcon = (props) => (
  <svg {...base} {...props}>
    <path d="m5 12.5 4.2 4.2L19 7" />
  </svg>
)

export const AlertIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 4 3 20h18L12 4Z" />
    <path d="M12 10v4" />
    <path d="M12 17h.01" />
  </svg>
)

export const CopyIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="8" y="8" width="12" height="12" rx="2" />
    <path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" />
  </svg>
)

export const DownloadIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 4v11" />
    <path d="m7.5 11 4.5 4.5L16.5 11" />
    <path d="M5 20h14" />
  </svg>
)

export const EditIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M4 20h4l10-10a2.8 2.8 0 0 0-4-4L4 16v4Z" />
    <path d="m13.5 6.5 4 4" />
  </svg>
)

export const SettingsIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1-2.8 2.8-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21h-4v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1L4.3 17l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3v-4h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8L4.3 7 7.1 4.2l.1.1a1.6 1.6 0 0 0 1.8.3 1.6 1.6 0 0 0 1-1.5V3h4v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1L19.7 7l-.1.1a1.6 1.6 0 0 0-.3 1.8 1.6 1.6 0 0 0 1.5 1h.2v4h-.2a1.6 1.6 0 0 0-1.4 1.1Z" />
  </svg>
)

export const BoltIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M13 2 4.5 13.5H11L10 22l8.5-11.5H12L13 2Z" />
  </svg>
)

export const XIcon = (props) => (
  <svg {...base} {...props}>
    <path d="m6 6 12 12M18 6 6 18" />
  </svg>
)

export const RefreshIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M20 11a8 8 0 1 0-2.3 6.4" />
    <path d="M20 5v6h-6" />
  </svg>
)

export const BulbIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M9 18h6" />
    <path d="M10 21h4" />
    <path d="M8.5 15.2A6 6 0 1 1 16 15a2 2 0 0 0-.7 1.5V17H8.7v-.4a2 2 0 0 0-.2-1.4Z" />
  </svg>
)

export const SheetIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="M4 9h16M4 15h16M10 3v18" />
  </svg>
)

export const BondIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <circle cx="8" cy="12" r="1.6" />
    <path d="M12 10h6M12 14h6" />
  </svg>
)
