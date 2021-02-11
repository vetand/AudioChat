import socket
import threading
import numpy as np
import json
import time
from protocol import Protocol, DataType

class ClientInfo:
    def __init__(self, room, name):
        self.name = name
        self.room = room
        self.stream = None
        self.prev_talking = -1

class Server:
    def __init__(self):
        self._number_of_rooms = 3
        self._incoming_status_port = 4750
        self._chunk_length = 512

        self._current_clients_lock = threading.Lock()
        self._current_clients = dict()

        self._start_server()

    def _start_server(self):
        self._myIP = '0.0.0.0'

        self._incoming_status = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._incoming_status.bind((self._myIP, self._incoming_status_port))
        self._incoming_status.listen(100)

        self._incoming_stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._incoming_stream.bind((self._myIP, self._incoming_status_port + 1))
        self._incoming_stream.listen(100)

        self._outcoming_stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._outcoming_stream.bind((self._myIP, self._incoming_status_port + 2))
        self._outcoming_stream.listen(100)

        print("Bind ports {}-{}".format((self._myIP, self._incoming_status_port), \
                                        (self._myIP, self._incoming_status_port + 2)))
        threading.Thread(target = self._handle_new_clients).start()

    def _send_nack(self, stream, address):
        response = json.dumps({'verdict': 'nope'})
        response = Protocol(dataType = DataType.ChangeRoomRequest, \
                            data = response.encode(encoding = 'UTF-8'))
        stream.sendall(response.out())

    def _handle_client_status(self, stream, address):
        while True:
            try:
                data = stream.recv(1024)
            except Exception:
                break

            if not data:
                break

            raw_message = Protocol(datapacket = data)
            decoder = json.JSONDecoder()
            try:
                message, _ = decoder.raw_decode(raw_message.data.decode(encoding = 'UTF-8'))
            except Exception as e:
                print("Buffer error!")
                continue

            if raw_message.DataType == DataType.ChangeRoomRequest:
                room = message['room'] - 1
                with self._current_clients_lock:
                    if (address[0], message['pid']) in self._current_clients.keys():
                        self._current_clients[(address[0], message['pid'])].name = message['name']
                        self._current_clients[(address[0], message['pid'])].room = room
                        response = json.dumps({'verdict': 'ok', 'room': message['room'] })
                        response = Protocol(dataType = DataType.ChangeRoomRequest, \
                                            data = response.encode(encoding = 'UTF-8'))
                        stream.sendall(response.out())
                        print("User with name {} changed room to {}".format(message['name'],
                                                                            message['room']))
                        continue

                self._current_clients[(address[0], message['pid'])] = \
                                        ClientInfo(room, message['name'])

                threading.Thread(target = self._handle_client_traffic, \
                                 args = (address, room, message['name'], message['pid'],)).start()
                response = json.dumps({'verdict': 'ok', \
                                       'room': message['room'], \
                                       'incoming port': self._incoming_status_port + 1, \
                                       'outcoming port': self._incoming_status_port + 2, \
                                     })
                print("New receiver in room {} -> {}, {}".format(message['room'], \
                                                                 message['name'], address))
                response = Protocol(dataType = DataType.ChangeRoomRequest, \
                                    data = response.encode(encoding = 'UTF-8'))
                stream.sendall(response.out())

            elif raw_message.DataType == DataType.UserListRequest:
                with self._current_clients_lock:
                    answer = dict()
                    answer['room_0'] = ""
                    answer['room_1'] = ""
                    answer['room_2'] = ""
                    for other_address, pid in self._current_clients.keys():
                        name = self._current_clients[(other_address, pid)].name
                        room = self._current_clients[(other_address, pid)].room
                        interval = time.time() - \
                                   self._current_clients[(other_address, pid)].prev_talking
                        if interval < 0.5:
                            answer['room_' + str(room)] += name + " (talking)\n"
                        else:
                            answer['room_' + str(room)] += name + "\n"
                    response = json.dumps(answer)
                    response = Protocol(dataType = DataType.UserListRequest, \
                                        data = response.encode(encoding = 'UTF-8'))
                    stream.sendall(response.out())

    def _handle_new_clients(self):
        while True:
            stream, address = self._incoming_status.accept()
            threading.Thread(target = self._handle_client_status,
                             args = (stream, address,)).start()

    def _erase_client(self, address, pid):
        try:
            name = self._current_clients[(address, pid)].name
            self._current_clients[(address, pid)].stream.close()
            del self._current_clients[(address, pid)]
            print("Client with name {} disconnected!".format(name))
        except Exception as e:
            pass

    def _handle_client_traffic(self, address, room, name, pid):
        with self._current_clients_lock:
            incoming_stream, addr = self._incoming_stream.accept()
            outcoming_stream, addr = self._outcoming_stream.accept()
            self._current_clients[(address[0], pid)].stream = outcoming_stream

        while True:
            try:
                data = incoming_stream.recv(self._chunk_length)
            except Exception as e:
                break

            with self._current_clients_lock:
                try:
                    room = self._current_clients[(address[0], pid)].room
                    self._current_clients[(address[0], pid)].prev_talking = time.time()
                except Exception as e:
                    pass

            if not data:
                with self._current_clients_lock:
                    self._erase_client(address[0], pid)
                    break

            with self._current_clients_lock:
                to_erase = []
                for other_address, other_pid in self._current_clients.keys():
                    other_room = self._current_clients[(other_address, other_pid)].room
                    if other_pid == pid or other_room != room:
                        continue
                    try:
                        self._current_clients[(other_address, other_pid)].stream.sendall(data)
                    except Exception as e:
                        to_erase.append((other_address, other_pid))
                for client in to_erase:
                    self._erase_client(client[0], client[1])

server = Server()