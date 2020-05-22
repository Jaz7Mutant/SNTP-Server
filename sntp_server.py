import argparse
import queue
import socket
import struct
import sys
from datetime import date
from threading import Thread
from time import time

TIME_OFFSET = (date(1970, 1, 1) - date(1900, 1, 1)).days * 24 * 3600


class SNTPMessage:
    def __init__(self, is_correct: bool, version: int = 3, mode: int = 3,
                 originate_time: int = 0, receive_time: float = 0):
        self.correct = is_correct
        self.raw = b''
        self.time_offset = 0
        self.leap_indicator = 0
        self.version = version
        self.mode = mode
        self.stratum = 0
        self.poll = 0
        self.precision = 0
        self.root_delay = 0
        self.root_dispersion = 0
        self.ref_id = 0
        self.ref_time = 0
        self.originate_time = originate_time
        self.receive_time = receive_time
        self.transmit_time = 0

    def get_reply(self) -> bytes:
        first = (self.leap_indicator << 6) | (self.version << 3) | self.mode
        receive_time = self.format_time(self.receive_time + self.time_offset)
        transmit_time = self.format_time(
            time() + TIME_OFFSET + self.time_offset
        )
        return struct.pack(
            '>3Bb5I3Q', first, self.stratum, self.poll, self.precision,
            0, 0, 0, 0, 0, self.originate_time, receive_time, transmit_time
        )

    @staticmethod
    def format_time(raw_time):
        return int(raw_time * (2 ** 32))


class Server:
    def __init__(self, port: int, time_delay: int = 0, thread_count: int = 1):
        self.port = port
        self.time_delay = time_delay
        self.requests = queue.Queue()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', port))
        self.receiver = Thread(target=self.receive_request, daemon=True)
        self.workers = [
            Thread(target=self.reply_to_request, daemon=True)
            for _ in range(thread_count)
        ]

    def __enter__(self):
        [worker.start() for worker in self.workers]
        self.receiver.start()
        print(
            f'Server is working...'
            f'\nPort: {self.port}'
            f'\nTime delay: {self.time_delay}s\n'
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.socket.close()
        print('Exiting...')
        if exc_tb is not None:
            raise

    def reply_to_request(self):
        while True:
            try:
                sntp_message, address = self.requests.get(block=False)
            except queue.Empty:
                pass
            else:
                if sntp_message:
                    sntp_message.time_offset = self.time_delay
                    self.socket.sendto(sntp_message.get_reply(), address)

    def receive_request(self):
        while True:
            try:
                data, address = self.socket.recvfrom(1024)
                self.requests.put((self.format_request(data), address))
                print(f'Got request from: {address[0]} : {address[1]}\n')
            except socket.error:
                pass

    @staticmethod
    def format_request(data: bytes):
        if len(data) < 48:
            print('Got incorrect request')
            return SNTPMessage(False)
        version = (data[0] & 56) >> 3
        mode = data[0] & 7
        originate_time = int.from_bytes(data[40:48], 'big')
        if mode != 3:
            return None
        return SNTPMessage(
            True, version, 4, originate_time, time() + TIME_OFFSET)


def parse_args():
    parser = argparse.ArgumentParser(description="SNTP server with time delay")
    parser.add_argument(
        '-d', '--delay', action='store', dest='delay', type=int, default=0,
        help='Time delay is seconds')
    parser.add_argument(
        '-p', '--port', action='store', dest='port', type=int, default=123,
        help='Server port')
    return parser.parse_args()


def main():
    namespace = parse_args()
    if not 1 < namespace.port < 65535:
        print('Incorrect port', file=sys.stderr)
        exit(1)
    with Server(namespace.port, namespace.delay, thread_count=10):
        try:
            while True:
                pass
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
