/// <reference types="node" />

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ADULT_HORSE_ASSET_URL } from './HorseScene';

describe('adult horse asset boundary', () => {
  it('ships a non-empty local GLB at the loader path', () => {
    const assetPath = resolve(process.cwd(), 'public/models/horse-adult.glb');
    const asset = readFileSync(assetPath);

    expect(ADULT_HORSE_ASSET_URL).toBe('/models/horse-adult.glb');
    expect(asset.subarray(0, 4).toString('ascii')).toBe('glTF');
    expect(asset.byteLength).toBeGreaterThan(100_000);
  });
});