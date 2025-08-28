import json
import os
from typing import Any

import pytest
from mcp.server import FastMCP
from neo4j import AsyncGraphDatabase

from mcp_neo4j_cypher.server import create_mcp_server


@pytest.mark.asyncio(loop_scope="function")
async def test_get_graph_labels(mcp_server: FastMCP):
    response = await mcp_server.call_tool("get_graph_labels", dict())
    print(f"test_get_graph_labels response: {response}")
    
    # Handle the tuple response format
    content_list, _ = response
    result = json.loads(content_list[0].text)
    print(f"test_get_graph_labels result: {result}")
    
    # Verify the response structure
    assert isinstance(result, list)
    assert len(result) == 1
    
    # The result contains a single object with APOC-joined labels
    labels_obj = result[0]
    assert "apoc.text.join(collect(label), ',')" in labels_obj
    
    # Extract the comma-separated labels string
    labels_string = labels_obj["apoc.text.join(collect(label), ',')"]
    labels_list = labels_string.split(',')
    
    # Verify we have multiple labels (should be 75+ from your database)
    assert len(labels_list) > 50, f"Expected many labels, got {len(labels_list)}"
    
    # Verify some expected labels from your real database
    expected_labels = {"users", "groups", "role", "customer", "mission"}
    actual_labels = set(labels_list)
    assert expected_labels.issubset(actual_labels), f"Expected {expected_labels} to be subset of {actual_labels}"
    
    print(f"Found {len(labels_list)} labels: {labels_list[:10]}...")  # Show first 10
    

@pytest.mark.asyncio(loop_scope="function")
async def test_read_neo4j_cypher(mcp_server: FastMCP):
    # Test direct Cypher query execution with real database

    # Execute a simple query to count nodes by label from real database
    query = """
    MATCH (u:users)
    RETURN count(u) AS user_count
    """

    response = await mcp_server.call_tool("read_neo4j_cypher", dict(query=query))
    print(f"test_read_neo4j_cypher response: {response}")
    
    # Handle the tuple response format
    content_list, _ = response
    result = json.loads(content_list[0].text)
    print(f"test_read_neo4j_cypher result: {result}")
    
    # Verify the query result structure
    assert isinstance(result, list)
    assert len(result) == 1
    assert "user_count" in result[0]
    
    # Verify we have users in the database (should be > 0)
    user_count = result[0]["user_count"]
    assert user_count > 0, f"Expected users in database, got {user_count}"
    
    # Test another query with relationships from real data
    relationship_query = """
    MATCH (u:users)-[r:USER]->(g:groups)
    RETURN u, type(r) as rel_type, g
    LIMIT 5
    """
    
    response2 = await mcp_server.call_tool("read_neo4j_cypher", dict(query=relationship_query))
    content_list2, _ = response2
    result2 = json.loads(content_list2[0].text)
    print(f"Relationship query result: {result2}")
    
    # This might return empty if no USER relationships exist in that direction
    # Just verify the response structure is correct
    assert isinstance(result2, list)


@pytest.mark.asyncio(loop_scope="function")
async def test_get_relationships_between_nodes(mcp_server: FastMCP):
    """Test getting relationships between Person nodes"""
    
    # Test getting relationships between Person and Person nodes
    response = await mcp_server.call_tool("get_relationships_between_nodes", {
        "node1": "Person",
        "node2": "Person"
    })
    
    print(f"test_get_relationships_between_nodes response: {response}")
    # Handle the tuple response format
    content_list, _ = response
    result = json.loads(content_list[0].text)
    print(f"test_get_relationships_between_nodes result: {result}")
    
    # Verify the response structure
    assert isinstance(result, list)
    assert len(result) == 1
    
    # Check that we get the expected relationship types
    relationships = result[0]
    assert "relationship_types" in relationships
    relationship_types = relationships["relationship_types"]
    assert isinstance(relationship_types, list)
    
    # For real database, test with actual labels that exist (users and groups)
    response_real = await mcp_server.call_tool("get_relationships_between_nodes", {
        "node1": "users",
        "node2": "groups"
    })
    
    print(f"Real database test response: {response_real}")
    content_list_real, _ = response_real
    result_real = json.loads(content_list_real[0].text)
    print(f"Real database test result: {result_real}")
    
    # Should return the actual relationship types from real data
    assert isinstance(result_real, list)
    assert len(result_real) == 1
    real_relationships = result_real[0]["relationship_types"]
    assert isinstance(real_relationships, list)
    # Should contain "USER" and "GROUP" based on earlier testing
    expected_types = {"USER", "GROUP"}
    actual_types = set(real_relationships)
    assert expected_types.issubset(actual_types), f"Expected {expected_types} to be subset of {actual_types}"


@pytest.mark.asyncio(loop_scope="function")
async def test_get_relationships_between_nodes_real_db():
    """Test getting relationships between nodes using the real Neo4j database"""
    
    # Get connection details from environment variables
    db_url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "<setApassword123>")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    # Create connection to real database
    neo4j_driver = AsyncGraphDatabase.driver(
        db_url,
        auth=(username, password)
    )
    
    try:
        # Create MCP server with real database connection
        mcp_server = create_mcp_server(neo4j_driver, database)
        
        # Test getting relationships between users and groups (from your real data)
        response = await mcp_server.call_tool("get_relationships_between_nodes", {
            "node1": "users",
            "node2": "groups"
        })
        
        print(f"\nReal DB test response: {response}")
        # Handle the tuple response format
        content_list, _ = response
        result = json.loads(content_list[0].text)
        print(f"Real DB test result: {result}")
        
        # Verify the response structure
        assert isinstance(result, list)
        assert len(result) == 1
        
        # Check that we get the expected relationship types
        relationships = result[0]
        assert "relationship_types" in relationships
        relationship_types = relationships["relationship_types"]
        
        # Should contain the relationship types we discovered earlier
        assert isinstance(relationship_types, list)
        # Based on your earlier query, should contain "USER" and "GROUP"
        expected_types = {"USER", "GROUP"}
        actual_types = set(relationship_types)
        assert expected_types.issubset(actual_types), f"Expected {expected_types} to be subset of {actual_types}"
        
        # Test with another real relationship from your database
        response_roles = await mcp_server.call_tool("get_relationships_between_nodes", {
            "node1": "users", 
            "node2": "role"
        })
        
        # Handle the tuple response format
        content_list_roles, _ = response_roles
        result_roles = json.loads(content_list_roles[0].text)
        print(f"Users-Role relationship result: {result_roles}")
        
        # Should also have relationships
        assert isinstance(result_roles, list)
        assert len(result_roles) == 1
        role_relationships = result_roles[0]["relationship_types"]
        assert isinstance(role_relationships, list)
        # Based on earlier query, should contain "ROLE" and "USER"
        expected_role_types = {"ROLE", "USER"}
        actual_role_types = set(role_relationships)
        assert expected_role_types.issubset(actual_role_types), f"Expected {expected_role_types} to be subset of {actual_role_types}"
        
    finally:
        # Clean up the database connection
        await neo4j_driver.close()
