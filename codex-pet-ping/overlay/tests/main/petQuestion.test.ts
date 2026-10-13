import { describe, expect, it, vi } from 'vitest';
import { petRequest, PetQuestions, type PetRequest } from '../../src/main/petQuestion';
import type { SharedPing } from '../../src/main/overlayManager';

const ping: SharedPing = { id: 'needvision', displayId: 2, x: 320, y: 200 };
const dip = { x: -1280, y: 0, width: 1280, height: 720 };
const physical = { x: -1920, y: -120, width: 1920, height: 1080 };

describe('pet screenshot coordinates', () => {
  it('uses the selected monitor and its DPI, including negative desktop origins', () => {
    expect(petRequest(ping, dip, physical)).toMatchObject({
      left: -1920, top: -120, width: 1920, height: 1080, markX: 480, markY: 300, radius: 45,
    });
  });
  it('keeps rounding at the bottom-right edge inside the image', () => {
    expect(petRequest({ ...ping, x: 1279.99, y: 719.99 }, dip, physical)).toMatchObject({ markX: 1919, markY: 1079 });
  });
  it('rejects missing or invalid screen geometry before capturing', () => {
    for (const x of [-1, 1280, Infinity, NaN]) expect(() => petRequest({ ...ping, x }, dip, physical)).toThrow();
    expect(() => petRequest(ping, { ...dip, width: 0 }, physical)).toThrow();
  });
});

function fixture(send = vi.fn<(_: PetRequest) => Promise<void>>().mockResolvedValue()) {
  const options = {
    enabled: () => true, platform: 'win32', request: vi.fn(() => petRequest(ping, dip, physical)), send,
    active: vi.fn(), error: vi.fn(),
  };
  return { options, questions: new PetQuestions(options) };
}

describe('pet question handoff', () => {
  it('only captures enabled, local Need Vision pings on Windows', async () => {
    const { options, questions } = fixture();
    expect(await questions.ask({ ...ping, id: 'danger' })).toBe('ignored');
    expect(await questions.ask({ ...ping, id: 'missing' })).toBe('ignored');
    options.enabled = () => false;
    expect(await questions.ask(ping)).toBe('ignored');
    options.enabled = () => true;
    options.platform = 'darwin';
    expect(await questions.ask(ping)).toBe('ignored');
    expect(options.request).not.toHaveBeenCalled();
    expect(options.send).not.toHaveBeenCalled();
  });
  it('drops duplicates while a question is being handed off', async () => {
    let finish!: () => void;
    const send = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    const { options, questions } = fixture(send);
    const first = questions.ask(ping);
    expect(await questions.ask(ping)).toBe('busy');
    expect(send).toHaveBeenCalledTimes(1);
    finish();
    expect(await first).toBe('sent');
    expect(options.active.mock.calls).toEqual([[true], [false]]);
  });
  it('restores input and overlays before showing an error and allows the next attempt', async () => {
    const send = vi.fn<(_: PetRequest) => Promise<void>>().mockRejectedValueOnce(new Error('Pet has a draft.')).mockResolvedValue();
    const { options, questions } = fixture(send);
    expect(await questions.ask(ping)).toBe('failed');
    expect(options.active.mock.calls).toEqual([[true], [false]]);
    expect(options.error).toHaveBeenCalledWith('Pet has a draft.');
    expect(options.active.mock.invocationCallOrder[1]).toBeLessThan(options.error.mock.invocationCallOrder[0]);
    expect(await questions.ask(ping)).toBe('sent');
  });
});
