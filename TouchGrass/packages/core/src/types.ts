export type UserId = string;
export type RoomId = string;
export type MessageId = string;

export interface User {
  id: UserId;
  username: string;
  displayName: string;
  avatarUrl?: string;
  createdAt: string;
  roles: string[]; // e.g. ['admin', 'mod', 'member']
}

export interface Room {
  id: RoomId;
  name: string;
  topic?: string;
  isPrivate: boolean;
  createdAt: string;
  createdBy: UserId;
}

export interface Message {
  id: MessageId;
  roomId: RoomId;
  senderId: UserId;
  content: string;          // encrypted or plaintext depending on room
  createdAt: string;
  editedAt?: string;
  deletedAt?: string;
}

export interface ModerationEvent {
  id: string;
  type: 'REPORT' | 'BAN' | 'MUTE';
  targetUserId: UserId;
  actorUserId: UserId;
  reason: string;
  createdAt: string;
}

