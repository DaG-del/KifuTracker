import json
import os
import re
import sys
import time
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://www.go4go.net"
INDEX_URL = f"{BASE_URL}/go/games/tournament"
STATE_FILE = "state.json"


def load_state():
    """Load the last seen game IDs from the JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Warning: state.json was corrupted. Initializing fresh.")
    return {}


def save_state(state):
    """Save the updated state back to the JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)


def get_html(url):
    """Fetch HTML with headers to prevent basic bot-blocking."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
        print(f"Failed to fetch {url}: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None


def parse_tournament_index(html):
    """Extract tournament URLs and their clean names from the main page."""
    soup = BeautifulSoup(html, "html.parser")
    tournaments = []

    # Find all anchor tags pointing to a tournament subpage
    links = soup.find_all("a", href=re.compile(r"/go/games/tournament/\d+"))

    for link in links:
        href = link.get("href")
        name = link.get_text(strip=True)

        # Normalize relative links to absolute links
        full_url = href if href.startswith("http") else BASE_URL + href
        if name and full_url not in [t["url"] for t in tournaments]:
            tournaments.append({"name": name, "url": full_url})

    return tournaments


def parse_latest_game(tournament_html):
    """Extract the very first game detail block and its unique ID from a tournament page."""
    soup = BeautifulSoup(tournament_html, "html.parser")

    # Look for the Replay or Download links containing the game IDs
    game_link_element = soup.find(
        "a", href=re.compile(r"/go/games/(sgfview|record_request)/")
    )
    if not game_link_element:
        return None

    href = game_link_element.get("href")
    # Extract the numeric ID using regex
    match = re.search(r"(\d+)$", href)
    if not match:
        return None

    game_id = int(match.group(1))

    # Construct complete paths for viewing and downloading
    view_url = f"{BASE_URL}/go/games/sgfview/{game_id}"
    download_url = f"{BASE_URL}/go/games/record_request/{game_id}"

    return {
        "id": game_id,
        "view_url": view_url,
        "download_url": download_url,
    }


def main():
    print("🔄 Loading tracking state...")
    state = load_state()
    mismatches = []

    print(f"🌐 Fetching tournament list from {INDEX_URL}...")
    index_html = get_html(INDEX_URL)
    if not index_html:
        print("❌ Could not load main tournament index. Exiting.")
        sys.exit(1)

    tournaments = parse_tournament_index(index_html)
    print(f"📋 Found {len(tournaments)} tournaments to check.\n")

    print("-" * 60)
    print(f"{'Tournament Name':<35} | {'Latest Game ID':<15}")
    print("-" * 60)

    for tourney in tournaments:
        name = tourney["name"]
        url = tourney["url"]

        # Throttle slightly to respect Go4Go's servers and avoid IP bans
        time.sleep(0.5)

        tourney_html = get_html(url)
        if not tourney_html:
            continue

        latest_game = parse_latest_game(tourney_html)

        if latest_game:
            game_id = latest_game["id"]
            print(f"{name:<35} | {game_id:<15}")

            # Check history
            last_known_id = state.get(name)

            # If there's no history, or the game ID is strictly greater, it's a new match
            if last_known_id is None or game_id > last_known_id:
                mismatches.append(
                    f"🏆 Tournament: {name}\n"
                    f"   🆕 New Game ID: {game_id} (Previous: {last_known_id})\n"
                    f"   👁️ View: {latest_game['view_url']}\n"
                    f"   📥 Download SGF: {latest_game['download_url']}\n"
                )
                state[name] = game_id
        else:
            print(f"{name:<35} | No games found")

    print("-" * 60)

    # Output the tracking summary reports
    print("-" * 60)

    # Output the tracking summary reports
    if mismatches:
        print(f"\n🚨 FOUND {len(mismatches)} NEW GAME UPDATES!\n")
        alert_string = "\n".join(mismatches)
        print(alert_string)

        # Write out to a temporary file for backup
        with open("alert_msg.txt", "w") as f:
            f.write(alert_string)

        # =====================================================================
        # 🚀 ADD THE NTFY PUSH CODE RIGHT HERE
        # =====================================================================
        try:
            # Replace 'gg1427_go_kifu_alerts' with whatever custom name you want
            ntfy_url = "https://ntfy.sh/kifu_tracker_for_go_4_go_notifications"
            
            requests.post(
                ntfy_url, 
                data=alert_string, 
                headers={
                    "Title": "New Go Games Found!",
                    "Tags": "go,trophy" # Adds a little go stone / trophy emoji to the notification
                },
                timeout=10
            )
            print("📲 Push notification successfully dispatched via ntfy.sh!")
        except Exception as e:
            print(f"⚠️ Failed to send ntfy notification: {e}")
        # =====================================================================

        save_state(state)
    else:
        print("\n✅ Everything matches up to date. No new uploads.")


if __name__ == "__main__":
    main()
