
# COMP9331 Assignment T2 2020
# Name: Sidney Tandjiria
# Language: Python 3.7

# client.py

from socket import *
import sys
from datetime import datetime
import json
import struct
import threading
import os

t_lock = threading.Condition()

# create an empty contact log file whenever the client is run
with open('z5272671_contactlog.txt', 'w'):
    pass 

# Read in specified port
if len(sys.argv) != 4:
    raise ValueError('Usage: python client.py server_IP server_port client_udp_port')

serverIP = sys.argv[1] # can use localhost for testing

# Parse the port numbers to int
try:
    serverPort = int(sys.argv[2])
    client_udp_port = int(sys.argv[3])
except:
    print("Server port number and client UDP port number must be an integer greater than 1024 (and not 8080).")

# Create the TCP client socket
clientSocket = socket(AF_INET, SOCK_STREAM)

# Establish TCP connection
clientSocket.connect_ex((serverIP, serverPort))

# Initial authentication variables
username_is_valid = False
password_is_valid = False

# Buffers for connection with server
receiving_buffer = b"" # append all incoming messages here
sending_buffer = b"" # append all messages to be sent here

# UDP sockets for beaconing feature
UDP_send_socket = socket(AF_INET, SOCK_DGRAM) # sending socket
UDP_recv_socket = socket(AF_INET, SOCK_DGRAM) # receiving socket
UDP_recv_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1) # avoids the Address already in use error
UDP_recv_socket.bind(('', client_udp_port)) # bind to the port

# Function for sending beacons
def send_beacon(tempID, startTime, endTime, dest_IP, dest_port):
    global UDP_send_socket
    content = json.dumps(dict(tempID = tempID, startTime = startTime, endTime = endTime, version = 1)).encode('utf-8')
    header = struct.pack(">H", len(content)) # encode into 2 bytes (check this)
    message = header + content
    address = (dest_IP, dest_port)
    UDP_send_socket.sendto(message, address)
    print(f"{tempID}, {startTime}, {endTime}.")

# function to remove a record from the contact log
# In the case there are duplicates (due to the same user beaconing more than once with the same tempID)
# then we delete the first occurance
def remove_from_contact_log(logfile, line_to_delete):
    global t_lock
    with t_lock:
        with open(logfile, "r") as f:
            lines = f.readlines()
        deleted = False
        with open(logfile, "w") as f:
            for line in lines:
                if line.strip("\n") == line_to_delete and deleted == False:
                    deleted = True
                else:
                    f.write(line)
        t_lock.notify()

# Function for receiving beacons
def recv_beacon():
    global t_lock
    while(1):
        message, beacon_address = UDP_recv_socket.recvfrom(4069)
        if len(message) >= 2:
            content_length = struct.unpack(">H", message[:2])[0]
            message = message[2:]
            response = json.loads(message.decode('utf-8'))
            tempID = response["tempID"]
            startTime = response["startTime"]
            endTime = response["endTime"]
            # version number doesn't get used
            if (username_is_valid == False) or (password_is_valid == False):
                print(f"\n> received beacon: ")
            else:
                print(f"received beacon: ")
            print(f"{tempID}, {startTime}, {endTime}.")
            currentTime = datetime.now()
            currentTime_str = currentTime.strftime("%d/%m/%Y %H:%M:%S")
            print(f"Current time is: {currentTime_str}.")
            if currentTime >= datetime.strptime(startTime, "%d/%m/%Y %H:%M:%S") and currentTime <= datetime.strptime(endTime, "%d/%m/%Y %H:%M:%S"):
                print('The beacon is valid.')
                with t_lock:
                    with open("z5272671_contactlog.txt", "a") as cl_file: # write to contact log
                        line_add = f"{tempID} {startTime} {endTime}\n"
                        cl_file.write(line_add)
                    t_lock.notify()
                # start a 3 minute timer to remove the line from the contact log
                threading.Timer(180, remove_from_contact_log, args = ["z5272671_contactlog.txt", line_add.strip('\n')]).start()
            else:
                print('The beacon is invalid.')
            if username_is_valid == False:
                print('> Username: ', end = '', flush = True)
            elif password_is_valid == False:
                print('> Password: ', end = '', flush = True)
            else:
                print("> ", end = '', flush = True)

# Checks if command is valid
# Creates the request in json format (content to be delivered)
# Adds on a header
def create_message(command, value):
    if (command == "check_username") or (command == "check_password") or (command == "logout") or (command == "Download_tempID") or (command == "Upload_contact_log"): # check if username exists and if it is blocked, or check pw
        # content saved as json, encoded in utf-8
        content = json.dumps(dict(command = command, value = value)).encode('utf-8')
    else:
        raise ValueError("Command not supported")
    header = struct.pack(">H", len(content)) # encode into 2 bytes (check this)
    message = header + content
    return message

# Checks if the username is valid
while not username_is_valid:
    username = input('> Username: ')
    message = create_message("check_username", username)
    sending_buffer += message
    sent = clientSocket.send(sending_buffer)
    sending_buffer = sending_buffer[sent:]
    # wait for response
    data = clientSocket.recv(4096)
    if data:
        receiving_buffer += data
    else:
        RuntimeError("Connection ended.")
    # Obtain contents from receiving buffer
    if len(receiving_buffer) >= 2:
        content_length = struct.unpack(">H", receiving_buffer[:2])[0]
        receiving_buffer = receiving_buffer[2:] # update to start from contents
        response = json.loads(receiving_buffer.decode('utf-8'))
        receiving_buffer = receiving_buffer[content_length:]
        status = response["status"]
        if status == "BLOCKED":
            print('Your account is blocked due to multiple login failures. Please try again later.')
            clientSocket.close()
            exit()
        username_is_valid = True if status == "OK" else False
        if not username_is_valid:
            print('Invalid username. Try again.')

