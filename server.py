import grpc
import chat_pb2
import chat_pb2_grpc
from concurrent import futures
import sqlite3
import uuid
import time
import threading
import queue
from collections import defaultdict

class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        self.conn = sqlite3.connect('chat.db', check_same_thread=False)
        self.create_tables()
        self.subscribers = defaultdict(list)
        self.lock = threading.Lock()

    def create_tables(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    room_id TEXT,
                    author_id TEXT,
                    content TEXT,
                    timestamp INTEGER,
                    FOREIGN KEY (room_id) REFERENCES rooms (id)
                )
            ''')

    def CreateRoom(self, request, context):
        room_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute('INSERT INTO rooms (id, name) VALUES (?, ?)',
                           (room_id, request.name))
        print(f"Созданная комната: {room_id} ({request.name})")
        return chat_pb2.CreateRoomResponse(
            room=chat_pb2.ChatRoom(id=room_id, name=request.name)
        )

    def ListRooms(self, request, context):
        with self.conn:
            cursor = self.conn.execute('SELECT id, name FROM rooms')
            rooms = [chat_pb2.ChatRoom(id=row[0], name=row[1]) for row in cursor.fetchall()]
        print(f"Выведено {len(rooms)} комнат")
        return chat_pb2.ListRoomsResponse(rooms=rooms)

    def JoinRoom(self, request, context):
        room_id = request.room_id
        message_queue = queue.Queue()
        with self.lock:
            self.subscribers[room_id].append(message_queue)
        print(f"Клиент {request.author_id} присоединился к комнате {room_id}")

        try:
            with self.conn:
                cursor = self.conn.execute(
                    'SELECT id, room_id, author_id, content, timestamp FROM messages WHERE room_id = ? ORDER BY timestamp',
                    (room_id,)
                )
                messages = [
                    chat_pb2.Message(id=row[0], room_id=row[1], author_id=row[2], content=row[3], timestamp=row[4])
                    for row in cursor.fetchall()
                ]
                for message in messages:
                    yield chat_pb2.JoinRoomResponse(message=message)
                print(f"Отправлено {len(messages)} сообщений из истории для {request.author_id} в комнате {room_id}")

            while context.is_active():
                try:
                    message = message_queue.get(timeout=1)
                    yield chat_pb2.JoinRoomResponse(message=message)
                except queue.Empty:
                    continue
        except Exception as e:
            print(f"Ошибка присоединения у {request.author_id} в комнате {room_id}: {e}")
        finally:
            with self.lock:
                if message_queue in self.subscribers[room_id]:
                    self.subscribers[room_id].remove(message_queue)
                print(f"Клиент {request.author_id} покинул комнату {room_id}")

    def SendMessage(self, request_iterator, context):
        for request in request_iterator:
            message_id = str(uuid.uuid4())
            timestamp = int(time.time())
            
            with self.conn:
                self.conn.execute(
                    'INSERT INTO messages (id, room_id, author_id, content, timestamp) VALUES (?, ?, ?, ?, ?)',
                    (message_id, request.room_id, request.author_id, request.content, timestamp)
                )
            
            message = chat_pb2.Message(
                id=message_id,
                room_id=request.room_id,
                author_id=request.author_id,
                content=request.content,
                timestamp=timestamp
            )
            
            with self.lock:
                subscribers = self.subscribers[request.room_id].copy()
                print(f"Трансляция новых сообщений для {len(subscribers)} пользователей в комнате {request.room_id}")
                for subscriber in subscribers:
                    try:
                        subscriber.put(message)
                    except Exception as e:
                        print(f"Ошибка отправки в комнате {request.room_id}: {e}")
                        self.subscribers[request.room_id].remove(subscriber)
            
            yield chat_pb2.SendMessageResponse(message=message)

    def GetHistory(self, request, context):
        with self.conn:
            cursor = self.conn.execute(
                'SELECT id, room_id, author_id, content, timestamp FROM messages WHERE room_id = ? ORDER BY timestamp',
                (request.room_id,)
            )
            messages = [
                chat_pb2.Message(id=row[0], room_id=row[1], author_id=row[2], content=row[3], timestamp=row[4])
                for row in cursor.fetchall()
            ]
        print(f"Получено {len(messages)} сообщений для комнаты {request.room_id}")
        return chat_pb2.GetHistoryResponse(messages=messages)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    server.add_insecure_port('[::]:50051')
    print("Server started on port 50051")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()