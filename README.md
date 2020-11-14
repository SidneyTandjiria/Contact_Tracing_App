# Contact_Tracing_App

This project simulates the CovidSafe digital contact tracing app, based on the BlueTrace protocol. A client-server architecture is used, where multiple smartphone clients can communicate with a server via TCP, and with each other via UDP.

Two programs are used in this simulation:
- **server.py**: The server is responsible for authenticating users, generating tempIDs, and generating contact details of known contacts for a user that has tested positive to COVID-19.
- **client.py**: The client is responsible for allowing users to login, request a tempID, beacon other clients and to upload their contact log to the server.
