import grpc
import chat_pb2
import chat_pb2_grpc
import threading
import time
import os

def join_room(stub, room_id, author_id):
    def listen_for_messages():
        try:
            messages = []
            for response in stub.JoinRoom(chat_pb2.JoinRoomRequest(room_id=room_id, author_id=author_id)):
                messages.append(f"[{response.message.timestamp}] {response.message.author_id}: {response.message.content}")
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"\n=== История комнаты {room_id} ===")
                for msg in messages:
                    print(msg)
        except grpc.RpcError as e:
            print(f"Поток JoinRoom закрыт: {e}")

    thread = threading.Thread(target=listen_for_messages)
    thread.daemon = True
    thread.start()
    return thread

def send_messages(stub, room_id, author_id):
    def message_generator():
        while True:
            content = input(f"\nВведите сообщение для комнаты {room_id} (или 'quit' для выхода): ")
            if content.lower() == 'quit':
                break
            yield chat_pb2.SendMessageRequest(room_id=room_id, author_id=author_id, content=content)

    responses = stub.SendMessage(message_generator())
    for response in responses:
        print(f"Сообщение отправлено: {response.message.content}")

def main():
    author_id = input("Введите имя пользователя: ").strip()
    if not author_id:
        print("Имя пользователя не может быть пустым. Выход.")
        return

    with grpc.insecure_channel('localhost:50051') as channel:
        stub = chat_pb2_grpc.ChatServiceStub(channel)
        current_room_id = None
        join_thread = None

        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\n=== Меню чата ===")
            print("1. Создать комнату")
            print("2. Список комнат")
            print("3. Присоединиться к комнате")
            print("4. Получить историю комнаты")
            print("5. Выход")
            choice = input("Выберите действие (1-5): ").strip()

            if choice == '1':
                room_name = input("Введите название комнаты: ").strip()
                if not room_name:
                    print("Название комнаты не может быть пустым.")
                    continue
                room_response = stub.CreateRoom(chat_pb2.CreateRoomRequest(name=room_name))
                print(f"Создана комната: {room_response.room.name} ({room_response.room.id})")
                input("Нажмите Enter для продолжения...")

            elif choice == '2':
                rooms_response = stub.ListRooms(chat_pb2.ListRoomsRequest())
                print("\nДоступные комнаты:")
                if not rooms_response.rooms:
                    print("Нет доступных комнат.")
                for room in rooms_response.rooms:
                    print(f"- {room.name} ({room.id})")
                input("Нажмите Enter для продолжения...")

            elif choice == '3':
                if join_thread and join_thread.is_alive():
                    print("Вы уже в комнате. Сначала выйдите из текущей комнаты.")
                    input("Нажмите Enter для продолжения...")
                    continue
                room_id = input("Введите ID комнаты для присоединения: ").strip()
                if not room_id:
                    print("ID комнаты не может быть пустым.")
                    input("Нажмите Enter для продолжения...")
                    continue
                rooms_response = stub.ListRooms(chat_pb2.ListRoomsRequest())
                rooms = [room.id for room in rooms_response.rooms]
                if room_id not in rooms:
                    print(f"Ошибка: Комната {room_id} не существует.")
                    input("Нажмите Enter для продолжения...")
                    continue
                current_room_id = room_id
                join_thread = join_room(stub, room_id, author_id)
                send_messages(stub, room_id, author_id)
                join_thread = None
                current_room_id = None

            elif choice == '4':
                room_id = input("Введите ID комнаты для получения истории: ").strip()
                if not room_id:
                    print("ID комнаты не может быть пустым.")
                    input("Нажмите Enter для продолжения...")
                    continue
                rooms_response = stub.ListRooms(chat_pb2.ListRoomsRequest())
                rooms = [room.id for room in rooms_response.rooms]
                if room_id not in rooms:
                    print(f"Ошибка: Комната {room_id} не существует.")
                    input("Нажмите Enter для продолжения...")
                    continue
                history_response = stub.GetHistory(chat_pb2.GetHistoryRequest(room_id=room_id))
                print(f"\nИстория комнаты {room_id}:")
                if not history_response.messages:
                    print("В этой комнате нет сообщений.")
                for msg in history_response.messages:
                    print(f"[{msg.timestamp}] {msg.author_id}: {msg.content}")
                input("Нажмите Enter для продолжения...")

            elif choice == '5':
                print("Выход из чата.")
                break

            else:
                print("Неверный выбор. Выберите 1-5.")
                input("Нажмите Enter для продолжения...")

if __name__ == '__main__':
    main()