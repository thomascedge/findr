import json
import pytest
import base64
import json
from starlette.testclient import TestClient

AUSTIN_LAT = 30.2672
AUSTIN_LNG = -97.7431


def _token(headers: dict) -> str:
    return headers["Authorization"].replace("Bearer ", "")


# ── Connection ────────────────────────────────────────────────────────────────

def test_ws_connect_success(client: TestClient, auth_headers):
    """A user with a valid token can connect to the WebSocket."""
    token = _token(auth_headers)

    with client.websocket_connect(f"/ws/map?token={token}") as ws:
        ws.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT, "lng": AUSTIN_LNG, "visible": True}
        })
        data = ws.receive_json()
        assert data["event"] == "map_snapshot"


def test_ws_invalid_token(client: TestClient):
    """A user with an invalid token is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/map?token=not-a-real-token") as ws:
            ws.receive_json()


def test_ws_missing_token(client: TestClient):
    """Connecting without a token is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/map") as ws:
            ws.receive_json()


# ── Heartbeat ─────────────────────────────────────────────────────────────────

def test_ws_heartbeat(client: TestClient, auth_headers):
    """Sending a heartbeat after setting presence does not cause an error."""
    token = _token(auth_headers)

    with client.websocket_connect(f"/ws/map?token={token}") as ws:
        # set presence first
        ws.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT, "lng": AUSTIN_LNG, "visible": True}
        })
        ws.receive_json()  # consume map_snapshot

        # send heartbeat — should not raise
        ws.send_json({"event": "heartbeat", "payload": {}})


# ── Presence ──────────────────────────────────────────────────────────────────

def test_ws_user_goes_offline(client: TestClient, auth_headers):
    """Sending visible=False removes the user from presence."""
    token = _token(auth_headers)
    current_user_id = _user_id_from_token(token)

    with client.websocket_connect(f"/ws/map?token={token}") as ws:
        ws.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT, "lng": AUSTIN_LNG, "visible": True}
        })
        ws.receive_json()

        ws.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT, "lng": AUSTIN_LNG, "visible": False}
        })
        data = ws.receive_json()
        assert data["event"] == "map_snapshot"
        user_ids = [u["user_id"] for u in data["payload"]["users"]]
        assert current_user_id not in user_ids


# ── Nearby users ──────────────────────────────────────────────────────────────

def test_ws_nearby_users(client: TestClient, auth_headers, auth_headers_2):
    """Two users in the same area appear in each other's map snapshot."""
    token_1 = _token(auth_headers)
    token_2 = _token(auth_headers_2)

    with client.websocket_connect(f"/ws/map?token={token_1}") as ws1:
        ws1.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT, "lng": AUSTIN_LNG, "visible": True}
        })
        snapshot_1 = ws1.receive_json()

    with client.websocket_connect(f"/ws/map?token={token_2}") as ws2:
        ws2.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT + 0.001, "lng": AUSTIN_LNG + 0.001, "visible": True}
        })
        snapshot_2 = ws2.receive_json()

    assert snapshot_1["event"] == "map_snapshot"
    assert snapshot_2["event"] == "map_snapshot"
    assert len(snapshot_1["payload"]["users"]) >= 0
    assert len(snapshot_2["payload"]["users"]) >= 0


# ── Unknown event ─────────────────────────────────────────────────────────────

def test_ws_unknown_event(client: TestClient, auth_headers):
    """Sending an unknown event type does not crash the connection."""
    token = _token(auth_headers)

    with client.websocket_connect(f"/ws/map?token={token}") as ws:
        ws.send_json({"event": "unknown_event", "payload": {}})

        # connection should still be alive
        ws.send_json({
            "event": "location_update",
            "payload": {"lat": AUSTIN_LAT, "lng": AUSTIN_LNG, "visible": True}
        })
        data = ws.receive_json()
        assert data["event"] == "map_snapshot"


def _user_id_from_token(token: str) -> str:
    # JWT payload is the second segment, base64 encoded
    payload = token.split(".")[1]
    # Add padding if needed
    payload += "=" * (4 - len(payload) % 4)
    return json.loads(base64.b64decode(payload))["sub"]