import time  # Import the time module for measuring and calculating latency
"""
Input(from user): No. of Cores to be formed{n}, No. qubits in each core{k},
Qubits (i,j) i.e the qubits which are supposed to be made adjacent. 

Code-wise Desc:

Step1: Defining a core and its components(this is used during 'n' core creation) 
a)Core_components: Core name, A 'list' of qubits embeded in a core(with the range indirectly set by the user),
                   Wireless Router(with an empty buffer), Quantum Memory(as an empty 'list'),
                   Control packet(a request for EPR bit):
                   i)Header:Sender(the core which sends the packet), Initial_Dest(set as the EPR Generator),
                            Reciever(the Actual Destination, 2nd Core)

Step2: Creation and desc of EPR Generator
The EPR Gen is a component which recieves the control packet from the requesting cores through classical channels.
The EPR Gen unit then stores these requests in the EPRGenTable. An Entanglement generation list(helps to get 
the dest for the EPR bit) is formed using the table(contains the index(in the table) of the communicating cores)
and the EPR bit. Then from this list, the EPR bit is extracted and sent to the requesting cores through Quantum Channels.
EPR Gen components:
EPRGen Table:
a)genCore Pair(It is a string containing names of the communicating cores): From control packet, 
extract the sender and reciever.
b)populate_EPR_Gen_Table:As and when a control packet arrives it is registered into the table
(Col)Gen Table Component:i.Index(Request id's, stored in a FCFS{queue} form)
                        ii.Source Core(Extracted from the control packet info)
                       iii.Initial_Dest(EPR Gen)
                        iv.Core Pair(e.g A-B)
c)generate_entanglement_list(quantum Channel):
From the epr_gen_table extract the index sender and reciever core(from the core_pair column of the table) and
attach them along with the EPR bit.(format: [i,j,ent bit], send this ent_list to the quantum memories of the cores).
Ent_list components:i.Sender(Src) index
                   ii.Reciever(Dest) index
                  iii.Ent_bit(In order, is reserved for each core pair)
Then the EPR bits gets loaded into the QM, done by the code block "create_data_packet",actually, here the main
EPR bit Distribution occurs.(catches the c1{sender} and c2{reciever} core is caught(using the ent_list) 
and then the ent bit is appended to the QMs )

Step3:Loading, the embeded qubit(the user input i) present in the sender core into the Quantum Memory of the sender core.

Step4:Creation of Data Packet(by Preprocessing): Extracts data from the quantum Memory(EPR bit+Qubit to be sent)
Info in the data packet():
i.Sender
ii.Reciver
iii.Quantum Memory content(EPR bit+Qubit)
iv.Empty Payload(64 Bytes)
Now Append the created Data Packet into the wireless router of the Sender Core

Step5:Transmit data packet:Transfering of the data packets from WR of Sender to (the buffer of) WR of Reciever.

Step6:Extract the info from the Data packer in the Reciever core(Extracting the EPR Bit and the Sender qubit)

Step7:Matching EPR bit
Now from the qubit_epr_bit_pair, extract EPR bit(of the sender core),  Match it with the EPR bit of the Reciever Core 
If Matched Reconstruction is possible.

Step 8: Extract The Qubit and Place the Sender Core Qubit into the Reciever code qubit
Step 9: Main function and Latency Calculations
"""
# Function to generate a core(STEP1)
def generate_core(name, qubit_start, qubit_end):
    """
    Generate a core dictionary with the given name and a range of qubits.
    It also initializes an empty buffer for the wireless router, a control packet with sender,
    initial destination, and receiver (aka Actual Destination initially set to None), 
    and an empty quantum memory.
    """
    return {
        "name": name,  # The name of the core
        "qubits": list(range(qubit_start, qubit_end)),  # List of qubits in the core, determined by the range
        "wireless_router": {
            "buffer": []  # Initialize an empty buffer for the wireless router
        },
        "control_packet": {
            "type": "header",  # Type of control packet (header)
            "sender": name,  # Sender is the name of the core
            "initial_dest": "EPRGen",  # Initial destination set to EPR Generator
            "receiver": None  # Receiver is initially set to None
        },
        "quantum_memory": [],  # Initialize an empty quantum memory
    }

# Function to generate core pairs(STEP2)
def genCorePair(core):
    """
    Generate a string representing the core pair by concatenating the sender and receiver names.
    """
    return core["control_packet"]["sender"] + "-" + core["control_packet"]["receiver"]  # Concatenate sender and receiver names

# Function to populate EPR Generation Table
def populate_EPRGenTable(cores):
    """
    Create an EPR Generation Table by iterating over the cores.
    For each core, if it has a receiver assigned, generate the core pair and append it to the table.
    """
    EPRGenTable = []  # Initialize an empty EPR Generation Table
    i = 0  # Initialize a request ID counter
    for core in cores:  # Iterate over each core
        if core["control_packet"]["receiver"] is not None:  # Check if the core has a receiver assigned
            corePair = genCorePair(core)  # Generate the core pair string
            EPRGenTable.append([i, core["control_packet"]["sender"], core["control_packet"]["initial_dest"], corePair])  # Append details to the EPR Generation Table
            i += 1  # Increment the request ID counter
    return EPRGenTable  # Return the populated EPR Generation Table

