from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import docker
import socket
import time

app = FastAPI()
client = docker.from_env()

CONTAINER_NAME = "minecraft"
HOMER_URL = "https://dash.hamishburke.dev"  # keep this for compatibility

MC_HOST = "127.0.0.1"
MC_PORT = 25565


# serve the static site from ./static
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/toggle_mc")
def toggle_mc_redirect():
    """
    Existing endpoint kept for Homer compatibility. It redirects to HOMER_URL.
    """
    try:
        container = client.containers.get(CONTAINER_NAME)
        if container.status == "running":
            container.stop()
        else:
            container.start()
    except Exception as e:
        return RedirectResponse(url=f"{HOMER_URL}?error={str(e)}")

    return RedirectResponse(url=HOMER_URL)


@app.post("/api/toggle")
def api_toggle():
    """
    JSON-friendly toggle endpoint for the UI.
    Starts or stops the container and returns JSON with the new status.
    """
    try:
        container = client.containers.get(CONTAINER_NAME)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="container not found")

    try:
        if container.status == "running":
            container.stop()
            # wait briefly and reload status
            time.sleep(0.6)
            container.reload()
            return {"result": "ok", "action": "stopped", "container_status": container.status}
        else:
            container.start()
            time.sleep(0.6)
            container.reload()
            return {"result": "ok", "action": "started", "container_status": container.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_container_ip(container_name, preferred_network=None):
    """Return the container IP on a docker network, or None."""
    try:
        c = client.containers.get(container_name)
        nets = c.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
        # if a preferred network provided, try that first
        if preferred_network and preferred_network in nets:
            ip = nets[preferred_network].get("IPAddress")
            if ip:
                return ip
        # otherwise return first non-empty IP
        for netname, netinfo in nets.items():
            ip = netinfo.get("IPAddress")
            if ip:
                return ip
    except Exception:
        return None
    return None

def is_tcp_open(host: str, port: int, timeout=1):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except Exception as e:
        return False, str(e)

def is_mc_online(timeout=1):
    """
    Try to detect whether the Minecraft server accepts connections.
    Returns a tuple (online_bool, target_host_used, last_error_or_none).
    """
    # First, try the container name as DNS. Docker provides container name resolution
    targets_tried = []
    # try DNS name first
    dns_host = CONTAINER_NAME  # 'minecraft'
    ok, err = is_tcp_open(dns_host, MC_PORT, timeout=timeout)
    targets_tried.append((dns_host, ok, err))
    if ok:
        return True, dns_host, None

    # if DNS failed, try to get the container IP on the docker network
    container_ip = get_container_ip(CONTAINER_NAME)
    if container_ip and container_ip != dns_host:
        ok, err = is_tcp_open(container_ip, MC_PORT, timeout=timeout)
        targets_tried.append((container_ip, ok, err))
        if ok:
            return True, container_ip, None

    # as a last resort try localhost in case the server is published to the host network
    ok, err = is_tcp_open("127.0.0.1", MC_PORT, timeout=timeout)
    targets_tried.append(("127.0.0.1", ok, err))
    if ok:
        return True, "127.0.0.1", None

    # none worked, return False and the last error plus a tiny summary of what we tried
    last_err = "; ".join(f"{t[0]}: {'ok' if t[1] else t[2]}" for t in targets_tried)
    return False, targets_tried[0][0], last_err

@app.get("/status")
def status():
    result = {}
    # Docker container info
    try:
        c = client.containers.get(CONTAINER_NAME)
        state = c.attrs.get("State", {})
        result["container_status"] = state.get("Status", "unknown")
        result["health"] = state.get("Health", {}).get("Status")
    except docker.errors.NotFound:
        result["container_status"] = "not_found"
        result["health"] = None
    except Exception as e:
        result["container_error"] = str(e)

    # Minecraft server check (tries container name, container IP, then localhost)
    mc_online, mc_target, mc_err = is_mc_online(timeout=1)
    result["minecraft_online"] = mc_online
    result["mc_target"] = mc_target
    if mc_err:
        result["mc_last_error"] = mc_err

    return JSONResponse(result)
