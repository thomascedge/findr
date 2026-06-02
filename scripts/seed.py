"""
Findr Seed Script
─────────────────
Populates the running stack with realistic Austin-scale test data.
Simulates ~50 users spread across Austin with varied profiles, locations,
chats, and messages.

Usage:
    docker compose exec app python scripts/seed.py

    # Or with options:
    docker compose exec app python scripts/seed.py --users 100 --clear
"""

import argparse
import random
import sys
import httpx
from datetime import datetime, timezone, timedelta

BASE_URL = "http://localhost:8000/api/v1"

# ── Austin area coordinates (lat, lng bounds) ─────────────────────────────────
AUSTIN_BOUNDS = {
    "lat_min": 30.15,
    "lat_max": 30.45,
    "lng_min": -97.85,
    "lng_max": -97.60,
}

# ── Realistic seed data ───────────────────────────────────────────────────────
USERNAMES = [
    "austinlocal",
    "keepitweird",
    "bartonsprings",
    "sixthstreet",
    "zilker_fan",
    "sxsw_regular",
    "longhorn_fan",
    "rainey_st",
    "eastaustin",
    "southcongress",
    "ladybirdlake",
    "domainlife",
    "roundrock_guy",
    "cedar_park_tx",
    "pflugerville",
    "travis_heights",
    "bouldin_creek",
    "cherrywood_tx",
    "mueller_austin",
    "crestview_atx",
    "rosedale_tx",
    "tarrytown_atx",
    "hyde_park_atx",
    "clarksville_tx",
    "bryker_woods",
    "pecan_springs",
    "govuniv_atx",
    "montopolis_tx",
    "riverside_atx",
    "onion_creek",
    "slaughter_ln",
    "manchaca_tx",
    "sunset_valley",
    "rollingwood_tx",
    "westlake_hills",
    "bee_cave_tx",
    "lakeway_atx",
    "volente_tx",
    "jonestown_tx",
    "cedar_valley",
    "manor_tx",
    "elgin_adjacent",
    "bastrop_nearby",
    "kyle_tx_guy",
    "buda_tx",
    "dripping_springs",
    "wimberley_way",
    "san_marcos_adj",
    "lockhart_bbq",
    "luling_fan",
]

BIOS = [
    "Coffee first, everything else second ☕",
    "ATX native. Love Barton Springs and live music.",
    "Dog dad, amateur chef, always down for tacos 🌮",
    "Cyclist, hiker, weekend camper.",
    "Keeping Austin weird since 2015.",
    "Software engineer by day, musician by night 🎸",
    "Yoga instructor and brunch enthusiast.",
    "New to Austin, looking to explore the city!",
    "Foodie. If you know a great hidden gem, tell me.",
    "Outdoor adventures and good conversation.",
    "Plant parent 🌿 and bookworm.",
    "Gym rat and taco truck connoisseur.",
    "Festival season is my favorite season.",
    "Remote worker, coffee shop hopper.",
    "Amateur photographer, always exploring.",
    None,  # some users have no bio
    None,
    None,
]

INTERESTS = [
    "hiking",
    "cycling",
    "coffee",
    "tacos",
    "live_music",
    "yoga",
    "photography",
    "cooking",
    "reading",
    "gaming",
    "fitness",
    "brunch",
    "travel",
    "dogs",
    "plants",
    "art",
    "tech",
    "film",
    "running",
    "climbing",
]


# ── Helpers ───────────────────────────────────────────────────────────────────


def random_austin_coords():
    """Returns a random lat/lng within Austin bounds."""
    lat = random.uniform(AUSTIN_BOUNDS["lat_min"], AUSTIN_BOUNDS["lat_max"])
    lng = random.uniform(AUSTIN_BOUNDS["lng_min"], AUSTIN_BOUNDS["lng_max"])
    return round(lat, 6), round(lng, 6)


def random_dob():
    """Returns a random date of birth for a user aged 21-40."""
    age = random.randint(21, 40)
    dob = datetime.now(timezone.utc) - timedelta(
        days=age * 365 + random.randint(0, 364)
    )
    return dob.isoformat()


