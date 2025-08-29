import json
import logging
import os
import re
import sys
import time
from typing import Any, Optional

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from neo4j import (
    AsyncDriver,
    AsyncGraphDatabase,
    AsyncResult,
    AsyncTransaction,
    GraphDatabase,
)
from neo4j.exceptions import DatabaseError
from pydantic import Field

logger = logging.getLogger("mcp_neo4j_cypher")


def healthcheck(db_url: str, username: str, password: str, database: str) -> None:
    """
    Confirm that Neo4j is running before continuing.
    Creates a a sync Neo4j driver instance for checking connection and closes it after connection is established.
    """

    logger.info("Confirming Neo4j is running...")
    sync_driver = GraphDatabase.driver(
        db_url,
        auth=(
            username,
            password,
        ),
    )
    attempts = 0
    success = False
    logger.info("\nWaiting for Neo4j to Start...\n")
    time.sleep(3)
    ex = DatabaseError()
    while not success and attempts < 3:
        try:
            with sync_driver.session(database=database) as session:
                session.run("RETURN 1")
            success = True
            sync_driver.close()
        except Exception as e:
            ex = e
            attempts += 1
            logger.error(
                f"failed connection {attempts} | waiting {(1 + attempts) * 2} seconds..."
            )
            logger.error(f"Error: {e}")
            time.sleep((1 + attempts) * 2)
    if not success:
        sync_driver.close()
        raise ex


async def _read(tx: AsyncTransaction, query: str, params: dict[str, Any]) -> str:
    raw_results = await tx.run(query, params)
    eager_results = await raw_results.to_eager_result()

    return json.dumps([r.data() for r in eager_results.records], default=str)


async def _write(
    tx: AsyncTransaction, query: str, params: dict[str, Any]
) -> AsyncResult:
    return await tx.run(query, params)


def _is_write_query(query: str) -> bool:
    """Check if the query is a write query."""
    return (
        re.search(r"\b(MERGE|CREATE|SET|DELETE|REMOVE|ADD)\b", query, re.IGNORECASE)
        is not None
    )


