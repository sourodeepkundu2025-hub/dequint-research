
from sequence.components.memory import Memory
from sequence.components.photon import Photon
from sequence.topology.node import Node, QuantumRouter, BSMNode
from sequence.kernel.timeline import Timeline

from sequence.entanglement_management.generation import EntanglementGenerationB
from sequence.resource_management.resource_manager import ResourceManager
from sequence.network_management.network_manager import NewNetworkManager

# timeline = Timeline()



# node = Node("node1", timeline)
component_templates = {
    "MemoryArray": {
        # "timeline": timeline,
        # "fidelity": 0.9,          
        # "frequency": 100e6,         
        # "efficiency": 0.95,      
        # "coherence_time": 1e-3,     
        # "wavelength": 700        
    }
}

tl = Timeline(10e14)
quantum_router = QuantumRouter(name="router1", tl=tl, memo_size=10, seed=10, component_templates=component_templates)
quantum_router.init()
# node.add_component(quantum_router)


# node2 = Node("node2", timeline)
quantum_router_2 = QuantumRouter(name="router2", tl=tl, memo_size=10, seed=10, component_templates=component_templates)
# node2.add_component(quantum_router_2)

# node.add_receiver(node2)

test = quantum_router.get_components_by_type("MemoryArray")
print(test)
for i in range(len(test[0].memories)):
    p1 = Photon("photon" + "%d" % i, tl, 700, None, use_qm=True)
    print(test[0].memories[i])

#for i in range(len(test[0].memories)):
#   print(f"{i}: {test[0].memories[i].stored_photons.name}")