"""
MCP Stdio Bridge Server
Exposes the HTTP proxy as a stdio MCP server accessible via TCP
"""

import asyncio
import json
import logging
import sys
from typing import Optional
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

class MCPStdioHandler:
    """Handles MCP stdio protocol over TCP connection"""

    def __init__(self, reader, writer, api_key: Optional[str] = None):
        self.reader = reader
        self.writer = writer
        self.api_key = api_key
        self.request_id_counter = 0

    async def handle_client(self):
        """Main message loop for client"""
        try:
            while True:
                # Read a line from the client
                line = await asyncio.wait_for(
                    self.reader.readline(),
                    timeout=300.0  # 5 minute timeout
                )

                if not line:
                    logger.info("Client disconnected")
                    break

                try:
                    message = json.loads(line.decode().strip())
                    logger.debug(f"Received: {message}")

                    response = await self.handle_message(message)

                    if response:
                        response_line = json.dumps(response)
                        self.writer.write(response_line.encode() + b'\n')
                        await self.writer.drain()
                        logger.debug(f"Sent: {response}")

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
                    self.writer.write(json.dumps(error_response).encode() + b'\n')
                    await self.writer.drain()

        except asyncio.TimeoutError:
            logger.warning("Client timeout")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def handle_message(self, message: dict) -> Optional[dict]:
        """Handle MCP protocol message"""

        msg_type = message.get("jsonrpc")
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})

        logger.info(f"Method: {method}, ID: {request_id}")

        # Handle initialize
        if method == "initialize":
            return await self.handle_initialize(request_id)

        # Handle list_resources
        elif method == "resources/list":
            return await self.handle_list_resources(request_id)

        # Handle read_resource
        elif method == "resources/read":
            return await self.handle_read_resource(request_id, params)

        # Handle generic proxy request
        elif method and method.startswith("outline/"):
            return await self.handle_outline_request(request_id, method, params)

        # Unknown method
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": request_id
            }

    async def handle_initialize(self, request_id):
        """Handle MCP initialize request"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "resources": {
                        "subscribe": False
                    }
                },
                "serverInfo": {
                    "name": "Outline MCP Stdio Bridge",
                    "version": "1.0.0"
                }
            },
            "id": request_id
        }

    async def handle_list_resources(self, request_id):
        """Handle list_resources request"""
        try:
            headers = {"X-Outline-API-Key": self.api_key} if self.api_key else {}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{HTTP_PROXY_URL}/api/documents.list",
                    headers=headers
                )

                if response.status_code == 200:
                    documents = response.json().get("data", [])
                    resources = [
                        {
                            "uri": f"outline://document/{doc.get('id', i)}",
                            "name": doc.get('title', 'Untitled'),
                            "mimeType": "text/plain"
                        }
                        for i, doc in enumerate(documents)
                    ]

                    return {
                        "jsonrpc": "2.0",
                        "result": {"resources": resources},
                        "id": request_id
                    }
                else:
                    raise Exception(f"HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": request_id
            }

    async def handle_read_resource(self, request_id, params):
        """Handle read_resource request"""
        uri = params.get("uri", "")

        try:
            # Extract document ID from URI (outline://document/123)
            if uri.startswith("outline://document/"):
                doc_id = uri.replace("outline://document/", "")

                headers = {"X-Outline-API-Key": self.api_key} if self.api_key else {}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"{HTTP_PROXY_URL}/api/documents.info",
                        params={"id": doc_id},
                        headers=headers
                    )

                    if response.status_code == 200:
                        doc = response.json().get("data", {})
                        content = doc.get('text', '') or doc.get('body', '')

                        return {
                            "jsonrpc": "2.0",
                            "result": {
                                "contents": [
                                    {
                                        "uri": uri,
                                        "mimeType": "text/plain",
                                        "text": content
                                    }
                                ]
                            },
                            "id": request_id
                        }
                    else:
                        raise Exception(f"HTTP {response.status_code}")
            else:
                raise Exception(f"Invalid URI format: {uri}")

        except Exception as e:
            logger.error(f"Error reading resource: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": request_id
            }

    async def handle_outline_request(self, request_id, method, params):
        """Handle generic Outline API request via proxy"""
        try:
            # Extract endpoint from method (outline/api.documents.list -> /api/documents.list)
            endpoint = method.replace("outline/", "/")

            headers = {"X-Outline-API-Key": self.api_key} if self.api_key else {}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{HTTP_PROXY_URL}{endpoint}",
                    json=params,
                    headers=headers
                )

                result = response.json() if response.status_code < 400 else {
                    "error": response.text
                }

                if response.status_code == 200:
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": response.status_code,
                            "message": f"HTTP {response.status_code}",
                            "data": result
                        },
                        "id": request_id
                    }

        except Exception as e:
            logger.error(f"Error handling Outline request: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": request_id
            }


async def handle_client_connection(reader, writer):
    """Handle incoming client connection"""
    addr = writer.get_extra_info('peername')
    logger.info(f"Client connected from {addr}")

    # Extract API key from first message or environment
    api_key = None  # Will be provided by client in first message

    handler = MCPStdioHandler(reader, writer, api_key)
    await handler.handle_client()


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
