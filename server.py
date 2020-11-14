
# COMP9331 Assignment T2 2020
# Name: Sidney Tandjiria
# zID: z5272671
# Language: Python 3.7

# server.py

from socket import *
import sys
from datetime import datetime, timedelta
import json
import struct
import threading
from collections import defaultdict
import time
import selectors
import types
import secrets
import string
import pandas as pd
import os

sel = selectors.DefaultSelector()
t_lock = threading.Condition()

# create an empty tempIDs.txt file whenever the server is run
with open('tempIDs.txt', 'w'):
    pass 

# removes a user from the blocked list
def remove_block(user):
    global t_lock
    with t_lock:
        blocked_clients.remove(user)
        print(f"> {user} has been unblocked.")
        t_lock.notify()

# function creates the server's response to a client's request
def create_response(command, value):
    if command == "check_username":
        status = "NOT FOUND" # default
        # check if user is blocked
        if value in blocked_clients:
            status = "BLOCKED"
            print(f"> {value} attempted to log in but is currently blocked.")
        else:    
            # compare against credentials.txt
            with open("credentials.txt", "r") as credentials:
                for line in credentials:
                    user, password = line.strip('\n').split(' ',1)
                    if value == user:
                        status = "OK"
                        attempts[user] = 0 # add to attempts dict
                        break
    elif command == "check_password":
        status = "INCORRECT"
        # compare against credentials.txt
        with open("credentials.txt", "r") as credentials:
            for line in credentials:
                user, password = line.strip('\n').split(' ',1)
                if value["username"] == user and value["password"] == password:
                    status = "OK"
                    clients.append(value["username"])
                    print(f"> {value['username']} login")
                    break
        if status == "INCORRECT":
            attempts[value["username"]] += 1 # add an attempt
            if attempts[value["username"]] == 3:
                status = "BLOCKED"
                blocked_clients.append(value["username"])
                print(f"> {value['username']} has been blocked.")
                attempts.pop(value["username"], None) # reset attempts
                # start a timer that blocks the user for block_duration
                # threading.Timer calls the remove_block function after the specified time
                threading.Timer(block_duration, remove_block, args = [value["username"]]).start()
        else:
            if value["username"] in attempts:
                attempts.pop(value["username"]) # reset attempts
    elif command == "logout":
        status = "OK"
        clients.remove(value)
        print(f"> {value} logout")
    elif command == "Download_tempID":
        tempID = ''.join(secrets.choice(string.digits) for i in range(20)) # generate a random 20 digit tempID
        start = datetime.now()
        end = start + timedelta(minutes=14, seconds=59)
        start_str = start.strftime("%d/%m/%Y %H:%M:%S")
        end_str = end.strftime("%d/%m/%Y %H:%M:%S")
        status = dict(tempID = tempID, startTime = start_str, endTime = end_str)
        with open("tempIDs.txt", "a") as tempID_file:
            tempID_file.write(f"{value} {tempID} {start_str} {end_str}\n")
        print(f"> user: {value}")
        print(f"> TempID: {tempID}")

    # encode the response and add a header
    content = json.dumps(dict(command = command, status = status)).encode('utf-8')
    header = struct.pack(">H", len(content)) # encode into 2 bytes
    response = header + content
    return response

