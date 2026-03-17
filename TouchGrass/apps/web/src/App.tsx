import React, { useEffect, useState } from 'react';
import { WSClient } from './wsClient';
import { ServerToClientEvent } from '@chat/core';

const wsClient = new WSClient();

export const App: React.FC = () => {
  const [messages, setMessages] = useState<string[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    wsClient.connect('ws://localhost:4000');
    wsClient.onEvent((event: ServerToClientEvent) => {
      if (event.type === 'NEW_MESSAGE') {
        setMessages((prev) => [...prev, event.payload.message.content]);
      }
    });

    // simple auth for now
    wsClient.send({ type: 'AUTH_LOGIN', payload: { token: 'demo-token' } });
    wsClient.send({ type: 'JOIN_ROOM', payload: { roomId: 'general' } });
  }, []);

  const sendMessage = () => {
    wsClient.send({
      type: 'SEND_MESSAGE',
      payload: { roomId: 'general', content: input },
    });
    setInput('');
  };

  return (
    <div>
      <h1>Chat – Web</h1>
      <div>
        {messages.map((m, i) => (
          <div key={i}>{m}</div>
        ))}
      </div>
      <input value={input} onChange={(e) => setInput(e.target.value)} />
      <button onClick={sendMessage}>Send</button>
    </div>
  );
};
