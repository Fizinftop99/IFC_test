import json
import pickle

from ifc_to_nx_converter import IfcToNxConverter
from nx_to_neo4j_converter import NxToNeo4jConverter

if __name__ == "__main__":
    nx_exp = IfcToNxConverter()
    nx_exp.create_net_graph("../Amundsena_IFC_24/АР_Амундсена_Син_R22.ifc")

    # pickle.dump(nx_exp.get_net_graph(), open('new_AR.pickle', 'wb'))
    # G = pickle.load(open('exp_AR.pickle', 'rb'))

    neo4j_exp = NxToNeo4jConverter()
    G = nx_exp.get_net_graph()
    neo4j_exp.create_neo4j(G)
    # neo4j_exp.save_edges()

    with open("data.json", "w", encoding="UTF-8") as file_out:
        json.dump(neo4j_exp.get_dict()[0:2], file_out, ensure_ascii=False, indent=2)

    neo4j_exp.close()
