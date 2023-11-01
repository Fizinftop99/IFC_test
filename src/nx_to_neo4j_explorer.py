import math

import pandas as pd
from neo4j import GraphDatabase, Transaction, RoutingControl

GROUPS_URI = "neo4j://localhost:7688"
# GROUPS_URI = "neo4j://localhost:7690"
ELEMENTS_URI = "neo4j://localhost:7687"
USER = "neo4j"
PSWD = "23109900"


class NxToNeo4jExplorer:
    def __init__(self):
        self.element_driver = GraphDatabase.driver(ELEMENTS_URI, auth=(USER, PSWD))
        self.element_driver.verify_connectivity()

        self.group_driver = GraphDatabase.driver(GROUPS_URI, auth=(USER, PSWD))
        self.group_driver.verify_connectivity()
        q_rel = '''MATCH (a:IfcClass)-[r:FOLLOWS]->(b:IfcClass)
        RETURN a.name AS type1, b.name AS type2'''
        self.group_link_df = pd.DataFrame(self.group_driver.session().run(q_rel).data())
        self.group_driver.close()

    def close(self):
        self.element_driver.close()

    @staticmethod
    def add_node(tx: Transaction, id_, stor_id_, props_):
        q = """
        CREATE (n:Element)
        SET n = $props
        SET n.id = $id
        SET n.stor_id = $stor_id
        """
        tx.run(q, id=str(id_), stor_id=str(stor_id_), props=props_)

    @staticmethod
    def add_edge(tx: Transaction, n, m):
        q_edge = '''
        MATCH (a:Element) WHERE a.id = $id1
        MATCH (b:Element) WHERE b.id = $id2
        MERGE (a)-[r:CONTAINS]->(b)
        '''
        tx.run(q_edge, id1=str(n), id2=str(m))

    @staticmethod
    def add_ifc_class(tx: Transaction, storey_id, class_id, class_name):
        q_class = '''
        MATCH (s:Element) WHERE s.id = $s_id
        MERGE (s)-[r:CONTAINS]->(:IfcClass {id: $id, name: $name})
        '''
        tx.run(q_class, s_id=str(storey_id), id=str(class_id), name=class_name)

    @staticmethod
    def add_el_to_class(tx: Transaction, class_id, element_id):
        q_cls_el = '''
        MATCH (c:IfcClass) WHERE c.id = $cls_id
        MATCH (e:Element) WHERE e.id = $el_id
        MERGE (c)-[:CONSISTS_OF]->(e)
        '''
        tx.run(q_cls_el, cls_id=str(class_id), el_id=str(element_id))

    @staticmethod
    def traverse(tx: Transaction, id1, id2):
        q_traverse = '''
        MATCH (a:Element) WHERE a.id = $id1
        MATCH (b:Element) WHERE b.id = $id2
        MERGE (a)-[:TRAVERSE]->(b)
        '''
        tx.run(q_traverse, id1=str(id1), id2=str(id2))

    @staticmethod
    def add_class_rel(tx: Transaction, pred_name: str, flw_name: str):
        q_rel = '''
        MATCH (a:IfcClass) WHERE a.name = $name1
        MATCH (b:IfcClass) WHERE b.name = $name2
        MERGE (a)-[r:FOLLOWS]->(b)
        '''
        tx.run(q_rel, name1=pred_name, name2=flw_name)

    def create_neo4j(self, G) -> None:
        """
        Создает граф в neo4j по объекту networkx.Graph
        :param G: networkx.Graph, сформированный по IFC модели
        """
        with self.element_driver.session() as session:
            session.run('MATCH (n) DETACH DELETE n')

            build_id = [node for node, data in G.nodes(data=True) if data.get('is_a') == 'IfcBuilding'][0]
            session.execute_write(NxToNeo4jExplorer.add_node, build_id, None, G.nodes[build_id])

            # Loop over all storeys in building
            for stor_id in G.successors(build_id):
                data = G.nodes[stor_id]
                if data.get('is_a') != 'IfcBuildingStorey':
                    continue
                # Create storey in graph and link it with building
                session.execute_write(NxToNeo4jExplorer.add_node, stor_id, None, data)
                session.execute_write(NxToNeo4jExplorer.add_edge, build_id, stor_id)

                # find all groups (IFC classes) in this storey
                contained_classes = set(G.nodes[i]['is_a'] for i in list(filter(
                    lambda el_id: G.nodes[el_id]["coordinates"],
                    G.successors(stor_id))
                ))
                # add groups (classes) to graph
                cls_to_id = dict()
                for j, cls_name in enumerate(contained_classes):
                    cls_to_id[cls_name] = str(stor_id) + '_' + str(j)
                    session.execute_write(NxToNeo4jExplorer.add_ifc_class, stor_id, cls_to_id[cls_name], cls_name)

                def insert_elements(group):
                    elements = list(filter(
                        lambda el_id: G.nodes[el_id]["is_a"] == group and G.nodes[el_id]["coordinates"],
                        G.successors(stor_id))
                    )

                    # Для упорядочивания элементов одной группы
                    start_point = (0, 0)

                    def compute_angle(el_id):
                        coordinates = G.nodes[el_id]["coordinates"]
                        x, y, z = coordinates[0], coordinates[1], coordinates[2]
                        angle = math.atan2(y - start_point[1], x - start_point[0])
                        return z, angle

                    # prev_id = 0
                    for j, i in enumerate(sorted(elements, key=compute_angle)):
                        s_data = G.nodes[i]
                        if s_data["coordinates"]:
                            session.execute_write(NxToNeo4jExplorer.add_node, i, stor_id, s_data)
                            session.execute_write(NxToNeo4jExplorer.add_el_to_class, cls_to_id[group], i)
                            if j > 0:
                                session.execute_write(NxToNeo4jExplorer.traverse, prev_id, i)
                            prev_id = i
                            if j == 4:
                                break

                def get_edge_elements(stor_id, type1: str, type2: str):
                    with self.element_driver.session() as session:
                        q_get_last = f'''MATCH (s:Element {{is_a: '{type1}', stor_id: '{str(stor_id)}' }})
                        WHERE NOT (s)-[]->(:Element {{is_a: '{type1}' }})
                        RETURN s.id AS id
                        LIMIT 1'''
                        last_res = session.run(q_get_last).data()
                        q_get_first = f'''MATCH (s:Element {{is_a: '{type2}', stor_id: '{str(stor_id)}' }})
                        WHERE NOT (:Element {{is_a: '{type2}' }})-[]->(s)
                        RETURN s.id AS id
                        LIMIT 1'''
                        first_res = session.run(q_get_first).data()

                        if len(last_res) > 0 and len(first_res) > 0:
                            q_rel = f'''MATCH (a:Element) WHERE a.id = '{last_res[0]['id']}'
                                MATCH (b:Element) WHERE b.id = '{first_res[0]['id']}'
                                MERGE (a)-[r:TRAVERSE]->(b)
                                '''
                            session.run(q_rel)

                for cls in contained_classes:
                    # fill the group with elements
                    insert_elements(cls)
                    # connect elements based on group links
                    self.group_link_df.apply(
                        lambda row: get_edge_elements(stor_id, row.type1, row.type2),
                        axis=1
                    )

    def get_dict(self):
        query = """MATCH (el)-[:TRAVERSE]->(relEl) RETURN el.ADCM_Title as wbs1, el.ADCM_Level as wbs2, el.ADCM_DIN as 
        wbs3_id, el.ADCM_JobType as wbs3, el.name as name UNION MATCH (el)-[:TRAVERSE]->(relEl) RETURN 
        relEl.ADCM_Title as wbs1, relEl.ADCM_Level as wbs2, relEl.ADCM_DIN as wbs3_id, relEl.ADCM_JobType as wbs3, 
        relEl.name as name"""

        records = self.element_driver.session().run(query).data()
        return records