# does the mapping between an uploaded contact log and tempIDs.txt
# prints to terminal
def check_contact_log(contact_log):
    cl_tempID = []
    startTimes = []
    endTimes = []
    contacts = contact_log.split("\n")
    for line in contacts:
        tempID, start_datetime, end_datetime = line.strip(';').split(',')
        cl_tempID.append(tempID)
        startTimes.append(start_datetime)
        endTimes.append(end_datetime)
    # convert to data frame
    contact_log_df = pd.DataFrame(dict(tempID = cl_tempID, startTime = startTimes, endTime = endTimes, n = [i for i in range(len(cl_tempID))]))
    userID = []
    ti_tempID = []
    if os.stat("tempIDs.txt").st_size == 0: # if tempIDs.txt is empty. This shouldn't happen, but handle it anyway.
        print("No valid mapping from tempIDs to usernames.")
        return
    with open("tempIDs.txt", "r") as tempID_file2:
        for line in tempID_file2:
            user, temp_ID, start_date, start_time, end_date, end_time = line.strip('\n').split(' ')
            userID.append(user)
            ti_tempID.append(temp_ID)
    # convert to dataframe
    temp_ID_df = pd.DataFrame(dict(userID = userID, tempID = ti_tempID))
    # do the mapping using pandas.merge
    merged_list = pd.merge(contact_log_df, temp_ID_df, on = "tempID").sort_values(by=["n"])
    merged_list["output"] = merged_list["userID"] + ", " + merged_list["startTime"] + ", " + merged_list["tempID"] + ";"
    output = merged_list["output"].tolist()
    if output:
        print('\n'.join(output))
    else:
        print('No valid mapping from tempIDs to usernames.') # there might be no mapping (shouldn't happen)

# Read in specified port (and block duration)
if len(sys.argv) != 3:
    raise ValueError('Usage: python server.py server_port block_duration')

# Parse the port number to an int
try:
    serverPort = int(sys.argv[1])
    block_duration = int(sys.argv[2])
except:
    print("Server port number and block duration must be integers")

# Create the welcoming socket
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1) # avoids the Address already in use error
serverSocket.bind(('', serverPort)) # bind to the port
serverSocket.listen() # listen for connections

print('The server is ready to receive.')
serverSocket.setblocking(False) # make this server non-blocking
sel.register(serverSocket, selectors.EVENT_READ, data = None) # register the socket

clients = [] # connected clients
attempts = defaultdict(int) # keeps a counter of password attempts for each user
blocked_clients = [] # list of users blocked for 3 minutes

try:
    # Start a loop to listen to incoming messages
    while True:

        events = sel.select(timeout = None)
        for key, mask in events:
            if key.data is None: # connection doesn't exist yet, accept connection
                connectionSocket, addr = serverSocket.accept() # create connection socket
                connectionSocket.setblocking(False)
                data = types.SimpleNamespace(client=addr, recv_buffer = b"", send_buffer = b"")
                events = selectors.EVENT_READ | selectors.EVENT_WRITE
                sel.register(connectionSocket, events, data=data)
            else: # connection already exists, do things
                sock = key.fileobj
                data = key.data
                if mask & selectors.EVENT_READ:
                    recv_data = sock.recv(4096)
                    # need to check that the buffer contains everything
                    if recv_data:
                        data.recv_buffer += recv_data
                        # Obtain contents from receiving buffer
                        if len(data.recv_buffer) >= 2:
                            content_length = struct.unpack(">H", data.recv_buffer[:2])[0] # length after removing 2 byte header
                            data.recv_buffer = data.recv_buffer[2:] # update to start from contents
                            if len(data.recv_buffer) >= content_length: # server has to receive all the contents before responding
                                response = json.loads(data.recv_buffer[:content_length].decode('utf-8'))
                                data.recv_buffer = data.recv_buffer[content_length:]
                                command = response["command"]
                                value = response["value"]
                                
                                if command == "Upload_contact_log": # don't respond
                                    username = value["username"]
                                    contactlog = value["contactlog"]
                                    print(f"> received contact log from {username}")
                                    print(contactlog)
                                    print(f"> Contact log checking")
                                    check_contact_log(contactlog) # perform contact log checking
                                else:
                                    # Respond to commands
                                    response = create_response(command, value)
                                    # Add the response to the send buffer
                                    data.send_buffer += response
                    else:
                        sel.unregister(sock)
                        sock.close()
                        RuntimeError("Connection ended.")
                if mask & selectors.EVENT_WRITE:
                    if data.send_buffer:
                        # Send the response
                        sent = sock.send(data.send_buffer)
                        data.send_buffer = data.send_buffer[sent:]
finally:
    sel.close()

connectionSocket.close()
