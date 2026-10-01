import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { adminTopics } from './adminTopics';
import { analyticsTopics } from './analyticsTopics';
import { gettingStartedTopics, memberTopics, providerTopics, troubleshootingTopics } from './roleTopics';
import { manualScreenshots } from './screenshots';

const topics = [...gettingStartedTopics, ...adminTopics, ...providerTopics, ...memberTopics, ...analyticsTopics, ...troubleshootingTopics];

describe('Delivered manual coverage and bundled illustrations', () => {
  it('keeps topic anchors unique and every task self-explanatory', () => {
    expect(new Set(topics.map((topic) => topic.id)).size).toBe(topics.length);
    for (const topic of topics) {
      expect(topic.id).toMatch(/^[a-z][a-z0-9-]+$/);
      for (const field of ['title', 'purpose', 'where', 'who', 'result'] as const) {
        expect(topic[field].trim(), `${topic.id}: ${field}`).not.toBe('');
      }
      expect(topic.prerequisites.length, topic.id).toBeGreaterThan(0);
      expect(topic.steps.length, topic.id).toBeGreaterThan(0);
      expect(topic.restrictions.length, topic.id).toBeGreaterThan(0);
    }
  });

  it('covers the operational dashboard separately from each analytics domain', () => {
    const ids = analyticsTopics.map((topic) => topic.id);
    for (const id of [
      'admin-dashboard-overview-and-activity', 'admin-dashboard-provider-locations-map',
      'admin-dashboard-visiting-provider-calendar', 'analytics-workspace-and-date-controls',
      'analytics-website-traffic', 'analytics-member-registration-cohorts',
      'analytics-provider-inventory-applications-invitations', 'analytics-reviews-and-private-feedback',
      'analytics-enquiries-and-subscribers', 'analytics-trends-detail-tables-and-coverage',
      'analytics-csv-exports', 'dashboard-analytics-glossary',
    ]) expect(ids).toContain(id);
  });

  it('maps illustrations only to existing topics and bundles genuine readable image assets', () => {
    expect(Object.keys(manualScreenshots).length).toBeGreaterThan(30);
    for (const [id, images] of Object.entries(manualScreenshots)) {
      expect(topics.some((topic) => topic.id === id), `Unknown illustrated topic ${id}`).toBe(true);
      expect(images.length, id).toBeGreaterThan(0);
      for (const image of images) {
        expect(image.src).toMatch(/^\/manual\/[a-z0-9-]+\.webp$/);
        expect(image.alt.trim()).not.toBe('');
        expect(image.caption.trim()).not.toBe('');
        const file = resolve(process.cwd(), 'public', image.src.slice(1));
        expect(existsSync(file), `Missing deployed asset ${image.src}`).toBe(true);
        const bytes = readFileSync(file);
        expect(bytes.subarray(0, 4).toString()).toBe('RIFF');
        expect(bytes.subarray(8, 12).toString()).toBe('WEBP');
        expect(bytes.length).toBeGreaterThan(1000);
      }
    }
  });

  it('illustrates every delivered topic rather than leaving workflow coverage implicit', () => {
    for (const topic of topics) {
      expect(manualScreenshots[topic.id]?.length, `No genuine illustration for ${topic.id}`).toBeGreaterThan(0);
    }
  });
});