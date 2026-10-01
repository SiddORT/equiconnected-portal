import { analyticsScreenshots } from './analyticsScreenshots';
import { publicScreenshots } from './publicScreenshots';
import { roleScreenshots } from './roleScreenshots';
import { adminScreenshots } from './adminScreenshots';

export const manualScreenshots: Record<string, { src: string; alt: string; caption: string }[]> = {
  ...analyticsScreenshots,
  ...publicScreenshots,
  ...roleScreenshots,
  ...adminScreenshots,
  'dashboard-analytics-glossary': [{
    src: '/manual/provider-record-details.webp',
    alt: 'Sample administrator provider detail showing distinct Active and Published listing labels.',
    caption: 'Status examples: Active is the provider’s management state; Published is a separate directory-display setting. Neither replaces the other.',
  }],
};