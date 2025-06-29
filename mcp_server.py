#!/usr/bin/env python3

import requests
import json
import time
import datetime
from urllib.parse import quote
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

@mcp.tool()
def search_content(query):
    """
    Searches for content on OQEE and returns a simplified format.
    """
    try:
        encoded_query = quote(query)
        response = requests.get(f"https://api.oqee.net/api/v3/search/{encoded_query}")
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("result", []):
            result_item = {"type": item.get("type")}
            
            if "collection" in item:
                collection_data = item.get("collection", {})
                result_item["title"] = collection_data.get("title")
                result_item["type"] = collection_data.get("type")
                result_item["id"] = collection_data.get("id")
                result_item["url"] = f"https://oqee.tv/search-collection/{result_item['id']}/all"
            
            elif "replay_collection" in item:
                replay_collection_data = item.get("replay_collection", {})
                result_item["title"] = replay_collection_data.get("title")
                result_item["id"] = replay_collection_data.get("id")
                result_item["url"] = f"https://oqee.tv/search-replay_collection/{result_item['id']}/all"

            elif "content" in item:
                content_data = item.get("content", {})
                result_item["title"] = content_data.get("title")
                result_item["description"] = content_data.get("description")
                result_item["original_title"] = content_data.get("original_title")
                result_item["id"] = content_data.get("id")
                if content_data.get("display_as") == "vod":
                    result_item["url"] = f"https://oqee.tv/vod/contents/{result_item['id']}"

            results.append(result_item)
            
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error searching for content: {e}")
        return None


@mcp.tool()
def get_epg_live():
    """
    Lists the current and next program for all channels.
    """
    try:
        # Get channel list
        service_plan_response = requests.get("https://api.oqee.net/api/v5/service_plan")
        service_plan_response.raise_for_status()
        service_plan = service_plan_response.json()
        channels = service_plan.get("result", {}).get("channels", {})
        channel_list = service_plan.get("result", {}).get("channel_list", [])

        lcn_mapping = {}
        for channel_info in channel_list:
            lcn_mapping[str(channel_info.get("channel_id"))] = channel_info.get("number")
        
        # Get EPG data
        # Get EPG data for the beginning of the current day (UTC)
        today = datetime.datetime.now(datetime.timezone.utc).date()
        start_of_day = datetime.datetime(today.year, today.month, today.day, tzinfo=datetime.timezone.utc)
        current_timestamp = int(start_of_day.timestamp())
        epg_response = requests.get(f"https://api.oqee.net/api/v1/epg/all/{current_timestamp}")
        epg_response.raise_for_status()
        epg_data = epg_response.json()
        epg_entries = epg_data.get("result", {}).get("entries", {})
        
        results = []
        for channel_id, channel_data in channels.items():
            channel_name = channel_data.get("name")
            lcn = lcn_mapping.get(channel_id)
            if channel_id in epg_entries:
                programs = epg_entries[channel_id]
                current_program = programs[0].get("live", {}).get("title") if len(programs) >= 1 else None
                next_program = programs[1].get("live", {}).get("title") if len(programs) >= 2 else None
                
                results.append({
                    "lcn": lcn,
                    "channel": channel_name,
                    "current_program": current_program,
                    "next_program": next_program
                })
        
        # Sort results by LCN
        results.sort(key=lambda x: (x.get("lcn") is None, x.get("lcn")))
        
        return results

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

if __name__ == "__main__":
    results = get_epg_live()
    if results:
        print(json.dumps(results, indent=2))
