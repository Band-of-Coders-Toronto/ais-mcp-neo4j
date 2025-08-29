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
    # Should contain directional relationships based on new format
    # Extract relationship types from the directional format
    extracted_types = set()
    for rel in real_relationships:
        if ':' in rel:
            # Extract type after the colon
            rel_type = rel.split(':')[1]
            if rel_type:  # Only add non-empty types
                extracted_types.add(rel_type)
    
    expected_types = {"USER", "GROUP"}
    assert expected_types.issubset(extracted_types), f"Expected {expected_types} to be subset of extracted types {extracted_types} from {real_relationships}"


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
        
        # Query directed relationships users -> groups
        response_forward = await mcp_server.call_tool("read_neo4j_cypher", {
            "query": "MATCH (u:users)-[r]->(g:groups) RETURN collect(DISTINCT type(r)) AS relationship_types"
        })
        content_list_forward, _ = response_forward
        result_forward = json.loads(content_list_forward[0].text)
        forward_types = result_forward[0]["relationship_types"] if result_forward else []
        
        # Query directed relationships groups -> users  
        response_backward = await mcp_server.call_tool("read_neo4j_cypher", {
            "query": "MATCH (g:groups)-[r]->(u:users) RETURN collect(DISTINCT type(r)) AS relationship_types"
        })
        content_list_backward, _ = response_backward
        result_backward = json.loads(content_list_backward[0].text)
        backward_types = result_backward[0]["relationship_types"] if result_backward else []
        
        # Query undirected relationships (both ways)
        response_undirected = await mcp_server.call_tool("read_neo4j_cypher", {
            "query": "MATCH (u:users)-[r]-(g:groups) RETURN collect(DISTINCT type(r)) AS relationship_types"
        })
        content_list_undirected, _ = response_undirected
        result_undirected = json.loads(content_list_undirected[0].text)
        all_undirected_types = result_undirected[0]["relationship_types"] if result_undirected else []
        
        # Calculate truly undirected relationships (those that appear in both directions)
        forward_set = set(forward_types)
        backward_set = set(backward_types)
        all_directed = forward_set.union(backward_set)
        truly_undirected = [rel for rel in all_undirected_types if rel not in all_directed]
        
        # Format the output as requested
        formatted_relationships = []
        
        # Add directed relationships users -> groups
        for rel_type in forward_types:
            formatted_relationships.append(f"users->groups:{rel_type}")
        
        # Add directed relationships groups -> users
        for rel_type in backward_types:
            formatted_relationships.append(f"groups->users:{rel_type}")
        
        # Add undirected relationships (empty list after colon if none)
        undirected_str = ",".join(truly_undirected) if truly_undirected else ""
        formatted_relationships.append(f"users-groups:{undirected_str}")
        
                # Create the formatted result
        formatted_result = [{"relationship_types": formatted_relationships}]
        
        print(f"\nFormatted relationship result: {formatted_result}")
        
        # Verify we got some relationships
        assert len(formatted_relationships) > 0, "Expected to find some relationships"
        
        # Verify the format is correct
        for rel in formatted_relationships:
            assert ":" in rel, f"Expected colon in relationship format: {rel}"
            if "->" in rel:
                assert rel.count("->") == 1, f"Expected exactly one -> in directed relationship: {rel}"
            elif "-" in rel and "->" not in rel:
                assert rel.count("-") == 1, f"Expected exactly one - in undirected relationship: {rel}"
        
        # Test the current tool implementation (this will show it doesn't match our expected format yet)
        tool_response = await mcp_server.call_tool("get_relationships_between_nodes", {
            "node1": "users",
            "node2": "groups"
        })
        
        # Extract the tool response correctly (handle tuple format)
        content_list, _ = tool_response
        tool_response_text = json.loads(content_list[0].text)
        print(f"Tool response: {tool_response_text}")
        
        # Show what we expect vs what we get
        print(f"Expected output: {formatted_result}")
        
        # This assertion will FAIL until the tool is updated to return directional relationships
        assert tool_response_text == formatted_result, f"EXPECTED FAILURE: Tool should return {formatted_result}, but currently returns {tool_response_text}. Tool needs to be updated to support directional relationship format."
        
    finally:
        # Clean up the database connection
        await neo4j_driver.close()


