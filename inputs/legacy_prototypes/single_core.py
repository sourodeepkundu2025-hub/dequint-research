import time
#Creating Dictionary and defining the components {}
coreA = {
    "name": "coreA",
    "qubits": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "wireless_router": {
        "buffer": []
    },
    "control_packet": {
        "type": "header",
        "sender": "coreA",
        "initial_dest": "EPRGen",
        "receiver": "coreB"
    },
    "quantum_memory": [],
}

coreB = {
    "name": "coreB",
    "qubits": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
    "wireless_router": {
        "buffer": []
    },
    "control_packet": {
        "type": "header",
        "sender": "coreB",
        "initial_dest": "EPRGen",
        "receiver": "coreA"
    },
    "quantum_memory": [],
}

def genCorePair(core):
    return core["control_packet"]["sender"] + "-" + core["control_packet"]["receiver"]

def populate_EPRGenTable():
    EPRGenTable = []
    i = 0
    corePair_AtoB = genCorePair(coreA)
    corePair_BtoA = genCorePair(coreB)
    EPRGenTable.append([i, coreA["control_packet"]["sender"], coreA["control_packet"]["initial_dest"], corePair_AtoB])
    i += 1
    EPRGenTable.append([i, coreB["control_packet"]["sender"], coreA["control_packet"]["initial_dest"], corePair_BtoA])
    return EPRGenTable

def generate_entanglement_list(EPRGenTable):
    entanglement_list = []
    ent_bit = 0
    for i in range(len(EPRGenTable)):
        for j in range(i + 1, len(EPRGenTable)):
            if (EPRGenTable[i][3][4] == EPRGenTable[j][3][10] and EPRGenTable[i][3][10] == EPRGenTable[j][3][4]):
                entanglement_list.append([i, j, ent_bit])
                ent_bit += 1
    return entanglement_list

def load_qubit(core, qubit):
    if core == "coreA":
        coreA["quantum_memory"].append({"QUBIT": qubit})
    else:
        coreB["quantum_memory"].append({"QUBIT": qubit})
    print("Qubit loaded to quantum memory of", core)

def create_data_packet(core, entanglement_list, EPRGenTable):
    for k in range(len(entanglement_list)):
        if EPRGenTable[entanglement_list[k][0]][1] == core["name"]:
            c1 = coreA if EPRGenTable[entanglement_list[k][0]][1] == "coreA" else coreB
            c2 = coreB if EPRGenTable[entanglement_list[k][1]][1] == "coreB" else coreA
            c1["quantum_memory"].append({"ENT_BIT": entanglement_list[k][2]})
            c2["quantum_memory"].append({"ENT_BIT": entanglement_list[k][2]})

def preprocessing(core):
    data_packet = [""] * 4
    payload = []
    
    if core["name"] == "coreA":
        data_packet[0] = coreA["control_packet"]["sender"]
        data_packet[1] = coreA["control_packet"]["receiver"]
        data_packet[2] = coreA["quantum_memory"]
        data_packet[3] = payload
        coreA["wireless_router"]["buffer"].append(data_packet)
        
    elif core["name"] == "coreB":
        data_packet[0] = coreB["control_packet"]["sender"]
        data_packet[1] = coreB["control_packet"]["receiver"]
        data_packet[2] = coreB["quantum_memory"]
        data_packet[3] = payload
        coreB["wireless_router"]["buffer"].append(data_packet)
        
    return data_packet

def transmit_data_packet(data_packet):
    if data_packet[1] == "coreB":
        coreB["wireless_router"]["buffer"].append(data_packet)
    elif data_packet[1] == "coreA":
        coreA["wireless_router"]["buffer"].append(data_packet)

def extract_processed_data(core):
    qubit_epr_bit_pair = []
    
    data_packet = core["wireless_router"]["buffer"][0]
    qubit = data_packet[2][0]["QUBIT"]
    ent_bit = data_packet[2][1]["ENT_BIT"]
    
    qubit_epr_bit_pair.append(qubit)
    qubit_epr_bit_pair.append(ent_bit)
    
    return qubit_epr_bit_pair

def match_epr(core1, core2):
    epr_bit1 = core1["quantum_memory"][1]["ENT_BIT"]
    
    lst = extract_processed_data(core2)
    epr_bit2 = lst[1]
    
    if epr_bit1 == epr_bit2:
        core2["qubits"].append(lst[0])
        core1["qubits"].remove(lst[0])
    else:
        print("EPR Bit mismatch!")

def main():
    start_time = time.time()
    
    EPRGenTable = populate_EPRGenTable()

    control_packet_sent_time = time.time()
    
    entanglement_list = generate_entanglement_list(EPRGenTable)

    epr_generation_time = time.time()
        
    i = int(input("Enter qubit i: "))
    j = int(input("Enter qubit j: "))
    
    if j <= 9 or i > 9:
        print("They are intra-core")
        return
    
    load_qubit("coreA", i)
    create_data_packet(coreA, entanglement_list, EPRGenTable)
    
    entanglement_distribution_time = time.time()
    
    data_packet = preprocessing(coreA)
    
    preprocessing_time = time.time()
    
    transmit_data_packet(data_packet)

    transmission_time = time.time()
    
    print("Qubits in Core B before matching:", coreB["qubits"])
    match_epr(coreA, coreB)
    print("Qubits in Core B after matching:", coreB["qubits"])
    
    control_packet_latency = (control_packet_sent_time - start_time)*(10e-12)
    epr_generation_latency = epr_generation_time - control_packet_sent_time
    entanglement_distribution_latency = entanglement_distribution_time - epr_generation_time
    preprocessing_latency = preprocessing_time - entanglement_distribution_time
    transmission_latency = transmission_time - preprocessing_time
    
    print("\nLatencies:")
    print(f"Control Packet Sending Latency: {control_packet_latency:.6f} picoseconds")
    print(f"EPR Generation Latency: {epr_generation_latency:.6f} seconds")
    print(f"Entanglement Distribution Latency: {entanglement_distribution_latency:.6f} seconds")
    print(f"Preprocessing Latency: {preprocessing_latency:.6f} seconds")
    print(f"Data Packet Transmission Latency: {transmission_latency:.6f} seconds")

if __name__ == "__main__":
    main()