# Function to generate entanglement list
def generate_entanglement_list(EPRGenTable):
    """
    Generate a list of entangled core pairs and their corresponding entanglement bit indices.
    """
    entanglement_list = []  # Initialize an empty entanglement list
    ent_bit = 0  # Initialize an entanglement bit counter
    for i in range(len(EPRGenTable)):  # Iterate over the EPR Generation Table
        for j in range(i + 1, len(EPRGenTable)):  # Compare each core pair with every other core pair
            if (EPRGenTable[i][3][4] == EPRGenTable[j][3][10] and EPRGenTable[i][3][10] == EPRGenTable[j][3][4]):  # Check if cores are entangled
                entanglement_list.append([i, j, ent_bit])  # Append the indices and entanglement bit to the entanglement list
                ent_bit += 1  # Increment the entanglement bit counter
    return entanglement_list  # Return the generated entanglement list

# Function to load a qubit to the core(STEP3)
def load_qubit(core, qubit):
    """
    Load a qubit to the quantum memory of the given core and print a message.
    """
    core["quantum_memory"].append({"QUBIT": qubit})  # Append the qubit to the core's quantum memory
    print("Qubit loaded to quantum memory of", core["name"])  # Print a message indicating the qubit is loaded

# Function to create data packet
def create_data_packet(core, entanglement_list, EPRGenTable):
    """
    Create data packets for the given core by appending entanglement bits to the quantum memory
    of the core and its corresponding entangled core.
    """
    for k in range(len(entanglement_list)):  # Iterate over the entanglement list
        if EPRGenTable[entanglement_list[k][0]][1] == core["name"]:  # Check if the core is the sender
            c1 = cores[EPRGenTable[entanglement_list[k][0]][1]]  # Get the sender core
            c2 = cores[EPRGenTable[entanglement_list[k][1]][1]]  # Get the receiver core
            c1["quantum_memory"].append({"ENT_BIT": entanglement_list[k][2]})  # Append the entanglement bit to the sender's quantum memory
            c2["quantum_memory"].append({"ENT_BIT": entanglement_list[k][2]})  # Append the entanglement bit to the receiver's quantum memory

# Function for preprocessing
def preprocessing(core):
    """
    Preprocess the data packet by creating a list with the sender, receiver, quantum memory,
    and an empty payload. Append this data packet to the buffer of the core's wireless router.
    """
    data_packet = [""] * 4  # Initialize a data packet with 4 empty elements
    payload = []  # Initialize an empty payload
    
    data_packet[0] = core["control_packet"]["sender"]  # Set the sender of the data packet
    data_packet[1] = core["control_packet"]["receiver"]  # Set the receiver of the data packet
    data_packet[2] = core["quantum_memory"]  # Set the quantum memory content of the data packet
    data_packet[3] = payload  # Set the empty payload of the data packet
    core["wireless_router"]["buffer"].append(data_packet)  # Append the data packet to the wireless router buffer
    
    return data_packet  # Return the created data packet

# Function to transmit data packet
def transmit_data_packet(data_packet):
    """
    Transmit the data packet by appending it to the buffer of the receiver core's wireless router.
    """
    receiver_core = cores[data_packet[1]]  # Get the receiver core using the receiver name in the data packet
    receiver_core["wireless_router"]["buffer"].append(data_packet)  # Append the data packet to the receiver's wireless router buffer

# Function to extract processed data
def extract_processed_data(core):
    """
    Extract the qubit and entanglement bit from the data packet in the core's wireless router buffer.
    """
    qubit_epr_bit_pair = []  # Initialize an empty list to hold the qubit and entanglement bit
    
    data_packet = core["wireless_router"]["buffer"][0]  # Get the first data packet from the wireless router buffer
    qubit = data_packet[2][0]["QUBIT"]  # Extract the qubit from the quantum memory in the data packet
    ent_bit = data_packet[2][1]["ENT_BIT"]  # Extract the entanglement bit from the quantum memory in the data packet
    
    qubit_epr_bit_pair.append(qubit)  # Append the qubit to the list
    qubit_epr_bit_pair.append(ent_bit)  # Append the entanglement bit to the list
    
    return qubit_epr_bit_pair  # Return the list containing the qubit and entanglement bit

