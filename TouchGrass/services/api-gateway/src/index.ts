import http from 'http';
import express from 'express';
import { WebSocketServer } from 'ws';
import { ClientToServerEvent, ServerToClientEvent } from '@chat/core';

const app = express();
app.use(express.json());

// Simple health check
app.get('/health', (_req, res) => res.json({ status: 'ok' }));

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

type AuthedSocket = WebSocket & { userId?: string };

wss.on('connection', (ws: AuthedSocket) => {
  ws.on('message', (data) => {
    let event: ClientToServerEvent;
    try {
      event = JSON.parse(data.toString());
    } catch {
      send(ws, { type: 'ERROR', payload: { code: 'BAD_JSON', message: 'Invalid JSON' } });
      return;
    }

    handleEvent(ws, event);
  });
});

function send(ws: WebSocket, event: ServerToClientEvent) {
  ws.send(JSON.stringify(event));
}

async function handleEvent(ws: AuthedSocket, event: ClientToServerEvent) {
  switch (event.type) {
    case 'AUTH_LOGIN': {
      // TODO: verify token via auth-service
      const userId = await fakeVerifyToken(event.payload.token);
      ws.userId = userId;
      send(ws, { type: 'AUTH_OK', payload: { userId } });
      return;
    }

    case 'JOIN_ROOM': {
      if (!ws.userId) return notAuthed(ws);
      // TODO: join room via chat-service
      send(ws, { type: 'ROOM_JOINED', payload: { roomId: event.payload.roomId } });
      return;
    }

    case 'SEND_MESSAGE': {
      if (!ws.userId) return notAuthed(ws);
      // TODO: persist message via chat-service and broadcast
      // For now, echo back
      send(ws, {
        type: 'NEW_MESSAGE',
        payload: {
          message: {
            id: 'temp',
            roomId: event.payload.roomId,
            senderId: ws.userId,
            content: event.payload.content,
            createdAt: new Date().toISOString(),
          },
        },
      });
      return;
    }

    case 'REPORT_MESSAGE': {
      if (!ws.userId) return notAuthed(ws);
      // TODO: forward to moderation-service
      send(ws, {
        type: 'MODERATION_NOTICE',
        payload: { text: 'Report received. Moderators will review.' },
      });
      return;
    }
  }
}

function notAuthed(ws: AuthedSocket) {
  send(ws, {
    type: 'ERROR',
    payload: { code: 'UNAUTHENTICATED', message: 'You must authenticate first.' },
  });
}

async function fakeVerifyToken(token: string): Promise<string> {
  // Replace with real auth-service call
  return `user-${token.slice(0, 6)}`;
}

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => {
  console.log(`API Gateway listening on ${PORT}`);
});
