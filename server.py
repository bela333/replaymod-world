import json
import struct

LISTEN_PORT = 3333
JOIN_PORT = 3334

#https://gist.github.com/nickelpro/7312782
def pack_varint(val):
	total = b''
	if val < 0:
		val = (1<<32)+val
	while val>=0x80:
		bits = val&0x7F
		val >>= 7
		total += struct.pack('B', (0x80|bits))
	bits = val&0x7F
	total += struct.pack('B', bits)
	return total

def read_packet(f):
    #Replaymod packet format: time (u32) + packet_length (u32) + packet
    data = f.read(8)
    if len(data) == 0:
        return None
    (time, length) = struct.unpack(">II", data)
    data = f.read(length)
    return (time, length, data)

def convert_packet(f):
    packet = read_packet(f)
    if packet is None:
        return None
    (time, length, data) = packet
    #Minecraft packet format: packet_length (varint) + packet
    return pack_varint(length) + data


def listen(socket, zip):
    conn, addr = socket.accept()
    try:
        with zip.open("recording.tmcpr") as f:
            #Read and convert packets from `f` until None
            packets = iter(partial(convert_packet, f), None) 
            for packet in packets:
                conn.sendall(packet)
    finally:
        print("Closing server")
        conn.close()

def join(socket, zip):
    try:
        #Load protocol version
        with zip.open("metaData.json") as f:
            data = json.loads(f.read())
            protocol_version = data['protocol']
        server_address = b'127.0.0.1'
        #https://wiki.vg/Protocol#Handshake
        packet = pack_varint(0) + pack_varint(protocol_version) + pack_varint(len(server_address)) + server_address + struct.pack('>H', LISTEN_PORT) + pack_varint(2)
        packet = pack_varint(len(packet)) + packet
        
        socket.sendall(packet)
        
        #Wait until EOF
        while len(socket.recv(4096)) > 0:
            pass
    finally:
        print("Closing client")
        socket.close()


if __name__ == "__main__":
    import sys
    import socket
    from functools import partial
    import zipfile
    import threading


    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.bind(('0.0.0.0', LISTEN_PORT))
    listen_socket.listen(1)

    join_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    join_socket.connect(('127.0.0.1', JOIN_PORT))

    with zipfile.ZipFile(sys.argv[1]) as zip:
        listen_thread = threading.Thread(target=listen, args=(listen_socket, zip))
        join_thread = threading.Thread(target=join, args=(join_socket, zip))

        listen_thread.start()
        join_thread.start()

        listen_thread.join()
        join_thread.join()