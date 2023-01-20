import asyncio
import getpass
import json
import os

import requests  # type: ignore
import websockets

SMARTRENT_BASE_URI = "https://control.smartrent.com/api/v2/"
SMARTRENT_SESSIONS_URI = SMARTRENT_BASE_URI + "sessions"
SMARTRENT_HUBS_URI = SMARTRENT_BASE_URI + "hubs"
SMARTRENT_HUBS_ID_URI = SMARTRENT_BASE_URI + "hubs/{}/devices"

JOINER_PAYLOAD = '["null", "null", "devices:{device_id}", "phx_join", {{}}]'
SMARTRENT_WEBSOCKET_URI = (
    "wss://control.smartrent.com/socket/websocket?token={}&vsn=2.0.0"
)

email = os.getenv("sr_email", input("Email: "))
password = os.getenv("sr_password", getpass.getpass())

res = requests.post(
    SMARTRENT_SESSIONS_URI, json={"email": email, "password": password}
).json()

if res.get("errors"):
    print(res)
    exit()

token = None
if not res.get("errors"):
    tfa_api_token = res.get("tfa_api_token")
    if tfa_api_token:
        tfa_code = input("Enter in a TFA code: ")
        res = requests.post(
            SMARTRENT_SESSIONS_URI,
            json={"tfa_api_token": tfa_api_token, "token": tfa_code},
        ).json()

    token = res["access_token"]

headers = {"authorization": f"Bearer {token}"}

hubs = requests.get(SMARTRENT_HUBS_URI, headers=headers).json()

# print hub information
print(json.dumps(hubs, indent=4))

device_ids_and_titles = []
for hub in hubs:
    devices = requests.get(
        SMARTRENT_HUBS_ID_URI.format(hub["id"]), headers=headers
    ).json()

    output = json.dumps(devices, indent=4)
    print(output)

    for device in devices:
        id = device["id"]
        name = device["name"]

        device_ids_and_titles.append((id, name))

# print table of found devices
print(f'\n{"Device ID:":<15} Device Name:\n{"="*30}')
for device in device_ids_and_titles:
    print(f"{device[0]:<15} {device[1]}")

device_id = input("Put in the Device ID you wish to track: ")


async def asyncoman():
    uri = SMARTRENT_WEBSOCKET_URI.format(token)

    async with websockets.connect(uri) as websocket:
        joiner = JOINER_PAYLOAD.format(device_id=device_id)
        print(f"Joining topic for {device_id}...")
        await websocket.send(joiner)

        while True:
            resp = await websocket.recv()

            formatted_resp = json.loads(f"{resp}")[4]

            # print(formatted_resp)
            if formatted_resp.get("response", {}).get("reason") == "unauthorized":
                print(
                    "You seem to have entered in the wrong Device ID. Please try again!"
                )
                exit(1)

            event_type = formatted_resp.get("type")
            event_name = formatted_resp.get("name")
            event_state = formatted_resp.get("last_read_state")
            if event_type:
                print(f"{event_type:<20}{event_name:<20}{event_state}")
            else:
                print(formatted_resp)


try:
    asyncio.run(asyncoman())
except KeyboardInterrupt:
    pass