# Function to match EPR bits
def match_epr(core1, core2):
    """
    Match the entanglement bits of the two cores.
    If they match, transfer the qubit from the sender core to the receiver core.
    If they don't match, print an error message.
    """
    epr_bit1 = core1["quantum_memory"][1]["ENT_BIT"]  # Extract the entanglement bit from the sender core's quantum memory
    
    lst = extract_processed_data(core2)  # Extract the processed data from the receiver core
    epr_bit2 = lst[1]  # Get the entanglement bit from the extracted data
    
    if epr_bit1 == epr_bit2:  # Check if the entanglement bits match
        core2["qubits"].append(lst[0])  # Append the qubit to the receiver core's qubits
        core1["qubits"].remove(lst[0])  # Remove the qubit from the sender core's qubits
    else:
        print("EPR Bit mismatch!")  # Print an error message if the entanglement bits don't match

# Main function
def main():
    start_time = time.time()  # Record the start time for latency calculations
    
    # Get user input for the number of cores, qubits per core, and the qubit indices for sender and receiver
    n = int(input("Enter number of cores: "))  # Get the number of cores from the user
    k = int(input("Enter number of qubits in each core: "))  # Get the number of qubits per core from the user
    i = int(input("Enter qubit i: "))  # Get the index of the sender qubit from the user
    j = int(input("Enter qubit j: "))  # Get the index of the receiver qubit from the user
    
    # Generate cores dynamically
    global cores  # Declare cores as a global variable
    cores = {}  # Initialize an empty dictionary to hold the cores
    for idx in range(n):  # Iterate over the number of cores
        cores[f"core{chr(65 + idx)}"] = generate_core(f"core{chr(65 + idx)}", idx * k, (idx + 1) * k)  # Generate each core with a unique name and range of qubits

    # Set sender and receiver based on i and j
    sender_core = None  # Initialize sender core as None
    receiver_core = None  # Initialize receiver core as None
    for core in cores.values():  # Iterate over each core
        if i in core["qubits"]:  # Check if the sender qubit is in the current core
            sender_core = core  # Set the current core as the sender core
        if j in core["qubits"]:  # Check if the receiver qubit is in the current core
            receiver_core = core  # Set the current core as the receiver core
    
    if not sender_core or not receiver_core:  # Check if both sender and receiver cores are valid
        print("Invalid qubit indices")  # Print an error message if the qubit indices are invalid
        return

    # Assign the receiver for the sender and receiver cores
    sender_core["control_packet"]["receiver"] = receiver_core["name"]  # Set the receiver for the sender core
    receiver_core["control_packet"]["receiver"] = sender_core["name"]  # Set the receiver for the receiver core

    EPRGenTable = populate_EPRGenTable(list(cores.values()))  # Generate the EPR Generation Table

    control_packet_sent_time = time.time()  # Record the time for control packet sending
    
    entanglement_list = generate_entanglement_list(EPRGenTable)  # Generate the entanglement list

    epr_generation_time = time.time()  # Record the time for EPR generation
    
    if sender_core == receiver_core:  # Check if the sender and receiver are the same core
        print("They are intra-core")  # Print a message indicating intra-core communication
        return
    
    load_qubit(sender_core, i)  # Load the sender qubit into the sender core's quantum memory
    create_data_packet(sender_core, entanglement_list, EPRGenTable)  # Create data packets with entanglement bits
    
    entanglement_distribution_time = time.time()  # Record the time for entanglement distribution
    
    data_packet = preprocessing(sender_core)  # Preprocess the data packet
    
    preprocessing_time = time.time()  # Record the time for preprocessing
    
    transmit_data_packet(data_packet)  # Transmit the data packet to the receiver core

    transmission_time = time.time()  # Record the time for data packet transmission
    
    print("Qubits in Receiver Core before matching:", receiver_core["qubits"])  # Print the qubits in the receiver core before matching
    match_epr(sender_core, receiver_core)  # Match the entanglement bits and transfer the qubit
    print("Qubits in Receiver Core after matching:", receiver_core["qubits"])  # Print the qubits in the receiver core after matching
    
    # Calculate the latencies for different stages
    control_packet_latency = (control_packet_sent_time - start_time) * (10e-12)  # Convert to picoseconds
    epr_generation_latency = epr_generation_time - control_packet_sent_time  # Calculate EPR generation latency
    entanglement_distribution_latency = entanglement_distribution_time - epr_generation_time  # Calculate entanglement distribution latency
    preprocessing_latency = preprocessing_time - entanglement_distribution_time  # Calculate preprocessing latency
    transmission_latency = transmission_time - preprocessing_time  # Calculate data packet transmission latency
    
    print("\nLatencies:")  # Print latency header
    print(f"Control Packet Sending Latency: {control_packet_latency:.6f} picoseconds")  # Print control packet sending latency
    print(f"EPR Generation Latency: {epr_generation_latency:.6f} seconds")  # Print EPR generation latency
    print(f"Entanglement Distribution Latency: {entanglement_distribution_latency:.6f} seconds")  # Print entanglement distribution latency
    print(f"Preprocessing Latency: {preprocessing_latency:.6f} seconds")  # Print preprocessing latency
    print(f"Data Packet Transmission Latency: {transmission_latency:.6f} seconds")  # Print data packet transmission latency

if __name__ == "__main__":
    main()  # Execute the main function
