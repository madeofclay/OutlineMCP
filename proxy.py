"""
Outline MCP Proxy Server
Manages per-user Docker containers with auto-sleep (15 min idle timeout)
"""

import asyncio
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from time import time

import docker
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager
import uvicorn

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ContainerInfo:
    """Information about a tracked container"""
    container_name: str
    api_key_hash: str
    port: int
    last_used: float
    created_at: float
    status: str  # 'running' or 'stopped'

    def to_dict(self):
        return asdict(self)

# ============================================================================
# GLOBAL STATE
# ============================================================================

# Container registry: hash -> ContainerInfo
container_registry: Dict[str, ContainerInfo] = {}

# Port allocator
allocated_ports: set = set()
NEXT_PORT = 4000
MAX_PORT = 5000

# Cleanup task handle
cleanup_task: Optional[asyncio.Task] = None

# Docker client
docker_client: Optional[docker.DockerClient] = None

# Configuration
IDLE_TIMEOUT_SECONDS = 15 * 60  # 15 minutes
CONTAINER_IMAGE = "ghcr.io/vortiago/mcp-outline:latest"
CONTAINER_MEMORY = "256m"
CONTAINER_CPU = "0.3"
REQUEST_TIMEOUT = 90  # seconds

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def hash_api_key(api_key: str) -> str:
    """Generate container name from API key (first 12 chars of SHA256)"""
    hash_obj = hashlib.sha256(api_key.encode())
    return f"mcp-{hash_obj.hexdigest()[:12]}"


