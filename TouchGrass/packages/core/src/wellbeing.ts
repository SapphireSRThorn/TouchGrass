type BreakCallback = () => void;

export class BreakReminder {
  private activeMs = 0;
  private lastActivity = Date.now();
  private intervalId?: number;
  private readonly thresholdMs: number;
  private readonly onBreak: BreakCallback;

  constructor(hours: number, onBreak: BreakCallback) {
    this.thresholdMs = hours * 60 * 60 * 1000;
    this.onBreak = onBreak;
  }

  start() {
    this.lastActivity = Date.now();
    this.intervalId = setInterval(() => this.tick(), 1000) as unknown as number;
  }

  stop() {
    if (this.intervalId) clearInterval(this.intervalId);
  }

  notifyActivity() {
    const now = Date.now();
    this.activeMs += now - this.lastActivity;
    this.lastActivity = now;
  }

  private tick() {
    const now = Date.now();
    this.activeMs += now - this.lastActivity;
    this.lastActivity = now;

    if (this.activeMs >= this.thresholdMs) {
      this.activeMs = 0;
      this.onBreak();
    }
  }
}
