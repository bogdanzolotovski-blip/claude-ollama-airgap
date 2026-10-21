#!/usr/bin/env python3
"""Explicit local Ollama preflight. No pulls, no cloud, no tokens in output."""
import argparse
import ipaddress
import json
import socket
import urllib.parse
import urllib.request


def check_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Use server root http[s]://host:port without /v1, credentials, query or path")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("Cannot resolve Ollama server")
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast:
            raise ValueError("Only internal/loopback Ollama addresses are accepted")
    return url.rstrip("/")


def preflight(url, model, messages=False):
    if model.endswith(":cloud"):
        raise ValueError("Cloud models are not allowed")
    url = check_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def request(path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url + path, data=body, headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=120) as response:
            return json.load(response)
    version = request("/api/version").get("version")
    models = request("/api/tags").get("models", [])
    found = next((entry for entry in models if entry.get("name") == model), None)
    if found is None:
        raise ValueError("Exact model name not found in /api/tags; use an already installed local model")
    if found.get("remote_host") or found.get("remote_model"):
        raise ValueError("Selected model is backed by a remote/cloud provider")
    info = request("/api/show", {"model": model})
    if info.get("remote_host") or info.get("remote_model"):
        raise ValueError("Remote model rejected")
    capabilities = info.get("capabilities", [])
    if "tools" not in capabilities:
        raise ValueError("Model does not advertise tool calling; choose a tool-capable local model")
    print("PASS: internal Ollama reachable; model installed locally; tools capability present; version:", version)
    if messages:
        reply = request("/v1/messages", {"model": model, "max_tokens": 64, "stream": False,
                                        "messages": [{"role": "user", "content": "Reply with OK only."}]})
        if reply.get("type") != "message" or not reply.get("content"):
            raise ValueError("Unexpected Anthropic-compatible Messages response")
        print("PASS: /v1/messages returned an Anthropic-compatible message (model output not logged)")
    else:
        print("Model inference NOT tested; pass --test-messages to send a small real prompt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--test-messages", action="store_true")
    args = parser.parse_args()
    try:
        preflight(args.url, args.model, args.test_messages)
    except Exception as error:
        raise SystemExit("Ollama preflight failed: " + str(error))
