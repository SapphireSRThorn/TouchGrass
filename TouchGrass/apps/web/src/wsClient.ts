import { ClientToServerEvent, ServerToClientEvent } from '@chat/core';

export class WSClient {
  private ws?: WebSocket;
  private listeners: ((event: ServerToClientEvent) => void)[] = [];

  connect(url: string) {
    this.ws = new WebSocket(url);
    this.ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data.toString()) as ServerToClientEvent;
      this.listeners.forEach((l) => l(event));
    };
  }

  onEvent(listener: (event: ServerToClientEvent) => void) {
    this.listeners.push(listener);
  }

  send(event: ClientToServerEvent) {
    this.ws?.send(JSON.stringify(event));
  }
}