@pytest.mark.asyncio(loop_scope="function")
async def test_find_customer_by_name(mcp_server: FastMCP):
    """Test finding customers by name - this test should fail until the tool is implemented"""
    
    # Test searching for a customer by name
    search_name = "Abusus enim multitudine hominum-101"
    response = await mcp_server.call_tool("find_customer_by_name", {
        "name": search_name
    })
    
    print(f"find_customer_by_name response: {response}")
    
    # Handle the tuple response format
    content_list, _ = response
    result = json.loads(content_list[0].text)
    print(f"find_customer_by_name result: {result}")
    
    # Expected structure: list of customer objects with at least name property
    assert isinstance(result, list), "Expected list of customers"
    

    # Should return customers that match the search term
    if result:  # If customers found
        for customer in result:
            assert isinstance(customer, dict), "Each customer should be a dict"
            assert "name" in customer, "Each customer should have a name field"
            # Name should contain the search term (case insensitive)
            assert search_name.lower() in customer["name"].lower(), f"Customer name '{customer['name']}' should contain '{search_name}'"
            # Verify other expected fields exist
            assert "id" in customer, "Each customer should have an id field"
    
    # Test with a more specific search
    response_specific = await mcp_server.call_tool("find_customer_by_name", {
        "name": "Smith"
    })
    
    content_list_specific, _ = response_specific
    result_specific = json.loads(content_list_specific[0].text)
    print(f"Specific search result: {result_specific}")
    
    # Verify structure is consistent
    assert isinstance(result_specific, list), "Expected list of customers for specific search"
    
    # Test edge case: empty search should return error or empty list
    response_empty = await mcp_server.call_tool("find_customer_by_name", {
        "name": ""
    })
    
    content_list_empty, _ = response_empty
    result_empty = json.loads(content_list_empty[0].text)
    print(f"Empty search result: {result_empty}")
    
    # Should handle empty search gracefully
    assert isinstance(result_empty, list), "Empty search should return a list"


@pytest.mark.asyncio(loop_scope="function")
async def test_get_customer_requests(mcp_server: FastMCP):
    """Test getting customer requests - this test should fail until the tool is implemented"""
    
    # Test getting customer requests for a specific customer ID
    customer_id = "181"  # Using a customer we know exists
    response = await mcp_server.call_tool("get_customer_requests", {
        "customer_id": customer_id
    })
    
    print(f"get_customer_requests response: {response}")
    
    # Handle the tuple response format
    content_list, _ = response
    result = json.loads(content_list[0].text)
    print(f"get_customer_requests result: {result}")
    
    # Expected structure: list of customer_request objects
    assert isinstance(result, list), "Expected list of customer requests"
    
    # If there are customer requests, verify their structure
    if result:
        for request in result:
            assert isinstance(request, dict), "Each customer request should be a dict"
            # Verify expected fields exist (based on actual data structure)
            expected_fields = ["id", "created_on", "number"]
            for field in expected_fields:
                assert field in request, f"Each customer request should have a '{field}' field"
    
    # Test with a non-existent customer ID
    response_nonexistent = await mcp_server.call_tool("get_customer_requests", {
        "customer_id": "999999"
    })
    
    content_list_nonexistent, _ = response_nonexistent
    result_nonexistent = json.loads(content_list_nonexistent[0].text)
    print(f"Non-existent customer requests result: {result_nonexistent}")
    
    # Should return empty list for non-existent customer
    assert isinstance(result_nonexistent, list), "Expected list for non-existent customer"
    assert len(result_nonexistent) == 0, "Should return empty list for non-existent customer"
    
    # Test with invalid input (empty customer_id)
    response_empty = await mcp_server.call_tool("get_customer_requests", {
        "customer_id": ""
    })
    
    content_list_empty, _ = response_empty
    result_empty = json.loads(content_list_empty[0].text)
    print(f"Empty customer_id result: {result_empty}")
    
    # Should handle empty customer_id gracefully (either error or empty list)
    assert isinstance(result_empty, (list, dict)), "Empty customer_id should return list or error object"


