# Development Instructions for Assistant

## Testing changes to server.py

begin in the folder `/c/repositories/ais/ais-mcp-neo4j/servers/mcp-neo4j-cypher`  
1. Given a failing test, modify server.py to address the failure.
2. Re-run the test with this command, remember to substitute <function_name> with the actual test function name.
pytest tests/integration/test_server_IT.py::<function_name> -v -s
3. If the test still fails:
    a) prompt if you want to make changes to the test itself
    b) repeat from step 1 as many as 10 times.
4. Rebuild and run the docker container with these instructions:
```
pushd /c/repositories/ais/ais-hypernova/docker
docker compose up -d mcp-neo4j-cypher --build
sleep 3
popd
```
