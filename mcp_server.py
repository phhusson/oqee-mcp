#!/usr/bin/env python3

import requests
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Oqee")

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

@mcp.tool()
def play_channel(channel_name):
    """
    Finds the closest channel to the given name from the OQEE service plan
    and prints its information.
    """
    try:
        response = requests.get("https://api.oqee.net/api/v5/service_plan")
        response.raise_for_status()  # Raise an exception for bad status codes
        service_plan = response.json()
        
        channels = service_plan.get("result", {}).get("channels", {})
        if not channels:
            print("No channels found in the service plan.")
            return

        best_match = None
        min_distance = float('inf')

        for channel_id, channel_data in channels.items():
            name = channel_data.get("name", "")
            distance = levenshtein_distance(channel_name.lower(), name.lower())
            if distance < min_distance:
                min_distance = distance
                best_match = channel_data

        if best_match:
            channel_id = best_match.get('id')
            url = f"https://oqee.tv/home/channels/{channel_id}/play"
            return url
        else:
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching service plan: {e}")
    except json.JSONDecodeError:
        print("Error parsing service plan response.")

if __name__ == "__main__":
    url = play_channel("TF1")
    if url:
        print(f"URL for TF1: {url}")
    else:
        print("Could not find URL for TF1.")
