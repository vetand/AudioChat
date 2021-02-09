import json
import socket
import numpy as np
import threading
import time as timemodule
import sounddevice as sd
import os
from protocol import Protocol, DataType

class Client:
    def __init__(self, channels, rate, chunk_size):
        self._serverIP = '52.91.214.221'
        self._chunk_length = 11360
        self._server_port = 4750
        self._current_room_number = -1
        self._talking_mode = False
        self._pid = os.getpid()

        self._prev_received_chunk_lock = threading.Lock()
        self._prev_received_chunk = b''

        self._output_status = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._output_stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._input_stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._name = 'Guest'
        self.closed = False
        self._change_room_request = None
        self._other_users = {"room_0": "", "room_1": "", "room_2": ""}
        
        success = self.connect_to_server()
        threading.Thread(target = self._handle_server).start()

    def change_name(self, name):
        self._name = name

    def connect_to_server(self):
        try:
            self._output_status.connect((self._serverIP, self._server_port))
            return True
        except Exception as e:
            print("Failed to connect the server!")
            return False

    def pull_other_users(self):
        message = json.dumps({})
        message = Protocol(dataType = DataType.UserListRequest, \
                           data = message.encode(encoding = 'UTF-8'))
        self._output_status.sendall(message.out())

    def change_room(self, room_number):
        message = json.dumps({'name': self._name, 'room': room_number, 'pid': self._pid})
        message = Protocol(dataType = DataType.ChangeRoomRequest, \
                           data = message.encode(encoding = 'UTF-8'))
        self._output_status.sendall(message.out())

        while self._change_room_request is None:
            timemodule.sleep(0.2)

        answer = self._change_room_request
        self._change_room_request = None
        return answer
    
    def _handle_server(self):
        while True:
            try:
                raw_response = Protocol(datapacket = self._output_status.recv(1024))
                decoder = json.JSONDecoder()
                response, _ = decoder.raw_decode(raw_response.data.decode(encoding = 'UTF-8'))
            except Exception as e:
                break

            if raw_response.DataType == DataType.ChangeRoomRequest:
                if response['verdict'] == 'ok':
                    print('Room changed successfully to {}'.format(response['room']))
                    if 'outcoming port' in response:
                        # first time any room was accepted, 
                        # create streaming channels and start listen to server
                        self._output_stream.connect((self._serverIP, self._server_port + 1))
                        self._input_stream.connect((self._serverIP, self._server_port + 2))
                        threading.Thread(target = self._unpack_data).start()
                    self._current_room_number = response['room']
                    self._change_room_request = True
                else:
                    print('This name already exists!')
                    self._change_room_request = False

            elif raw_response.DataType == DataType.UserListRequest:
                self._other_users = response

    def _unpack_data(self):
        while True:
            try:
                data = self._input_stream.recv(self._chunk_length)
                with self._prev_received_chunk_lock:
                    if not data:
                        self._prev_received_chunk = b''
                    else:
                        self._prev_received_chunk += data
            except Exception as e:
                break

    def _send_chunk(self, data):
        if self._current_room_number != -1 and self._talking_mode:
            try:
                self._output_stream.sendall(data)
            except Exception as e:
                return

    def set_talking_mode(self):
        self._talking_mode = True

    def turn_down_talking_mode(self):
        self._talking_mode = False

    def callback(self, indata, outdata, frames, time, status):
        if self._current_room_number != -1:
            self._send_chunk(indata)
            with self._prev_received_chunk_lock:
                received = np.frombuffer(self._prev_received_chunk, dtype = 'float32')
                received.reshape(len(received))
                if len(received > self._chunk_length):
                    received = received[:self._chunk_length]
                if self._chunk_length - len(received) > 0:
                    zeros = np.zeros(self._chunk_length - len(received))
                    outdata[:] = np.concatenate((received, zeros), \
                            axis = None).reshape((self._chunk_length, 1))
                else:
                    outdata[:] = received.reshape((self._chunk_length, 1))
                self._prev_received_chunk = b''

    def drop_room(self):
        self._current_room_number = -1

    def get_room_number(self):
        return self._current_room_number

    def shutdown(self):
        try:
            self._output_stream.close()
            self._input_stream.close()
            self._output_status.close()
            self.closed = True
        except Exception:
            pass
            