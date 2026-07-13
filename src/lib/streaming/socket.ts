'use client';
import { io, type Socket } from 'socket.io-client';

const BFF_WS = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io(BFF_WS, {
      autoConnect: false,
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 8000,
    });
  }
  return socket;
}

export function destroySocket(): void {
  socket?.disconnect();
  socket = null;
}
