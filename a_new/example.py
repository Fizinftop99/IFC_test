import pandas as pd

from create_group_graph import create_group_graph
from ifc_to_neo4j import IfcToNeo4jConverter

if __name__ == "__main__":
    # print(os.getcwd())
    create_group_graph()

    path = "C:/Users/naumo/PycharmProjects/IFC_test/DOU_IFC_KR"

    neo4j_exp = IfcToNeo4jConverter()
    neo4j_exp.create(path)

    node_df = pd.DataFrame(neo4j_exp.get_nodes())
    edge_df = pd.DataFrame(neo4j_exp.get_edges())
    with pd.ExcelWriter('../result/new_wbs.xlsx', engine='openpyxl') as writer:
        node_df.to_excel(writer, sheet_name="Работы", index=False)
        edge_df.to_excel(writer, sheet_name="Связи", index=False)

    neo4j_exp.close()