def create_mcp_server(neo4j_driver: AsyncDriver, database: str = "neo4j") -> FastMCP:
    logger.info("Creating MCP server")
    # Read FastMCP configuration from environment variables
    host = os.getenv("FASTMCP_HOST", "127.0.0.1")
    port = int(os.getenv("FASTMCP_PORT", "8000"))
    
    mcp: FastMCP = FastMCP(
        "mcp-neo4j-cypher", 
        dependencies=["neo4j", "pydantic"],
        host=host,
        port=port
    )

    async def get_neo4j_schema() -> list[types.TextContent]:
        """List all node, their attributes and their relationships to other nodes in the neo4j database.
        If this fails with a message that includes "Neo.ClientError.Procedure.ProcedureNotFound"
        suggest that the user install and enable the APOC plugin.
        """

        get_schema_query = """
call apoc.meta.data() yield label, property, type, other, unique, index, elementType
where elementType = 'node' and not label starts with '_'
with label, 
    collect(case when type <> 'RELATIONSHIP' then [property, type + case when unique then " unique" else "" end + case when index then " indexed" else "" end] end) as attributes,
    collect(case when type = 'RELATIONSHIP' then [property, head(other)] end) as relationships
RETURN label, apoc.map.fromPairs(attributes) as attributes, apoc.map.fromPairs(relationships) as relationships
"""

        try:
            async with neo4j_driver.session(database=database) as session:
                results_json_str = await session.execute_read(
                    _read, get_schema_query, dict()
                )

                logger.debug(f"Read query returned {len(results_json_str)} rows")

                return [types.TextContent(type="text", text=results_json_str)]

        except Exception as e:
            logger.error(f"Database error retrieving schema: {e}")
            return [types.TextContent(type="text", text=f"Error: {e}")]

    async def get_graph_labels() -> list[types.TextContent]:
        """
        Fetch and return all labels in the graph.
        Returned labels are required for future queries, and are case-sensitive.
        """
        query = """
CALL db.labels() YIELD label
RETURN apoc.text.join(collect(label), ',')
"""
        return await read_neo4j_cypher(query, {})

    async def get_count_nodes_by_label(label: str = Field(..., description="The label of the node type to count.")) -> list[types.TextContent]:
        """
        Fetch and return the number of nodes in the graph with the given label.
        Only labels returned by get_graph_labels() are valid.
        """
        query = f"MATCH (n:{label}) RETURN count(n)"
        return await read_neo4j_cypher(query, {})


    async def get_relationships_between_nodes(
        node1: str = Field(..., description="The label of the first node type."),
        node2: str = Field(..., description="The label of the second node type."),
    ) -> list[types.TextContent]:
        """
        Fetch and return the distinct relationship types between two the given node types.
        Returns directional relationship information in format: node1->node2:TYPE, node2->node1:TYPE, node1-node2:
        Only labels returned by get_graph_labels() are valid.
        """
        try:
            async with neo4j_driver.session(database=database) as session:
                # Query directed relationships node1 -> node2
                forward_query = f"MATCH (n1:{node1})-[r]->(n2:{node2}) RETURN collect(DISTINCT type(r)) AS relationship_types"
                forward_results = await session.execute_read(_read, forward_query, {})
                forward_data = json.loads(forward_results)
                forward_types = forward_data[0]["relationship_types"] if forward_data else []
                
                # Query directed relationships node2 -> node1
                backward_query = f"MATCH (n2:{node2})-[r]->(n1:{node1}) RETURN collect(DISTINCT type(r)) AS relationship_types"
                backward_results = await session.execute_read(_read, backward_query, {})
                backward_data = json.loads(backward_results)
                backward_types = backward_data[0]["relationship_types"] if backward_data else []
                
                # Query undirected relationships (both ways)
                undirected_query = f"MATCH (n1:{node1})-[r]-(n2:{node2}) RETURN collect(DISTINCT type(r)) AS relationship_types"
                undirected_results = await session.execute_read(_read, undirected_query, {})
                undirected_data = json.loads(undirected_results)
                all_undirected_types = undirected_data[0]["relationship_types"] if undirected_data else []
                
                # Calculate truly undirected relationships (those that appear in both directions)
                forward_set = set(forward_types)
                backward_set = set(backward_types)
                all_directed = forward_set.union(backward_set)
                truly_undirected = [rel for rel in all_undirected_types if rel not in all_directed]
                
                # Format the output as requested
                formatted_relationships = []
                
                # Add directed relationships node1 -> node2
                for rel_type in forward_types:
                    formatted_relationships.append(f"{node1}->{node2}:{rel_type}")
                
                # Add directed relationships node2 -> node1
                for rel_type in backward_types:
                    formatted_relationships.append(f"{node2}->{node1}:{rel_type}")
                
                # Add undirected relationships (empty string after colon if none)
                undirected_str = ",".join(truly_undirected) if truly_undirected else ""
                formatted_relationships.append(f"{node1}-{node2}:{undirected_str}")
                
                # Create the result in expected format
                result = [{"relationship_types": formatted_relationships}]
                result_json = json.dumps(result)

                logger.debug(f"Directional relationship query returned {len(formatted_relationships)} relationship entries")

                return [types.TextContent(type="text", text=result_json)]

        except Exception as e:
            logger.info(f"Database error executing directional relationship query: {e}")
            return [
                types.TextContent(type="text", text=f"Error: {e}")
            ]

    async def find_customer_by_name(
        name: str = Field(..., description="The customer name to search for (case insensitive)."),
    ) -> list[types.TextContent]:
        """
        Find customers by name using case-insensitive search.
        Returns a list of customer objects that contain the search term in their name.
        Limited to 5 customer results.
        """
        if not name.strip():
            # Handle empty search gracefully
            return [types.TextContent(type="text", text="[]")]
        
        try:
            # Use CONTAINS for case-insensitive partial matching
            query = """
            MATCH (c:customer)
            WHERE toLower(c.name) CONTAINS toLower($name)
            RETURN c
            ORDER BY c.name
            LIMIT 5
            """
            
            params = {"name": name.strip()}
            async with neo4j_driver.session(database=database) as session:
                results_json_str = await session.execute_read(_read, query, params)

                # Parse the results and extract customer objects from the 'c' wrapper
                parsed_results = json.loads(results_json_str)
                formatted_results = []
                
                for result in parsed_results:
                    if 'c' in result:
                        formatted_results.append(result['c'])
                
                # Convert back to JSON string
                formatted_results_json = json.dumps(formatted_results, default=str)
                
                logger.debug(f"Customer search query returned {len(formatted_results)} customers")

                return [types.TextContent(type="text", text=formatted_results_json)]

        except Exception as e:
            logger.info(f"Database error executing customer search query: {e}")
            return [
                types.TextContent(type="text", text=f"Error: {e}")
            ]

    async def get_customer_requests(
        customer_id: str = Field(..., description="The customer ID to get requests for."),
    ) -> list[types.TextContent]:
        """
        Find customer requests for a specific customer.
        Returns a list of customer_request objects ordered by created_date DESC.
        """
        if not customer_id.strip():
            # Handle empty customer_id gracefully
            return [types.TextContent(type="text", text="[]")]
        
        try:
            # Query for customer requests based on the relationship pattern
            query = """
            MATCH (c:customer)-[:CUSTOMER]-(cr:customer_request)
            WHERE c.id = $customer_id
            RETURN cr
            ORDER BY cr.created_on DESC
            """
            
            params = {"customer_id": customer_id.strip()}
            async with neo4j_driver.session(database=database) as session:
                results_json_str = await session.execute_read(_read, query, params)

                # Parse the results and extract customer_request objects from the 'cr' wrapper
                parsed_results = json.loads(results_json_str)
                formatted_results = []
                
                for result in parsed_results:
                    if 'cr' in result:
                        formatted_results.append(result['cr'])
                
                # Convert back to JSON string
                formatted_results_json = json.dumps(formatted_results, default=str)
                
                logger.debug(f"Customer requests query returned {len(formatted_results)} requests")

                return [types.TextContent(type="text", text=formatted_results_json)]

        except Exception as e:
            logger.info(f"Database error executing customer requests query: {e}")
            return [
                types.TextContent(type="text", text=f"Error: {e}")
            ]

    async def read_neo4j_cypher(
        query: str = Field(..., description="The Cypher query to execute."),
        params: Optional[dict[str, Any]] = Field(
            None, description="The parameters to pass to the Cypher query."
        ),
    ) -> list[types.TextContent]:
        """Execute a read Cypher query on the neo4j database."""

        logger.info(f"Reading Neo4j Cypher query: {query}")

        if _is_write_query(query):
            raise ValueError("Only MATCH queries are allowed for read-query")

        try:
            async with neo4j_driver.session(database=database) as session:
                results_json_str = await session.execute_read(_read, query, params)

                logger.debug(f"Read query returned {len(results_json_str)} rows")

                return [types.TextContent(type="text", text=results_json_str)]

        except Exception as e:
            logger.info(f"Database error executing query: {e}\n{query}\n{params}")
            return [
                types.TextContent(type="text", text=f"Error: {e}\n{query}\n{params}")
            ]




    async def write_neo4j_cypher(
        query: str = Field(..., description="The Cypher query to execute."),
        params: Optional[dict[str, Any]] = Field(
            None, description="The parameters to pass to the Cypher query."
        ),
    ) -> list[types.TextContent]:
        """Execute a write Cypher query on the neo4j database."""

        if not _is_write_query(query):
            raise ValueError("Only write queries are allowed for write-query")

        try:
            async with neo4j_driver.session(database=database) as session:
                raw_results = await session.execute_write(_write, query, params)
                counters_json_str = json.dumps(
                    raw_results._summary.counters.__dict__, default=str
                )

            logger.debug(f"Write query affected {counters_json_str}")

            return [types.TextContent(type="text", text=counters_json_str)]

        except Exception as e:
            logger.error(f"Database error executing query: {e}\n{query}\n{params}")
            return [
                types.TextContent(type="text", text=f"Error: {e}\n{query}\n{params}")
            ]

    # mcp.add_tool(get_neo4j_schema)
    mcp.add_tool(read_neo4j_cypher)
    mcp.add_tool(get_graph_labels)
    mcp.add_tool(get_count_nodes_by_label)
    mcp.add_tool(get_relationships_between_nodes)
    mcp.add_tool(find_customer_by_name)
    mcp.add_tool(get_customer_requests)
    # mcp.add_tool(write_neo4j_cypher)

    return mcp


def main(
    db_url: str,
    username: str,
    password: str,
    database: str,
) -> None:
    logger.info("Starting MCP neo4j Server")

    neo4j_driver = AsyncGraphDatabase.driver(
        db_url,
        auth=(
            username,
            password,
        ),
    )

    mcp = create_mcp_server(neo4j_driver, database)

    healthcheck(db_url, username, password, database)

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