async def validate_outline_key(api_key: str) -> bool:
    """Validate API key by calling Outline's auth.info endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://app.getoutline.com/api/auth.info",
                headers={"Authorization": f"Bearer {api_key}"},
                json={}
            )
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to validate API key: {str(e)}")
        # For now, return False on any error - be conservative
        return False


def get_next_available_port() -> int:
    """Find next available port for container"""
    global NEXT_PORT, allocated_ports

    # Get ports already in use by Docker containers
    try:
        client = get_docker_client()
        containers = client.containers.list(all=True)
        used_ports = set()
        for container in containers:
            ports = container.ports
            if ports and '3000/tcp' in ports:
                port = int(ports['3000/tcp'][0]['HostPort'])
                used_ports.add(port)
    except Exception as e:
        logger.warning(f"Could not get Docker ports: {str(e)}")
        used_ports = set()

    # Find first available port
    for port in range(NEXT_PORT, MAX_PORT):
        if port not in allocated_ports and port not in used_ports:
            allocated_ports.add(port)
            return port

    raise RuntimeError(f"No available ports (max: {MAX_PORT})")


# ============================================================================
# DOCKER MANAGEMENT FUNCTIONS
# ============================================================================

def get_docker_client() -> docker.DockerClient:
    """Get or create Docker client"""
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


def is_container_running(name: str) -> bool:
    """Check if container is currently running"""
    try:
        client = get_docker_client()
        container = client.containers.get(name)
        return container.status == "running"
    except docker.errors.NotFound:
        return False
    except Exception as e:
        logger.error(f"Error checking container status: {str(e)}")
        return False


def is_container_stopped(name: str) -> bool:
    """Check if container exists but is stopped"""
    try:
        client = get_docker_client()
        container = client.containers.get(name)
        return container.status != "running"
    except docker.errors.NotFound:
        return False
    except Exception as e:
        logger.error(f"Error checking container status: {str(e)}")
        return False


def start_existing_container(name: str) -> bool:
    """Start a stopped container"""
    try:
        client = get_docker_client()
        container = client.containers.get(name)
        if container.status != "running":
            logger.info(f"Starting existing container: {name}")
            container.start()
            # Wait a moment for container to be ready
            return True
        return True
    except Exception as e:
        logger.error(f"Error starting container {name}: {str(e)}")
        return False


def create_container(api_key: str, port: int) -> Optional[str]:
    """Create a new Docker container for the user"""
    container_name = hash_api_key(api_key)

    try:
        client = get_docker_client()

        # Pull image if needed (silently)
        try:
            logger.info(f"Pulling image: {CONTAINER_IMAGE}")
            client.images.pull(CONTAINER_IMAGE)
        except Exception as e:
            logger.warning(f"Could not pull image: {str(e)}")

        # Create container
        logger.info(f"Creating container: {container_name} on port {port}")

        container = client.containers.create(
            CONTAINER_IMAGE,
            name=container_name,
            ports={"3000/tcp": port},
            environment={
                "OUTLINE_API_KEY": api_key,
                "OUTLINE_API_URL": "https://app.getoutline.com",
                "MCP_TRANSPORT": "streamable-http",
                "MCP_HOST": "0.0.0.0",
                "MCP_PORT": "3000",
            },
            mem_limit=CONTAINER_MEMORY,
            memswap_limit=CONTAINER_MEMORY,
            nano_cpus=int(float(CONTAINER_CPU) * 1e9),
            restart_policy={"Name": "unless-stopped"},
            network_mode="bridge",
        )

        # Start the container
        container.start()
        logger.info(f"Container started: {container_name}")
        return container_name

    except docker.errors.ImageNotFound:
        logger.error(f"Image not found: {CONTAINER_IMAGE}")
        return None
    except docker.errors.ContainerError as e:
        logger.error(f"Container error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error creating container: {str(e)}")
        return None


def get_container_info(name: str) -> Optional[Dict]:
    """Get detailed info about a container"""
    try:
        client = get_docker_client()
        container = client.containers.get(name)

        return {
            "name": container.name,
            "status": container.status,
            "ports": container.ports,
            "created": container.attrs["Created"],
            "image": container.image.tags[0] if container.image.tags else "unknown",
        }
    except Exception as e:
        logger.error(f"Error getting container info: {str(e)}")
        return None


# ============================================================================
# MAIN PROXY LOGIC
# ============================================================================

async def create_or_start_container(api_key: str) -> Tuple[int, str]:
    """
    Main logic: Get or create container for user
    Returns: (port, container_name)
    """
    api_key_hash = hash_api_key(api_key)
    container_name = hash_api_key(api_key)  # Deterministic name

    # Case 1: Container already tracked in registry
    if api_key_hash in container_registry:
        info = container_registry[api_key_hash]
        logger.info(f"Found existing container in registry: {info.container_name}")

        # Case 1a: Container is running
        if is_container_running(info.container_name):
            info.last_used = time()
            logger.debug(f"Container already running: {info.container_name}")
            return info.port, info.container_name

        # Case 1b: Container is stopped, restart it
        if is_container_stopped(info.container_name):
            logger.info(f"Restarting stopped container: {info.container_name}")
            if start_existing_container(info.container_name):
                info.last_used = time()
                info.status = "running"
                await asyncio.sleep(1)  # Give container time to start
                return info.port, info.container_name
            else:
                logger.error(f"Failed to restart container: {info.container_name}")
                # Fall through to create new one
                del container_registry[api_key_hash]

    # Case 2: Container exists on disk but not in registry (e.g., after proxy restart)
    if is_container_stopped(container_name):
        logger.info(f"Found stopped container on disk (not in registry): {container_name}")
        # Try to get port from existing container
        try:
            client = get_docker_client()
            container = client.containers.get(container_name)
            port_bindings = container.ports

            # Extract port from binding like {'3000/tcp': [{'HostPort': '4000', ...}]}
            # Only proceed if ports are correctly bound
            if port_bindings and '3000/tcp' in port_bindings:
                port = int(port_bindings['3000/tcp'][0]['HostPort'])
                # Mark port as allocated
                allocated_ports.add(port)

                # Restart container
                if start_existing_container(container_name):
                    container_registry[api_key_hash] = ContainerInfo(
                        container_name=container_name,
                        api_key_hash=api_key_hash,
                        port=port,
                        last_used=time(),
                        created_at=time(),
                        status="running"
                    )
                    logger.info(f"Restarted container from disk: {container_name} on port {port}")
                    await asyncio.sleep(1)
                    return port, container_name
            else:
                logger.warning(f"Container {container_name} exists but has no valid port bindings, removing it")
                container.remove(force=True)
        except Exception as e:
            logger.warning(f"Could not reuse existing container: {str(e)}, removing it")
            try:
                client = get_docker_client()
                container = client.containers.get(container_name)
                container.remove(force=True)
            except:
                pass
            # Fall through to create new one

    if is_container_running(container_name):
        logger.info(f"Found running container on disk (not in registry): {container_name}")
        # Container is somehow running but not in registry, try to add it back
        try:
            client = get_docker_client()
            container = client.containers.get(container_name)
            port_bindings = container.ports

            # Only proceed if ports are correctly bound
            if port_bindings and '3000/tcp' in port_bindings:
                port = int(port_bindings['3000/tcp'][0]['HostPort'])
                allocated_ports.add(port)

                container_registry[api_key_hash] = ContainerInfo(
                    container_name=container_name,
                    api_key_hash=api_key_hash,
                    port=port,
                    last_used=time(),
                    created_at=time(),
                    status="running"
                )
                logger.info(f"Recovered running container to registry: {container_name} on port {port}")
                return port, container_name
            else:
                logger.warning(f"Container {container_name} is running but has no valid port bindings, stopping it")
                container.stop()
        except Exception as e:
            logger.warning(f"Could not recover running container: {str(e)}")

    # Case 3: Container doesn't exist anywhere, create new one
    logger.info(f"Creating new container for API key hash: {api_key_hash}")
    port = get_next_available_port()

    created_name = create_container(api_key, port)
    if not created_name:
        raise RuntimeError("Failed to create container")

    # Wait for container to be ready
    await asyncio.sleep(2)

    # Register in memory
    container_registry[api_key_hash] = ContainerInfo(
        container_name=created_name,
        api_key_hash=api_key_hash,
        port=port,
        last_used=time(),
        created_at=time(),
        status="running"
    )

    logger.info(f"Container ready: {created_name} on port {port}")
    return port, created_name


async def proxy_request(
    port: int,
    path: str,
    request: Request,
    api_key: str
) -> StreamingResponse:
    """
    Proxy HTTP request to the container
    """
    url = f"http://localhost:{port}/{path}"

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # Build headers for proxy request
            # Start with a minimal set of important headers
            proxy_headers = {}

            # Copy relevant headers from original request
            headers_to_forward = ["content-type", "authorization", "user-agent"]
            for header_name in headers_to_forward:
                if header_name in request.headers:
                    proxy_headers[header_name] = request.headers[header_name]

            # Set Accept header for MCP streamable-http protocol
            # The container requires both application/json and text/event-stream
            proxy_headers["accept"] = "application/json, text/event-stream"

            # Read body if present
            body = b""
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()

            response = await client.request(
                method=request.method,
                url=url,
                headers=proxy_headers,
                content=body,
            )

            return StreamingResponse(
                iter([response.content]),
                status_code=response.status_code,
                headers=dict(response.headers),
            )

    except httpx.TimeoutException:
        logger.error(f"Timeout proxying request to {url}")
        raise HTTPException(status_code=504, detail="Gateway Timeout")
    except Exception as e:
        import traceback
        logger.error(f"Error proxying request to {url}: {type(e).__name__}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=502, detail="Bad Gateway")


# ============================================================================
# BACKGROUND CLEANUP TASK
# ============================================================================

async def cleanup_idle_containers():
    """
    Background task: Stop containers idle for > 15 minutes
    Runs every 60 seconds
    """
    while True:
        try:
            await asyncio.sleep(60)

            current_time = time()
            idle_keys = []

            for api_key_hash, info in container_registry.items():
                idle_duration = current_time - info.last_used
                idle_minutes = idle_duration / 60

                if idle_duration > IDLE_TIMEOUT_SECONDS:
                    logger.info(
                        f"Stopping idle container {info.container_name} "
                        f"(idle for {idle_minutes:.1f} minutes)"
                    )

                    try:
                        client = get_docker_client()
                        container = client.containers.get(info.container_name)
                        container.stop()
                        info.status = "stopped"
                    except Exception as e:
                        logger.error(f"Error stopping container: {str(e)}")

                    idle_keys.append(api_key_hash)

            # Update registry
            for key in idle_keys:
                container_registry[key].status = "stopped"

        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")


# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown"""
    global cleanup_task

    # Startup
    logger.info("Starting Outline MCP Proxy Server")
    try:
        client = get_docker_client()
        client.ping()
        logger.info("Docker connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to Docker: {str(e)}")

    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_idle_containers())
    logger.info("Cleanup task started")

    yield

    # Shutdown
    logger.info("Shutting down")
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Outline MCP Proxy",
    description="Per-user Docker proxy for Outline MCP",
    lifespan=lifespan,
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    running_count = sum(
        1 for info in container_registry.values()
        if info.status == "running"
    )
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "containers_tracked": len(container_registry),
        "containers_running": running_count,
    }