def register_user(client: httpx.Client, username: str, index: int) -> dict | None:
    """Register a user and return their token and id."""
    payload = {
        "username": username,
        "email": f"{username}@seed.findr",
        "password": "seedpassword123",
    }

    # Add date_of_birth if your schema requires it
    # payload["date_of_birth"] = random_dob()

    response = client.post(f"{BASE_URL}/auth/register", json=payload)
    if response.status_code == 409:
        print(f"  ⚠️  {username} already exists — logging in")
    elif response.status_code != 201:
        print(f"  ❌ Failed to register {username}: {response.text}")
        return None

    # Login
    login = client.post(
        f"{BASE_URL}/auth/token",
        data={
            "username": username,
            "password": "seedpassword123",
        },
    )
    if login.status_code != 200:
        print(f"  ❌ Failed to login {username}: {login.text}")
        return None

    token = login.json()["access_token"]
    user_id = (
        client.get(f"{BASE_URL}/users/me", headers={"Authorization": f"Bearer {token}"})
        .json()
        .get("id")
    )

    return {"username": username, "token": token, "id": user_id}


def set_location(client: httpx.Client, token: str, username: str):
    """Set a random Austin location for the user."""
    lat, lng = random_austin_coords()
    response = client.put(
        f"{BASE_URL}/location/me",
        json={"lat": lat, "lng": lng, "visible": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code != 200:
        print(f"  ⚠️  Could not set location for {username}")


def send_message(client: httpx.Client, sender_token: str, recipient_id: str, body: str):
    """Send a DM from one user to another."""
    client.post(
        f"{BASE_URL}/messages/send?recipient_id={recipient_id}",
        json={"body": body},
        headers={"Authorization": f"Bearer {sender_token}"},
    )


# ── Message templates ─────────────────────────────────────────────────────────

MESSAGES = [
    "Hey! Saw you on the map nearby 👋",
    "Love your profile! Down for coffee sometime?",
    "Are you going to the show at Stubb's this weekend?",
    "Great taste in music btw",
    "What's your go-to taco spot?",
    "Just moved to the east side, any recommendations?",
    "Barton Springs or Lady Bird Lake for a morning swim?",
    "Hey, what part of town are you in?",
    "You seem cool, want to grab drinks on Rainey?",
    "Saw you like hiking — have you done Barton Creek Greenbelt?",
]


# ── Main ──────────────────────────────────────────────────────────────────────


def main(num_users: int, clear: bool):
    print(f"\n🌱 Seeding Findr with {num_users} Austin users...\n")

    if clear:
        print("⚠️  --clear flag noted. To wipe data, run: make reset\n")

    users = []

    with httpx.Client(timeout=30) as client:

        # Check stack is up
        try:
            health = client.get("http://localhost:8000/health")
            if health.status_code != 200:
                print("❌ Stack not running. Run: make up")
                sys.exit(1)
        except Exception:
            print("❌ Cannot reach http://localhost:8000. Run: make up")
            sys.exit(1)

        # ── Register users ────────────────────────────────────────────────────
        print("👤 Registering users...")
        usernames = USERNAMES[:num_users]

        for i, username in enumerate(usernames):
            user = register_user(client, username, i)
            if user:
                users.append(user)
                print(f"  ✅ {username}")

        print(f"\n✅ {len(users)} users registered\n")

        # ── Set locations ─────────────────────────────────────────────────────
        print("📍 Setting Austin locations...")
        for user in users:
            set_location(client, user["token"], user["username"])
        print(f"  ✅ {len(users)} locations set\n")

        # ── Send messages ─────────────────────────────────────────────────────
        print("💬 Seeding conversations...")
        message_count = 0
        for user in users:
            # Each user messages 2-4 random others
            targets = random.sample(
                [u for u in users if u["id"] != user["id"]], min(3, len(users) - 1)
            )
            for target in targets:
                body = random.choice(MESSAGES)
                send_message(client, user["token"], target["id"], body)
                message_count += 1

        print(f"  ✅ {message_count} messages sent\n")

        # ── Summary ───────────────────────────────────────────────────────────
        print("─" * 40)
        print("🎉 Seed complete!")
        print(f"   Users:    {len(users)}")
        print(f"   Messages: {message_count}")
        print("\n   Swagger: http://localhost:8000/docs")
        print("   Login with any seeded user:")
        print(f"     username: {users[0]['username'] if users else 'N/A'}")
        print("     password: seedpassword123\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Findr with test data")
    parser.add_argument(
        "--users", type=int, default=25, help="Number of users to create (max 50)"
    )
    parser.add_argument(
        "--clear", action="store_true", help="Print reminder to wipe DB first"
    )
    args = parser.parse_args()

    num_users = min(args.users, len(USERNAMES))
    main(num_users, args.clear)
