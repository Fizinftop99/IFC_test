import pickle

from ifc_to_nx_explorer import IfcToNxExplorer
from nx_to_neo4j_explorer import NxToNeo4jExplorer

if __name__ == "__main__":
    nx_exp = IfcToNxExplorer()
    nx_exp.create_net_graph("../Amundsena_IFC_24/АР_Амундсена_Син_R22.ifc")

    # pickle.dump(nx_exp.get_net_graph(), open('new_AR.pickle', 'wb'))
    # G = pickle.load(open('exp_AR.pickle', 'rb'))

    neo4j_exp = NxToNeo4jExplorer()
    G = nx_exp.get_net_graph()
    neo4j_exp.create_neo4j(G)
