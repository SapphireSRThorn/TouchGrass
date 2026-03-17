import React, { useEffect, useState } from 'react';
import { SafeAreaView, Text, TextInput, Button, FlatList } from 'react-native';
import { WSClient } from '@chat/core-mobile-ws'; // or reuse same wsClient with small tweaks
import { ServerToClientEvent } from '@chat/core';

const wsClient = new WSClient();

export default function App() {
  const [messages, setMessages] = useState<string[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    wsClient.connect('ws://10.0.2.2:4000'); // emulator localhost
    wsClient.onEvent((event: ServerToClientEvent) => {
      if (event.type === 'NEW_MESSAGE') {
        setMessages((prev) => [...prev, event.payload.message.content]);
      }
    });

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
    <SafeAreaView style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 24, marginBottom: 8 }}>Chat – Mobile</Text>
      <FlatList
        data={messages}
        keyExtractor={(_, i) => i.toString()}
        renderItem={({ item }) => <Text>{item}</Text>}
      />
      <TextInput
        value={input}
        onChangeText={setInput}
        style={{ borderWidth: 1, marginVertical: 8, padding: 8 }}
      />
      <Button title="Send" onPress={sendMessage} />
    </SafeAreaView>
  );
}
