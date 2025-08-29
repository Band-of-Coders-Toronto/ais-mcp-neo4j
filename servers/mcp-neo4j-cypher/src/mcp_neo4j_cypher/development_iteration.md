# Development Instructions for Assistant

## Testing changes to server.py

For all shell commands, substitute home_folder with the value '/c/repositories/ais'

begin in the folder `home_folder/ais-mcp-neo4j/servers/mcp-neo4j-cypher`  
1. Given a failing test, modify server.py to address the failure.
2. Re-run the test with this command, remember to substitute <function_name> with the actual test function name.
```
pytest tests/integration/test_server_IT.py::<function_name> -v -s
```
3. If the test still fails:
    a) prompt if you want to make changes to the test itself
    b) repeat from step 1 as many as 10 times.
4. When that test passes, run the entire set of tests.
```
pytest tests/integration/test_server_IT.py -v -s
```
5. If all tests pass, rebuild and run the docker container with the following instructions. Otherwise, report on the failing tests, but don't fix them/
```
pushd home_folder/ais-hypernova/docker
docker compose up -d mcp-neo4j-cypher --build
sleep 3
popd
```