@app.get("/stats")
async def get_stats(authorization: Optional[str] = Header(None)):
    """
    Get detailed statistics (requires auth)
    Note: Nginx will handle basic auth, but we can add extra checks here
    """
    stats = []

    for api_key_hash, info in container_registry.items():
        container_info = get_container_info(info.container_name)
        idle_seconds = time() - info.last_used

        stats.append({
            "container_name": info.container_name,
            "api_key_hash": api_key_hash,
            "port": info.port,
            "status": info.status,
            "created_at": datetime.fromtimestamp(info.created_at, tz=timezone.utc).isoformat(),
            "last_used": datetime.fromtimestamp(info.last_used, tz=timezone.utc).isoformat(),
            "idle_seconds": int(idle_seconds),
            "idle_minutes": round(idle_seconds / 60, 1),
            "container_info": container_info,
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_containers": len(container_registry),
        "running_count": sum(1 for s in stats if s["status"] == "running"),
        "stopped_count": sum(1 for s in stats if s["status"] == "stopped"),
        "containers": stats,
    }


@app.post("/mcp")
@app.post("/")
async def mcp_http_endpoint(
    request: Request,
    x_outline_api_key: Optional[str] = Header(None),
):
    """
    MCP HTTP Protocol endpoint
    Handles JSON-RPC requests from Claude Code or other MCP clients
    Both /mcp and / paths are supported
    """
    # Step 1: Validate API key header
    if not x_outline_api_key:
        logger.warning("Request missing X-Outline-API-Key header")
        raise HTTPException(status_code=400, detail="Missing X-Outline-API-Key header")

    # Step 2: Validate against Outline
    logger.debug(f"Validating API key")
    is_valid = await validate_outline_key(x_outline_api_key)
    if not is_valid:
        logger.warning(f"Invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Step 3: Get or create container
    try:
        port, container_name = await create_or_start_container(x_outline_api_key)
        logger.info(f"MCP request routed to {container_name} on port {port}")
    except Exception as e:
        logger.error(f"Failed to get/create container: {str(e)}")
        raise HTTPException(status_code=503, detail="Container service unavailable")

    # Step 4: Proxy request to container (/mcp endpoint on container)
    return await proxy_request(port, "mcp", request, x_outline_api_key)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(
    path: str,
    request: Request,
    x_outline_api_key: Optional[str] = Header(None),
):
    """
    Legacy proxy endpoint
    Routes requests to per-user containers
    """
    # Step 1: Validate API key header
    if not x_outline_api_key:
        logger.warning("Request missing X-Outline-API-Key header")
        raise HTTPException(status_code=400, detail="Missing X-Outline-API-Key header")

    # Step 2: Validate against Outline
    logger.debug(f"Validating API key")
    is_valid = await validate_outline_key(x_outline_api_key)
    if not is_valid:
        logger.warning(f"Invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Step 3: Get or create container
    try:
        port, container_name = await create_or_start_container(x_outline_api_key)
        logger.info(f"Request routed to {container_name} on port {port}")
    except Exception as e:
        logger.error(f"Failed to get/create container: {str(e)}")
        raise HTTPException(status_code=503, detail="Container service unavailable")

    # Step 4: Proxy request
    return await proxy_request(port, path, request, x_outline_api_key)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "proxy:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
