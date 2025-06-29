#!/usr/bin/env python3

import requests
import json
import time
import datetime
from typing import Union
from urllib.parse import quote
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Oqee")

_SERVICE_PLAN_CACHE = None

def _load_service_plan_cache():
    global _SERVICE_PLAN_CACHE
    if _SERVICE_PLAN_CACHE is None:
        try:
            response = requests.get("https://api.oqee.net/api/v5/service_plan")
            response.raise_for_status()
            _SERVICE_PLAN_CACHE = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching service plan: {e}")
            _SERVICE_PLAN_CACHE = {}
        except json.JSONDecodeError:
            print("Error parsing service plan response.")
            _SERVICE_PLAN_CACHE = {}

_load_service_plan_cache()

def _load_service_plan_cache():
    global _SERVICE_PLAN_CACHE
    if _SERVICE_PLAN_CACHE is None:
        try:
            response = requests.get("https://api.oqee.net/api/v5/service_plan")
            response.raise_for_status()
            _SERVICE_PLAN_CACHE = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching service plan: {e}")
            _SERVICE_PLAN_CACHE = {}
        except json.JSONDecodeError:
            print("Error parsing service plan response.")
            _SERVICE_PLAN_CACHE = {}

def _get_channel_details(channel_id):
    _load_service_plan_cache()
    service_plan = _SERVICE_PLAN_CACHE
    if not service_plan:
        return None, None

    channels = service_plan.get("result", {}).get("channels", {})
    channel_list = service_plan.get("result", {}).get("channel_list", [])

    channel_name = channels.get(str(channel_id), {}).get("name")
    lcn = None
    for channel_info in channel_list:
        if str(channel_info.get("channel_id")) == str(channel_id):
            lcn = channel_info.get("number")
            break
    return channel_name, lcn

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
    _load_service_plan_cache()
    service_plan = _SERVICE_PLAN_CACHE
    if not service_plan:
        print("Service plan not loaded.")
        return
        
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
                elif content_data.get("display_as") == "diffusion":
                    diffusions = content_data.get("diffusions", [])
                    if diffusions:
                        first_diffusion = diffusions[0]
                        channel_id = first_diffusion.get("channel_id")
                        start_time = first_diffusion.get("start")
                        
                        channel_name, channel_number = _get_channel_details(channel_id)
                        
                        if channel_name:
                            result_item["channel_name"] = channel_name
                        if channel_number:
                            result_item["channel_number"] = channel_number
                        if start_time:
                            dt_object = datetime.datetime.fromtimestamp(start_time)
                            result_item["broadcast_time"] = dt_object.strftime("%m/%d %H:%M")
                        
                        end_time = first_diffusion.get("end")
                        if end_time:
                            dt_end_object = datetime.datetime.fromtimestamp(end_time)
                            result_item["broadcast_end_time"] = dt_end_object.strftime("%m/%d %H:%M")
                            if start_time:
                                duration_seconds = end_time - start_time
                                duration_minutes = duration_seconds // 60
                                result_item["duration"] = f"{duration_minutes} minutes"

            results.append(result_item)
            
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error searching for content: {e}")
        return None


def _get_epg_by_datetime(timestamp: datetime.datetime):
    """
    Lists the current and next program for all channels based on a given timestamp.
    """
    _load_service_plan_cache()
    service_plan = _SERVICE_PLAN_CACHE
    if not service_plan:
        print("Service plan not loaded.")
        return
    channels = service_plan.get("result", {}).get("channels", {})
    channel_list = service_plan.get("result", {}).get("channel_list", [])

    lcn_mapping = {}
    for channel_info in channel_list:
        lcn_mapping[str(channel_info.get("channel_id"))] = channel_info.get("number")
    
    current_time = timestamp.replace(minute=0, second=0, microsecond=0)
    current_timestamp = int(current_time.timestamp())
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
            programs = [x for x in programs if x['live']['end'] >= timestamp.timestamp()]
            current_program_data = programs[0].get("live", {}) if len(programs) >= 1 else None
            next_program_data = programs[1].get("live", {}) if len(programs) >= 2 else None

            current_program_title = current_program_data.get("title") if current_program_data else None
            next_program_title = next_program_data.get("title") if next_program_data else None

            current_program_start_time = datetime.datetime.fromtimestamp(current_program_data.get("start")).strftime("%H:%M") if current_program_data and current_program_data.get("start") else None
            current_program_end_time = datetime.datetime.fromtimestamp(current_program_data.get("end")).strftime("%H:%M") if current_program_data and current_program_data.get("end") else None

            next_program_start_time = datetime.datetime.fromtimestamp(next_program_data.get("start")).strftime("%H:%M") if next_program_data and next_program_data.get("start") else None
            next_program_end_time = datetime.datetime.fromtimestamp(next_program_data.get("end")).strftime("%H:%M") if next_program_data and next_program_data.get("end") else None

            results.append({
                "lcn": lcn,
                "channel": channel_name,
                "current_program": current_program_title,
                "current_program_start_time": current_program_start_time,
                "current_program_end_time": current_program_end_time,
                "next_program": next_program_title,
                "next_program_start_time": next_program_start_time,
                "next_program_end_time": next_program_end_time
            })

    # Sort results by LCN
    results.sort(key=lambda x: (x.get("lcn") is None, x.get("lcn")))

    return results

@mcp.tool()
def get_epg(time_input: Union[str, int] = None):
    """
    Lists the current and next program for all channels based on a given timestamp, HH:MM, or MM/DD HH:MM.
    """
    if time_input is None:
        timestamp = datetime.datetime.now()
    elif isinstance(time_input, int):
        timestamp = datetime.datetime.fromtimestamp(time_input)
    elif isinstance(time_input, str):
        try:
            # Try parsing as HH:MM
            hour, minute = map(int, time_input.split(':'))
            timestamp = datetime.datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            try:
                # Try parsing as MM/DD HH:MM
                month_day, time_part = time_input.split(' ')
                month, day = map(int, month_day.split('/'))
                hour, minute = map(int, time_part.split(':'))
                timestamp = datetime.datetime.now().replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                raise ValueError("Invalid time format. Use HH:MM, MM/DD HH:MM, or a Unix timestamp (int).")
    else:
        raise ValueError("Invalid time input. Must be a string (HH:MM or MM/DD HH:MM) or a Unix timestamp (int).")
    
    return _get_epg_by_datetime(timestamp)

@mcp.tool()
def get_epg_live():
    """
    Lists the current and next program for all channels.
    """
    return _get_epg_by_datetime(datetime.datetime.now())

@mcp.tool()
def get_epg_evening():
    """
    Lists the current and next program for all channels for the evening.
    """
    evening_time = datetime.datetime.now().replace(hour=21, minute=30, second=0, microsecond=0)
    return _get_epg_by_datetime(evening_time)

def main():
    import argparse
    argparser = argparse.ArgumentParser(description="Woob MCP server")
    argparser.add_argument('--sse', action='store_true', help='Run in SSE mode (default stdio)')
    args = argparser.parse_args()

    transport = 'stdio'
    if args.sse:
        transport = 'sse'
    mcp.run(transport=transport)

if __name__ == "__main__":
    results = search_content("bigflo")
    print(json.dumps(results, indent=2))
