export type ClientToServerEvent =
  | { type: 'AUTH_LOGIN'; payload: { token: string } }
  | { type: 'JOIN_ROOM'; payload: { roomId: string } }
  | { type: 'LEAVE_ROOM'; payload: { roomId: string } }
  | { type: 'SEND_MESSAGE'; payload: { roomId: string; content: string } }
  | { type: 'REPORT_MESSAGE'; payload: { messageId: string; reason: string } };

export type ServerToClientEvent =
  | { type: 'AUTH_OK'; payload: { userId: string } }
  | { type: 'ROOM_JOINED'; payload: { roomId: string } }
  | { type: 'NEW_MESSAGE'; payload: { message: any } }
  | { type: 'MESSAGE_UPDATED'; payload: { message: any } }
  | { type: 'MODERATION_NOTICE'; payload: { text: string } }
  | { type: 'ERROR'; payload: { code: string; message: string } };
