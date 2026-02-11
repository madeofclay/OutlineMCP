"""
Simple MCP Stdio Bridge - HTTP-based MCP proxy
Connects via HTTP to the FastAPI proxy and streams MCP protocol
"""

import asyncio
import json
import logging
import httpx

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
HTTP_PROXY_URL = "http://localhost:8000"
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 9000


async def handle_client_connection(reader, writer):
    """Handle incoming client connection"""
    addr = writer.get_extra_info('peername')
    logger.info(f"Client connected from {addr}")

    api_key = None

    try:
        while True:
            try:
                # Read a line from the client
                line = await asyncio.wait_for(
                    reader.readline(),
                    timeout=300.0  # 5 minute timeout
                )

                if not line:
                    logger.info("Client disconnected")
                    break

                try:
                    message = json.loads(line.decode().strip())
                    logger.debug(f"Received: {message}")

                    # Extract API key if provided
                    params = message.get("params", {})
                    if "X-Outline-API-Key" in params:
                        api_key = params["X-Outline-API-Key"]
                        logger.info(f"API key set from client")

                    # Handle based on method
                    method = message.get("method")
                    request_id = message.get("id")

                    if method == "initialize":
                        # Send initialize response
                        response = {
                            "jsonrpc": "2.0",
                            "result": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {
                                    "resources": {"subscribe": False}
                                },
                                "serverInfo": {
                                    "name": "Outline MCP Stdio Bridge",
                                    "version": "2.0.0"
                                }
                            },
                            "id": request_id
                        }
                        writer.write(json.dumps(response).encode() + b'\n')
                        await writer.drain()

                    elif api_key:
                        # Forward request to HTTP proxy
                        headers = {"X-Outline-API-Key": api_key}

                        try:
                            async with httpx.AsyncClient(timeout=90.0) as client:
                                # Send as POST to the proxy
                                response = await client.post(
                                    f"{HTTP_PROXY_URL}/",  # Root endpoint proxies MCP
                                    json=message,
                                    headers=headers
                                )

                                if response.status_code == 200:
                                    try:
                                        result = response.json()
                                        writer.write(json.dumps(result).encode() + b'\n')
                                        await writer.drain()
                                    except:
                                        # If not JSON, just forward response
                                        logger.warning(f"Non-JSON response from proxy: {response.text[:100]}")
                                        error = {
                                            "jsonrpc": "2.0",
                                            "error": {
                                                "code": -32603,
                                                "message": f"Proxy error: {response.status_code}"
                                            },
                                            "id": request_id
                                        }
                                        writer.write(json.dumps(error).encode() + b'\n')
                                        await writer.drain()
                                else:
                                    logger.error(f"Proxy returned {response.status_code}")
                                    error = {
                                        "jsonrpc": "2.0",
                                        "error": {
                                            "code": response.status_code,
                                            "message": f"HTTP {response.status_code}"
                                        },
                                        "id": request_id
                                    }
                                    writer.write(json.dumps(error).encode() + b'\n')
                                    await writer.drain()

                        except Exception as e:
                            logger.error(f"Error proxying request: {e}")
                            error = {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32603,
                                    "message": f"Proxy error: {str(e)}"
                                },
                                "id": request_id
                            }
                            writer.write(json.dumps(error).encode() + b'\n')
                            await writer.drain()

                    else:
                        # No API key set
                        error = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": "API key required. Pass X-Outline-API-Key in params or as first message param"
                            },
                            "id": request_id
                        }
                        writer.write(json.dumps(error).encode() + b'\n')
                        await writer.drain()

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32700,
                            "message": "Parse error"
                        },
                        "id": None
                    }
                    writer.write(json.dumps(error_response).encode() + b'\n')
                    await writer.drain()

            except asyncio.TimeoutError:
                logger.warning("Client timeout")
                break

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info(f"Connection closed: {addr}")


async def run_server():
    """Run the stdio bridge server"""
    server = await asyncio.start_server(
        handle_client_connection,
        LISTEN_HOST,
        LISTEN_PORT
    )

    addr = server.sockets[0].getsockname()
    logger.info(f"MCP Stdio Bridge listening on {addr[0]}:{addr[1]}")
    logger.info(f"Proxy backend: {HTTP_PROXY_URL}")
    logger.info(f"Connection command: nc {addr[0]} {addr[1]}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped")
