import os
from typing import Any

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase, GraphDatabase

from mcp_neo4j_cypher.server import create_mcp_server


@pytest_asyncio.fixture(scope="function")
async def async_neo4j_driver():
    """Create async Neo4j driver using environment variables for real database connection"""
    db_url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "<setApassword123>")
    
    driver = AsyncGraphDatabase.driver(
        db_url, auth=(username, password)
    )
    try:
        yield driver
    finally:
        await driver.close()


@pytest_asyncio.fixture(scope="function")
async def mcp_server(async_neo4j_driver):
    """Create MCP server with real database connection"""
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    mcp = create_mcp_server(async_neo4j_driver, database)
    return mcp


@pytest.fixture(scope="function")
def sync_neo4j_driver():
    """Create sync Neo4j driver for test data setup/cleanup"""
    db_url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "<setApassword123>")
    
    driver = GraphDatabase.driver(db_url, auth=(username, password))
    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture(scope="function")
def init_test_data(sync_neo4j_driver, clear_test_data: Any):
    """Initialize test data in real database (only for container-based tests)"""
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    with sync_neo4j_driver.session(database=database) as session:
        session.run("CREATE (a:Person {name: 'Alice', age: 30})")
        session.run("CREATE (b:Person {name: 'Bob', age: 25})")
        session.run("CREATE (c:Person {name: 'Charlie', age: 35})")
        session.run(
            "MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'}) CREATE (a)-[:FRIEND]->(b)"
        )
        session.run(
            "MATCH (b:Person {name: 'Bob'}), (c:Person {name: 'Charlie'}) CREATE (b)-[:FRIEND]->(c)"
        )


@pytest.fixture(scope="function")
def clear_test_data(sync_neo4j_driver):
    """Clear test data from real database (use with caution!)"""
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    with sync_neo4j_driver.session(database=database) as session:
        # WARNING: This deletes ALL Person nodes and FRIEND relationships
        # Only use this for dedicated test databases!
        session.run("MATCH (n:Person) DETACH DELETE n")
