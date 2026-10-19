import { vi } from 'vitest';

/**
 * A scriptable stand-in for the browser WebSocket (forum live replies).
 * Install it in `beforeEach` — the config's `mockReset: true` wipes anything
 * set up at module scope. The test drives the server side: `open()`,
 * `message(obj)`, `serverClose(code)`.
 */
export class FakeWs {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readonly url: string;
  readonly sent: string[] = [];
  readyState = FakeWs.CONNECTING;
  closedByClient = false;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string, instances: FakeWs[]) {
    this.url = url;
    instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  /** Client-initiated close: recorded; the client has already detached. */
  close(): void {
    this.closedByClient = true;
    this.readyState = FakeWs.CLOSED;
  }

  open(): void {
    this.readyState = FakeWs.OPEN;
    this.onopen?.(new Event('open'));
  }

  message(payload: unknown): void {
    const data = typeof payload === 'string' ? payload : JSON.stringify(payload);
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  serverClose(code: number): void {
    this.readyState = FakeWs.CLOSED;
    this.onclose?.(new CloseEvent('close', { code }));
  }
}

/** Replace `globalThis.WebSocket`; returns the list every new socket joins. */
export function installFakeWebSocket(): FakeWs[] {
  const instances: FakeWs[] = [];
  class BoundFakeWs extends FakeWs {
    constructor(url: string) {
      super(url, instances);
    }
  }
  vi.stubGlobal('WebSocket', BoundFakeWs);
  return instances;
}