# Once username is valid, checks if the password is valid
while not password_is_valid:
    password = input('> Password: ')
    message = create_message("check_password", dict(username = username, password = password))
    sending_buffer += message
    sent = clientSocket.send(sending_buffer)
    sending_buffer = sending_buffer[sent:]
    # wait for response
    data = clientSocket.recv(4096)
    if data:
        receiving_buffer += data
    else:
        RuntimeError("Connection ended.")
    # Obtain contents from receiving buffer
    if len(receiving_buffer) >= 2:
        content_length = struct.unpack(">H", receiving_buffer[:2])[0] 
        receiving_buffer = receiving_buffer[2:] # update to start from contents
        response = json.loads(receiving_buffer.decode('utf-8'))
        receiving_buffer = receiving_buffer[content_length:]
        status = response["status"]
        if status == "BLOCKED":
            print('Invalid password. Your account has been blocked. Please try again later.')
            clientSocket.close()
            exit()
        password_is_valid = True if status == "OK" else False
        if not password_is_valid:
            print('Invalid password. Try again.')

# temp ID details
current_tempID = ''
current_tempID_start = ''
current_tempID_end = ''

print("> Welcome to the BlueTrace Simulator!")

udp_recv_thread = threading.Thread(name="RecvBeacon", target = recv_beacon)
udp_recv_thread.daemon = True
udp_recv_thread.start()

# start of main loop which waits for user input
while True:
    user_command = input("> ")
    if user_command == "logout":
        message = create_message("logout", username)
        sending_buffer += message
        sent = clientSocket.send(sending_buffer)
        sending_buffer = sending_buffer[sent:]
        # wait for response
        data = clientSocket.recv(4096)
        if data:
            receiving_buffer += data
        else:
            RuntimeError("Connection ended.")
        # Obtain contents from receiving buffer
        if len(receiving_buffer) >= 2:
            content_length = struct.unpack(">H", receiving_buffer[:2])[0]
            receiving_buffer = receiving_buffer[2:] # update to start from contents
            response = json.loads(receiving_buffer[:content_length].decode('utf-8'))
            receiving_buffer = receiving_buffer[content_length:]
            status = response["status"]
            if status == "OK":
                clientSocket.close()
                exit()
    elif user_command == "Download_tempID":
        message = create_message("Download_tempID", username)
        sending_buffer += message
        sent = clientSocket.send(sending_buffer)
        sending_buffer = sending_buffer[sent:]
        # wait for response
        data = clientSocket.recv(4096)
        if data:
            receiving_buffer += data
        else:
            RuntimeError("Connection ended.")
        # Obtain contents from receiving buffer
        if len(receiving_buffer) >= 2:
            content_length = struct.unpack(">H", receiving_buffer[:2])[0] 
            receiving_buffer = receiving_buffer[2:] # update to start from contents
            response = json.loads(receiving_buffer.decode('utf-8'))
            receiving_buffer = receiving_buffer[content_length:]
            current_tempID = response["status"]["tempID"] 
            current_tempID_start = response["status"]["startTime"]
            current_tempID_end = response["status"]["endTime"]
            print(f"> TempID: {current_tempID}")
    elif user_command == "Upload_contact_log":
        # stop if contact log is empty
        if os.stat("z5272671_contactlog.txt").st_size == 0: 
            print("Contact log is empty. Try again later.")
        else:
            formatted_contactlog = ''
            with open("z5272671_contactlog.txt", "r") as logfile: # write to file
                for line in logfile:
                    tempID, start_date, start_time, end_date, end_time = line.strip('\n').split(' ')
                    formatted_contactlog += f"{tempID}, {start_date} {start_time}, {end_date} {end_time};\n"
            formatted_contactlog = formatted_contactlog.strip('\n')
            print(formatted_contactlog)
            message = create_message("Upload_contact_log", dict(username = username, contactlog = formatted_contactlog))
            sending_buffer += message
            sent = clientSocket.send(sending_buffer)
            sending_buffer = sending_buffer[sent:]
    elif user_command.startswith("Beacon") == True: # starts with the word beacon
        # check if command works
        words = user_command.split(' ')
        # verify if input is correct
        if (len(words) != 3) or (words[0] != "Beacon"):
            print("Error. Invalid command. Beacon usage: Beacon dest_IP dest_port.")
        else:
            dest_IP = words[1]
            try:
                dest_port = int(words[2])
                # check if user already has a tempID
                if not current_tempID:
                    print("Cannot beacon without a valid tempID. Please use Download_tempID to obtain a valid tempID.")
                else:
                    tempID_expiry = datetime.strptime(current_tempID_end, "%d/%m/%Y %H:%M:%S")
                    if tempID_expiry < datetime.now():
                        print("Warning: Beacon will be sent with an expired tempID. Download a new tempID to send a valid beacon.")
                    # attempt to send beacon (could be empty if user has not downloaded one)
                    send_beacon(current_tempID, current_tempID_start, current_tempID_end, dest_IP, dest_port)
            except:
                print("Error. Invalid IP address or destination port. Beacon usage: Beacon dest_IP dest_port.")        
    elif user_command != "":
            print("Error. Invalid command.")

