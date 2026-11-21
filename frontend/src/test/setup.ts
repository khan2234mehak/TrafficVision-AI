import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

class FakeWS {
  static OPEN = 1;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  send = vi.fn();
  close = vi.fn();
}
vi.stubGlobal("WebSocket", FakeWS);
Element.prototype.scrollIntoView = vi.fn();
HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;
