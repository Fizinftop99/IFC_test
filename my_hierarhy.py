import pickle
import sys

import ifcopenshell
from ifcopenshell import entity_instance
import networkx as nx
from neo4j import GraphDatabase, Transaction

k_spat = 0
k_agg = 0


# def filter_ifc(element: entity_instance) -> bool:
#     return element.is_a("IfcDoor") or \
#         element.is_a("IfcBuildingStorey") or element.is_a("IfcBuilding")
def filter_ifc(element: entity_instance) -> bool:
    return (
            element.is_a("IfcElement")
            or element.is_a("IfcSpatialStructureElement")
            or element.is_a("IfcObjectDefinition")
    ) and not (element.is_a("IfcGrid") or element.is_a("IfcAnnotation"))


def traverse(element, parent, filter_fn):
    if filter_fn(element):
        yield parent, element
        parent = element

    # follow Spatial relation
    if element.is_a('IfcSpatialStructureElement'):
        global k_spat
        k_spat += 1
        # session.execute_write(graph.node, str(element.id()), element.Name)
        for rel in element.ContainsElements:
            relatedElements = rel.RelatedElements
            for child in relatedElements:
                yield from traverse(child, parent, filter_fn)

    # follow Aggregation Relation
    if element.is_a('IfcObjectDefinition'):
        global k_agg
        k_agg += 1
        for rel in element.IsDecomposedBy:
            relatedObjects = rel.RelatedObjects
            for child in relatedObjects:
                yield from traverse(child, parent, filter_fn)


def add_node(tx: Transaction, id_, element: dict):
    q_node = 'CREATE (a:Element {id: $id, name: $name, type: $type})'
    tx.run(q_node, id=id_, name=element['name'], type=element['is_a'])


def add_edge(tx: Transaction, n, m):
    q_edge = '''
    MATCH (a:Element) WHERE a.id = $id1
    MATCH (b:Element) WHERE b.id = $id2
    MERGE (a)-[r:FOLLOWS]->(b)
    '''
    tx.run(q_edge, id1=n, id2=m)


def main():
    ifc_file = ifcopenshell.open(sys.argv[1])
    G = nx.MultiDiGraph()

    def node(element):
        return element.id()

    def get_coordinates(element):
        if not hasattr(element, "ObjectPlacement"):
            return None
        if not element.ObjectPlacement.RelativePlacement.Axis:
            return None
        coords = element.ObjectPlacement.RelativePlacement.Location.Coordinates
        return None if coords == (0.0, 0.0, 0.0) else coords

    for project in ifc_file.by_type("IfcProject"):
        for parent, child in traverse(project, None, filter_ifc):
            G.add_node(node(child),
                       global_id=str(child.GlobalId),
                       is_a=child.is_a(),
                       name=child.Name,
                       coordinates=get_coordinates(child)
                       )
            if parent is not None:
                G.add_edge(node(parent), node(child))
    print("Spatial (contains):", k_spat, "Aggregation (is decomposed):", k_agg)
    # node_attributes = ('is_a',)
    # ag_graph = nx.snap_aggregation(G,
    #                                node_attributes=node_attributes,
    #                                # supernode_attribute='is_a',
    #                                prefix='',
    #                                )

    # driver = GraphDatabase.driver(
    #     "bolt://localhost:7687",
    #     auth=("neo4j", "23109900")
    # )
    # with driver.session() as session:
    #     session.run('MATCH (n) DETACH DELETE n')
    #
    #     for i in G.nodes:
    #         session.execute_write(add_node, i, G.nodes[i])
    #     for i in G.edges():
    #         session.execute_write(add_edge, i[0], i[1])

    # pickle.dump(ag_graph, open('agg.pickle', 'wb'))
    pickle.dump(G, open('G_coord.pickle', 'wb'))

    # # load graph object from file
    # loaded_g = pickle.load(open('my.pickle', 'rb'))

    # plt.figure(figsize=(10, 10))
    # labels = nx.get_node_attributes(loaded_g, "is_a")
    # nx.draw_networkx(loaded_g, arrows=True, with_labels=True, labels=labels)
    # plt.savefig('my.png')
    # plt.show()


if __name__ == "__main__":
    main()
