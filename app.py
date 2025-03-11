import requests
from flask import Flask, request, jsonify, session
from flask_session import Session
from llmproxy import generate, pdf_upload
import os
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


app = Flask(__name__)
session_id = "10havelaydatePlanner-"

# Rocket.Chat API endpoint
API_BASE_URL = "https://chat.genaiconnect.net/api/v1"
ROCKETCHAT_URL = "https://chat.genaiconnect.net/api/v1/chat.postMessage"  # Keep the same URL

# Headers with authentication tokens stored securely in environment variables
HEADERS = {
    "Content-Type": "application/json",
    "X-Auth-Token": os.environ.get("RC_token"),  #Replace with your bot token for local testing or keep it and store secrets in Koyeb
    "X-User-Id": os.environ.get("RC_userId") #Replace with your bot user id for local testing or keep it and store secrets in Koyeb
}

upload_headers = {
    "X-Auth-Token": os.environ.get("RC_token"),  #Replace with your bot token for local testing or keep it and store secrets in Koyeb
    "X-User-Id": os.environ.get("RC_userId") #Replace with your bot user id for local testing or keep it and store secrets in Koyeb
}

def send_message_with_buttons(parts, username, text):
    """Send a message with Yes/No buttons for plan confirmation."""
    actions = []
    # Dynamically create a button for each available response.
    # If you need a minimum of 4 buttons, you can add a fallback button.
    for idx in range(parts):
        actions.append({
            "type": "button",
            "text": f"{idx}",
            "msg": f"The chosen place is: {idx}",
            "msg_in_chat_window": True,
            "style": "primary"
        })

    # # Optionally, add a fallback if there are fewer than 4 options.
    # if len(actions) < 4:
    #     actions.append({
    #         "type": "button",
    #         "text": "More options",
    #         "msg": "No more options available.",
    #         "msg_in_chat_window": True,
    #         "style": "default"
    #     })

    payload = {
        "channel": f"@{username}",
        "text": text,
        "attachments": [
            {
                "text": "Which option do you like?",
                "actions": actions
            }
        ]
    }

    try:
        response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"Message with buttons sent to {username}.")
        return response.json()
    except Exception as e:
        print(f"An unexpected error occurred while sending message to {username}: {e}")
        return {"error": f"Unexpected error: {e}"}

def ask_for_friend_username(username):
    """Ask the user for their friend's username."""
    payload = {
        "channel": f"@{username}",
        "text": "Please enter your friend's username:"
    }

    try:
        response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"Asked {username} for their friend's username.")

        return response.json()
    except Exception as e:
        print(f"An error occurred while asking for friend's username: {e}")
        return {"error": f"Error: {e}"}
    
def is_valid_username(username):
    """
    Check if a username exists by calling Rocket.Chat's /users.info API.
    """
    url = f"{API_BASE_URL}/users.info?username={username}"
    try:
        response = requests.get(url, headers=HEADERS)
        data = response.json()
        if response.status_code == 200 and data.get("user"):
            return True
        return False
    except Exception as e:
        print("Error validating username:", e)
        return False

def send_plan_to_friend(friend_username, username, plan_text):
    # """
    # Send the plan message to the friend.
    # """
    payload = {
        "channel": f"@{friend_username}",
        "text": plan_text,
        "attachments": [
            {
                "text": "Do you like this plan?",
                "actions": [
                    {
                        "type": "button",
                        "text": "✅ Yes",
                        "msg": f"!final {username} {friend_username} yes",
                        "msg_in_chat_window": True
                    },
                    {
                        "type": "button",
                        "text": "❌ No",
                        "msg": f"!final {username} {friend_username} no",
                        "msg_in_chat_window": True
                    }
                ]
            }
        ]
    }

    try:
        # Send the message with buttons to Rocket.Chat
        response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)
        print(f"Message with buttons sent successfully to {username}.")
        return response.json()  # Return the JSON response if successful
    except Exception as e:
        # Handle any other unexpected errors
        print(f"An unexpected error occurred while sending message to {username}: {e}")
        return {"error": f"Unexpected error: {e}"}

def send_typing_indicator(room_id):
    payload = {
        "roomId": room_id,
        "typing": True
    }
    try:
        response = requests.post(f"{API_BASE_URL}/chat.sendTyping", json=payload, headers=HEADERS)
        response.raise_for_status()
        print("Typing indicator sent.")
    except Exception as e:
        print(f"Error sending typing indicator: {e}")

def send_activity_suggestions(user):
    # Pair each suggestion with an emoji for a more visual presentation
    suggestions = [
        ("Restaurant", "🍽️"),
        ("Cafe", "☕"),
        ("Museum", "🏛️"),
        ("Movie", "🎬"),
        ("Park", "🌳")
    ]
    
    # Build the actions array with improved formatting and optional styling
    actions = []
    for idx, (suggestion, emoji) in enumerate(suggestions):
        actions.append({
            "type": "button",
            "text": f"{emoji} {suggestion.capitalize()}",
            "msg": f"The activity category chosen is: {suggestion}",
            "msg_in_chat_window": True,
            "style": "primary"  # Optional: use "primary", "danger", etc. if supported
        })
    
    payload = {
        "channel": f"@{user}",
        "text": "Here are some activity suggestions for you:",
        "attachments": [
            {
                "text": "Please choose one of the following activities:",
                "actions": actions
            }
        ]
    }
    
    try:
        response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"Sent activity suggestion buttons to {user}.")
        return response.json()
    except Exception as e:
        print(f"Error sending activity suggestions: {e}")
        return {"error": f"Unexpected error: {e}"}

def confirm_command(message):
    parts = message.split()
    if len(parts) >= 3:
        confirmed_user = parts[1]
        confirmation = parts[2]

        if confirmation == "yes":
            # Ask for the friend's username
            ask_for_friend_username(confirmed_user)
            return jsonify({"status": "asked_for_friend_username"})
        elif confirmation == "no":
            payload = {
                "channel": f"@{confirmed_user}",
                "text": f"The event has been canceled. Please try again!"
            }
            try:
                response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
                response.raise_for_status()

                return response.json()
            except Exception as e:
                print(f"An error occurred stating the confirmation: {e}")
                return {"error": f"Error: {e}"}
    return jsonify({"status": "invalid_confirmation"})

def activity_chosen(message, user, sess_id):
    response = generate(
        model = '4o-mini',
        system = 'Give human readable text and be friendly',
        query = (
            f"""There is a previously generated API list of activities.
            The user selected activity number {message.split()[0]} from that list.
            Please provide a detailed, human-readable summary of this activity or place, including key details.
            **Only** include the numbered place.
            In this summary, pleae also include the previously discussed time.
            Make sure to retain this summary in our session context for future reference."""                    
        ),
        # Please provide a detailed, human-readable summary of this activity or place, including key details such as location, features, and highlights.
        #     Make sure to retain this summary in our session context for future reference.
        temperature=0.3,
        lastk=20,
        session_id=sess_id
    )
    response_text = response['response']

    payload = {
        "channel": f"@{user}",
        "text": response_text,
        "attachments": [
            {
                "text": "Do you like this plan?",
                "actions": [
                    {
                        "type": "button",
                        "text": "✅ Yes",
                        "msg": f"!confirm {user} yes",
                        "msg_in_chat_window": True
                    },
                    {
                        "type": "button",
                        "text": "❌ No",
                        "msg": f"!confirm {user} no",
                        "msg_in_chat_window": True
                    }
                ]
            }
        ]
    }
    try:
        # Send the message with buttons to Rocket.Chat
        response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)
        return response.json()  # Return the JSON response if successful
    except Exception as e:
        # Handle any other unexpected errors
        return {"error": f"Unexpected error: {e}"}

def regenerate_summary(sess_id):
    print("MESSAGE LENGTH IS 1")
    print("VALID USERNAME")
    query = (
        """
        Give the previously generated summary of the plan.
        You are presenting this summary of the plan to somebody else.
        """
    )
    plan = generate(
        model='4o-mini',
        system="List the options clearly",
        query= query,
        temperature=0.0,
        lastk=20,
        session_id=sess_id
    )
    plan_text = plan['response']
    return plan_text

def send_calendar_to_recipient(message, room_id):
        parts = message.split()
        if len(parts) >= 4:
            confirmed_user = parts[1]
            confirmed_friend = parts[2]
            confirmation = parts[3]

            friend_sess_id = session_id + confirmed_user

            if confirmation == "yes": #SEND THE ICAL TO BOTH PARTIES
                # Ask for the friend's username
                system_message = (
                    "You are an assistant that generates iCalendar (ICS) documents based on previous conversation context. " 
                    "Your output must be a valid ICS file conforming to RFC 5545, " 
                    "and include only the ICS content without any additional commentary or explanation. " 
                    "Ensure you include mandatory fields such as BEGIN:VCALENDAR, VERSION, PRODID, BEGIN:VEVENT, UID, DTSTAMP, " 
                    "DTSTART, DTEND, and SUMMARY."
                    "Note that no line length should exceed 75 characters."
                )
                query = (f"""
                        Using the previously generated event summary from our conversation context, generate a complete and valid iCalendar (ICS) document
                        that reflects the event details.
                        Name the calendar event based on the activity/place found in the summary.
                        Set the location of the calendar event to the address of the location in the summary.
                        Set the time of the calendar event to the time of the hangout, using the current date as reference.
                        Keep the description brief (less than 60 characters) to comply with ICS file format.
                        Output only the ICS content with no extra text.
                        Follow valid ICS file format.
                        For reference, today's date and time is {datetime.now(ZoneInfo('America/New_York'))}.
                        """)
                response = generate(
                    model='4o-mini',
                    system= system_message,
                    query= query,
                    temperature=0.0,
                    lastk=20,
                    session_id=friend_sess_id
                )
                ical_content = response.get('response').strip()
                if ical_content.startswith("```") and ical_content.endswith("```"):
                    ical_content = ical_content[3:-3].strip()
                print("Generated ICS content:")
                print(ical_content)

                # Define the upload URL (same for all uploads)
                print("Room ID for file upload:", room_id)
                upload_url = f"{API_BASE_URL}/rooms.upload/{room_id}"
                print("Constructed upload URL:", upload_url)

                # Write the ICS content to a file
                ics_filename = "event.ics"
                print(f"Writing ICS content to file: {ics_filename}")
                ics_content = ical_content.replace("\n", "\r\n")
                ics_content = ics_content.strip()
                try:
                    with open(ics_filename, "w") as f:
                        f.write(ics_content)
                    print("ICS file written successfully.")
                except Exception as e:
                    print(f"Error writing ICS file: {e}")

                # Read and print the ICS file contents
                try:
                    with open(ics_filename, "r") as f:
                        file_contents = f.read()
                    print("ICS file contents:")
                    print(file_contents)
                except Exception as e:
                    print(f"Error reading ICS file: {e}")


                # Prepare the file for upload
                try:
                    files = {'file': (os.path.basename(ics_filename), open(ics_filename, "rb"), "text/calendar")}
                    data = {'description': 'Here is a calendar invitation with your plan!'}
                    print("About to send file upload POST request with data:", data)
                    print("Headers being used:", HEADERS)
                    response_upload = requests.post(upload_url, headers=upload_headers, data=data, files=files)
                    print("File upload response status code:", response_upload.status_code)
                    print("File upload response text:", response_upload.text)
                    if response_upload.status_code == 200:
                        print(f"File {ics_filename} has been sent to {confirmed_user}.")
                    else:
                        print(f"Failed to send file to {confirmed_user}. Error: {response_upload.text}")
                except Exception as e:
                    print(f"An exception occurred during file upload: {e}")

def send_calendar_to_planner(message, room_id):
    parts = message.split()
    if len(parts) >= 4:
        confirmed_user = parts[1]
        confirmed_friend = parts[2]
        confirmation = parts[3]

        friend_sess_id = session_id + confirmed_user

        if confirmation == "yes": #SEND THE ICAL TO BOTH PARTIES
            # Ask for the friend's username
            system_message = (
                "You are an assistant that generates iCalendar (ICS) documents based on previous conversation context. " 
                "Your output must be a valid ICS file conforming to RFC 5545, " 
                "and include only the ICS content without any additional commentary or explanation. " 
                "Ensure you include mandatory fields such as BEGIN:VCALENDAR, VERSION, PRODID, BEGIN:VEVENT, UID, DTSTAMP, " 
                "DTSTART, DTEND, and SUMMARY."
                "Note that no line length should exceed 75 characters."
            )
            query = (f"""
                    Using the previously generated event summary from our conversation context, generate a complete and valid iCalendar (ICS) document
                    that reflects the event details.
                    Name the calendar event based on the activity/place found in the summary.
                    Set the location of the calendar event to the address of the location in the summary.
                    Set the time of the calendar event to the time of the hangout, using the current date as reference.
                    Keep the description brief (less than 60 characters) to comply with ICS file format.
                    Output only the ICS content with no extra text.
                    Follow valid ICS file format.
                    For reference, today's date and time is {datetime.now(ZoneInfo('America/New_York'))}.
                    """)
            response = generate(
                model='4o-mini',
                system= system_message,
                query= query,
                temperature=0.0,
                lastk=20,
                session_id=friend_sess_id
            )
            ical_content = response.get('response').strip()
            if ical_content.startswith("```") and ical_content.endswith("```"):
                ical_content = ical_content[3:-3].strip()
            print("Generated ICS content:")
            print(ical_content)

            # Define the upload URL (same for all uploads)
            print("Room ID for file upload:", room_id)
            upload_url = f"{API_BASE_URL}/rooms.upload/{room_id}"
            print("Constructed upload URL:", upload_url)

            # Write the ICS content to a file
            ics_filename = "event.ics"
            print(f"Writing ICS content to file: {ics_filename}")
            ics_content = ical_content.replace("\n", "\r\n")
            ics_content = ics_content.strip()

            try:
                with open(ics_filename, "w") as f:
                    f.write(ics_content)
                print("ICS file written successfully.")
            except Exception as e:
                print(f"Error writing ICS file: {e}")

            # Read and print the ICS file contents
            try:
                with open(ics_filename, "r") as f:
                    file_contents = f.read()
                print("ICS file contents:")
                print(file_contents)
            except Exception as e:
                print(f"Error reading ICS file: {e}")


            # Prepare the file for upload
            try:
                files = {'file': (os.path.basename(ics_filename), open(ics_filename, "rb"), "text/calendar")}
                data = {'description': 'Here is a calendar invitation with your plan!'}
                print("About to send file upload POST request with data:", data)
                print("Headers being used:", HEADERS)
                response_upload = requests.post(upload_url, headers=upload_headers, data=data, files=files)
                print("File upload response status code:", response_upload.status_code)
                print("File upload response text:", response_upload.text)
                if response_upload.status_code == 200:
                    print(f"File {ics_filename} has been sent to {confirmed_user}.")
                else:
                    print(f"Failed to send file to {confirmed_user}. Error: {response_upload.text}")
            except Exception as e:
                print(f"An exception occurred during file upload: {e}")
            
            
            payload_user = {
                "channel": f"@{confirmed_user}",
                "text": f"The event has been confirmed!",
                "attachments": [
                    {
                        "text": "Would you like to download the event to your calendar?",
                        "actions": [
                            {
                                "type": "button",
                                "text": "Add to calendar📅",
                                "msg": f"!calendar {confirmed_user} {confirmed_friend} yes",
                                "msg_in_chat_window": True
                            },
                            {
                                "type": "button",
                                "text": "❌ No",
                                "msg": f"!calendar {confirmed_user} {confirmed_friend} no",
                                "msg_in_chat_window": True
                            }
                        ]
                    }
            ]

            }

            try:
                response = requests.post(ROCKETCHAT_URL, json=payload_user, headers=HEADERS)
                response.raise_for_status()

                return response.json()
            except Exception as e:
                print(f"An error occurred stating the confirmation: {e}")
                return {"error": f"Error: {e}"}
            

        elif confirmation == "no":
            payload_user = {
                "channel": f"@{confirmed_user}",
                "text": f"The event was cancelled with {confirmed_friend}!"
            }
            payload_friend = {
                "channel": f"@{confirmed_friend}",
                "text": f"The event was cancelled with {confirmed_user}!"
            }

            try:
                response = requests.post(ROCKETCHAT_URL, json=payload_user, headers=HEADERS)
                response.raise_for_status()
                response_friend = requests.post(ROCKETCHAT_URL, json=payload_friend, headers=HEADERS)
                response_friend.raise_for_status()

                return response.json()
            except Exception as e:
                print(f"An error occurred rejecting the confirmation: {e}")
                return {"error": f"Error: {e}"}

def radius_command(user, message, sess_id):
    parts = message.split()
    confirmed_user = parts[1]
    command_type = parts[2]
    if command_type == "radius":
        print(f"Increasing search radius and redoing API call...")
        try: 
            response = generate(
                model = '4o-mini',
                system = 'Be friendly and give human readable text. Remember the output of this query for future reference.',
                query = (
                    '''What was the previous message generated in chat'''
                ),
                temperature=0.3,
                lastk=5,
                session_id=sess_id
            )
            response_text = response['response']
            print('LAST MESSAGE WAS: ', response_text)
            activity = agent_activity(response_text)
            location = agent_location(response_text)

            params = {
                "category": activity,
                "bias": location,
                "limit":10,
                "apiKey":os.environ.get("geoapifyApiKey")
            }

            url = f"https://api.geoapify.com/v2/places?categories={params['category']}&filter=circle:{params['bias']},16093&limit=10&apiKey={params['apiKey']}"
            api_result = requests.get(url)
            print(url)
            if api_result.status_code == 200:
                data_api = api_result.json()
                print('THIS IS THE API RESULT.JSON: ', data_api)
                if len(data_api['features']) == 0:
                    print("No features generated by the API.")
                    payload = {
                        "channel": f"@{user}",
                        "text": response_text,
                        "attachments": [
                            {
                                "text": "No options were found, would you like to try a new activity?",
                                "actions": [
                                    {
                                        "type": "button",
                                        "text": "🆕 Activity",
                                        "msg": f"!redo {user} activity",
                                        "msg_in_chat_window": True
                                    }
                                ]
                            }
                        ]
                    }
                    try:
                        # Send the message with buttons to Rocket.Chat
                        response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
                        response.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)
                        return response.json()  # Return the JSON response if successful
                    except Exception as e:
                        # Handle any other unexpected errors
                        return {"error": f"Unexpected error: {e}"}

                print("Geoapify API response:", data_api)
            else:
                print("Error calling Geoapify API")

            system_message = (
                """You are a friendly assistant that formats API responses as a catalog of choices.
                Given a list of activities, output:
                1. On the first line, only the number of items provided.
                2. On the following lines, list each option on its own line prefixed with its number (starting at 1) and the details.
                Do not include any extra commentary or headings."""
            )
            response = generate(
                model = '4o-mini',
                system = system_message,
                query = (
                    f'''The following list of activities was generated from an API call: {api_result.json()}.
                    Only print the first 4 to start (if there are 4).
                    Please format the output so that:
                        - The first line is only the count of items in the list (not the limit of the API call, but the amount received and printed).
                        - Immediately after a newline, list the options as numbered choices with all relevant details.
                    Only include the options provided and nothing else.

                    In subsequent requests, refer to these numbers for any follow-up actions.
                    Right now, just show the first 4. Only show more when requested to. Do not
                    restart the numbering if more are asked to be seen.'''
                ),
                temperature=0.3,
                lastk=20,
                session_id=sess_id
            )
            response_text = response['response']

            print('nonstripped list')
            print(response_text)

            parts = response_text.split()
            responses_no = int(parts[0])
            lines = response_text.splitlines()
            # Reassemble the output without the first line (the number and its newline)
            if len(lines) > 1:
                response_text = "\n".join(lines[1:])
            else:
                response_text = ""
            print('LIST OF PLACES GENERATED')
            print(response_text)

            rocketchat_response = send_message_with_buttons(parts=parts, username=user, text=response_text)
            return jsonify({"status": "redo_search"})
        except Exception as e:
            # Log the error and update response_text with a generic error message
            print(f"An error occurred: {e}")
            response_text = "An error occurred while processing your request. Please try again later."


def redo_command(user, message, sess_id):
    parts = message.split()
    confirmed_user = parts[1]
    command_type = parts[2]
    if len(parts) < 3:
        return {"error": "Invalid command format. Use `!redo username radius` or `!redo username activity`"}

    if command_type == "activity":
        print("Fetching a new activity...")
        return
        # payload = {
        #         "channel": f"@{confirmed_user}",
        #         "text": f"Give a new activity"
        # }
        # try:
        #     response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
        #     response.raise_for_status()

        #     return response.json()
        # except Exception as e:
        #     print(f"An error occurred stating the confirmation: {e}")
        #     return {"error": f"Error: {e}"}
    
    else:
        return {"error": "Invalid option. Use `radius` to expand the search or `activity` to try a new one."}


def details_complete(room_id, response_text, user, sess_id, page=0):
    """
    Called when all necessary details have been provided.
    This function calls the Geoapify API with the extracted activity and location,
    then stores and displays a limited subset of the results.
    """
    print("ALL NECESSARY DETAILS")

    payload_initial = {
        "channel": f"@{user}",
        "text": "🔍 Gathering details... Hang tight while I process your request!",
    }
    requests.post(ROCKETCHAT_URL, json=payload_initial, headers=HEADERS)
    send_typing_indicator(room_id)
    try: 
        # Extract activity and location from the response
        activity = agent_activity(response_text)
        location = agent_location(response_text)
        
        # Set up parameters for the Geoapify API
        params = {
            "category": activity,
            "bias": location,
            "limit": 10,
            "apiKey": os.environ.get("geoapifyApiKey")
        }
        
        # Construct the API URL (using a circular filter with a 5000 meter radius here)
        url = f"https://api.geoapify.com/v2/places?categories={params['category']}&filter=circle:{params['bias']},5000&limit={params['limit']}&apiKey={params['apiKey']}"
        print("Calling Geoapify API:", url)
        api_result = requests.get(url)
        
        if api_result.status_code == 200:
            data_api = api_result.json()
            print("Geoapify API response:", data_api)
            features = data_api.get("features", [])
            if not features:
                print("No features found by the API.")
                payload = {
                    "channel": f"@{user}",
                    "text": response_text,
                    "attachments": [
                        {
                            "text": "No options were found. Would you like to increase the search radius or try a new activity?",
                            "actions": [
                                {
                                    "type": "button",
                                    "text": "⬆️ Search Radius",
                                    "msg": f"!radius {user} radius",
                                    "msg_in_chat_window": True
                                },
                                {
                                    "type": "button",
                                    "text": "🆕 Activity",
                                    "msg": f"!redo {user} activity",
                                    "msg_in_chat_window": True
                                }
                            ]
                        }
                    ]
                }
                response_payload = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
                response_payload.raise_for_status()
                return response_payload.json()
            
            # Save the full results and reset the current index for this user
            # Display the first subset of results using our helper function

            system_message = (
                """You are a friendly assistant that formats API responses as a catalog of choices.
                Given a list of activities, output:
                1. On the first line, only the number of items provided.
                2. On the following lines, list each option on its own line prefixed with its number (starting at 1) and the details.
                Do not include any extra commentary or headings."""
            )
            response = generate(
                model = '4o-mini',
                system = system_message,
                query = (
                    f'''The following list of activities was generated from an API call: {api_result.json()}.
                    Only print the first 4 to start (if there are 4).
                    Please format the output so that:
                        - The first line is only the count of items in the list (not the limit of the API call, but the amount received and printed).
                        - Immediately after a newline, list the options as numbered choices with all relevant details.
                    Only include the options provided and nothing else.

                    In subsequent requests, refer to these numbers for any follow-up actions.
                    Right now, just show the first 4. Only show more when requested to. Do not
                    restart the numbering if more are asked to be seen.'''
                ),
                temperature=0.3,
                lastk=20,
                session_id=sess_id
            )
            response_text = response['response']
            
            print('nonstripped list')
            print(response_text)

            parts = response_text.split()
            responses_no = int(parts[0])
            lines = response_text.splitlines()
            # Reassemble the output without the first line (the number and its newline)
            if len(lines) > 1:
                response_text = "\n".join(lines[1:])
            else:
                response_text = ""
            print('LIST OF PLACES GENERATED')
            print(response_text)
 
            rocketchat_response = send_message_with_buttons(parts=parts, username=user, text=response_text)
        else:
            print("Error calling Geoapify API:", api_result.text)
            payload = {
                "channel": f"@{user}",
                "text": "Error retrieving location options. Please try again later."
            }
            requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
    except Exception as e:
        print(f"An error occurred in details_complete: {e}")
        payload = {
            "channel": f"@{user}",
            "text": "An error occurred while processing your request. Please try again later."
        }
        requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)

@app.route('/', methods=['POST'])
def hello_world():
   return jsonify({"text":'Hello from Koyeb - you reached the main page!'})

@app.route('/query', methods=['POST'])
def main():
    data = request.get_json() 
    room_id = data.get("channel_id", "")

    # Extract relevant information
    user = data.get("user_name", "Unknown")
    message = data.get("text", "")
    sess_id = session_id + user

    print(data)

    # Ignore bot messages
    if data.get("bot") or not message:
        return jsonify({"status": "ignored"})

    print(f"Message from {user} : {message}")

    intent = agent_detect_intent(message)
    if intent == "1":
        print("========SEND_ACTIVITY_SUGGESTIONS START========")
        send_activity_suggestions(user)
        print("========SEND_ACTIVITY_SUGGESTIONS DONE========")
        return jsonify({"status": "activity_suggestions"})
    
    print("message length", len(message.split()[0]) == 1)
    print(message.split())

    if (len(message.split()) == 1) and message.split()[0].isdigit():
        print("========ACTIVITY_CHOSEN START========")
        activity_chosen(message, user, sess_id)
        print("========ACTIVITY_CHOSEN DONE========")
        return jsonify({"status": "activity_chosen"})
    
    if (len(message.split()) == 1) and is_valid_username(message.split()[0]):
        print("========REGENERATE_SUMMARY START========")
        plan_text = regenerate_summary(sess_id)
        print("========REGENERATE_SUMMARY DONE========")
        print("========SEND_PLAN_TO_FRIEND START========")
        send_plan_to_friend(message, user, plan_text) 
        print("========SEND_PLAN_TO_FRIEND DONE========")
        return jsonify({"status": "plan_sent", "friend_username": message})

    # Check if the message is a confirmation response
    if message.startswith("!confirm"):
        print("========CONFIRM_COMMAND START========")
        confirm_command(message)
        print("========CONFIRM_COMMAND DONE========")
        return jsonify({"status": "valid_confirmation"})
    
    # if message.startswith("!more"):
    #     print("========HANDLE_SHOW_MORE START========")
    #     handle_show_more(message)
    #     print("========HANDLE_SHOW_MORE START========")
    #     return jsonify({"status": "show_more_handled"})
        
    if message.startswith("!calendar"):
        print("========CALENDAR COMMAND START========")
        send_calendar_to_recipient(message, room_id)
        print("========CALENDAR COMMAND DONE========")
        return jsonify({"status": "calendar_sent"})
        

    if message.startswith("!final"):
        print("========SEND CALENDAR TO PLANNER FINAL COMMAND START ========")
        send_calendar_to_planner(message, room_id)
        print("========SEND CALENDAR TO PLANNER FINAL COMMAND DONE ========")
        return jsonify({"status": "valid_confirmation"})

    if message.startswith("!redo"): 
        print("========REDO COMMAND START========")
        redo_command(user, message, sess_id)
        print("========REDO COMMAND DONE========")

    if message.startswith("!radius"): 
        print("========REDO COMMAND START========")
        radius_command(user, message, sess_id)
        return jsonify({"status": "larger_radius_search"})
        print("========REDO COMMAND DONE========")

    print('MESSAGE BEFORE THE QUERY:', message)

    query = (
        "You are an aide to make hangout plans, a friendly assistant helping users plan a hangout. "
        "Your goal is to obtain all of the following details from the user: location, date, time (specific), and activity. "
        "If any one of these details is missing, ask a clear and direct question for that specific missing detail. "
        "Do not produce a final summary until you have all the required details. "
        "If the user inputs information that they have already given (changed their mind), rewrite over the previous information for that specific detail"
        "Do not ask for clarification for information that you have already received."
        "Only the time needs to be specific. The activity and location do not need to be. Do not prompt the user to make it more specific if they have already given the information."
        "Only when all details are provided, respond with exactly: 'All necessary details completed:' followed by a summary of the plan. "
        f"This is the user's next message: {message}"
    )
    system = (
        "You are an aide to make hangout plans, a helpful and friendly assistant. "
        "This is an ongoing conversation—do NOT restart it. Always remember what has already been discussed. "
        "If any of the required details (location, date, time, or activity) are missing, ask a clear and direct question to obtain them. "
        "Only when all details are provided, summarize the plan starting with: 'All necessary details completed:'. "
        "Do not ask for clarification for information that you have already received."
        "Please use emojis where appropriate."
    )

    print("*********ABOUT TO START QUERY*********")
    # Generate a response using LLMProxy
    response = generate(
        model='4o-mini',
        system=system,
        query= query,
        temperature=0.0,
        lastk=20,
        session_id=sess_id
    )
    print("*********QUERY FINISHED*********")
    response_text = response.get('response', '').strip()
    print("RESPONSE TEXT: ", response_text)
    print(sess_id)

    if "All necessary details completed" in response_text:
        print("========DETAILS_COMPLETE STARTED========")
        details_complete(room_id, response_text, user, sess_id)   
        print("========DETAILS_COMPLETE COMMAND DONE========")     
        return jsonify({"status": "details_complete"})
    else: 
        print(response_text)
        return jsonify({"text": response_text})

#bias=proximity:lon,lat
def agent_location(query):
    print('IN LOCATION AGENT')
    query_edited = (
        f"Extract the location of the user input and convert it to longitutde and latitiude.\n\n"
        f"User input is provided between triple asterisks: ***{query}***.\n\n"
    )
    system = """ 
        Extract the latitude and longitude of the given location in the format
        lon,lat. Only include this. Exclude all other information.
    """

    response = generate(model = '4o-mini',
        system = system,
        query = query_edited,
        temperature=0.3,
        lastk=0,
        session_id="generic"
    )

    try:
        print(response['response'])
        return response.get('response', '').strip()
    except Exception as e:
        print(f"Error occured with parsing output: {response}")
        raise e
    return 

def agent_activity(message):
    print('IN ACTIVITY AGENT')

    categories_pdf = pdf_upload(
        path = 'categories.pdf',
        session_id='activity_agent',
        strategy = 'smart')
    
    query = (
        f'''
        The user provided the following request: ***{message}***.
        Based on this request and the uploaded document, find the closest matching activity category.
        The category **must** be explicitly listed in the following:

        "activity, activity.community_center, activity.sport_club, catering.restaurant,
        catering.fast_food, catering.cafe, catering.food_court, catering.bar, catering.pub,
        catering.ice_cream, catering.biergarten, catering.taproom, entertainment.culture.theatre,
        entertainment.culture.arts_centre, entertainment.culture.gallery, entertainment.zoo,
        entertainment.aquarium, entertainment.planetarium, entertainment.museum, entertainment.cinema,
        entertainment.amusement_arcade, entertainment.escape_game, entertainment.miniature_golf,
        entertainment.bowling_alley, entertainment.flying_fox, entertainment.theme_park,
        entertainment.water_park, entertainment.activity_park.trampoline,
        entertainment.activity_park.climbing, leisure.picnic, leisure.playground, leisure.spa,
        leisure.park, leisure.park.garden, leisure.park.nature_reserve, camping.camp_pitch,
        camping.camp_site, camping.summer_camp, camping.caravan_site, sport.stadium,
        sport.dive_centre, sport.horse_riding, sport.ice_rink, sport.pitch, sport.sports_centre,
        sport.swimming_pool, sport.track, sport.fitness, ski, tourism.attraction.viewpoint,
        tourism.sights.castle, tourism.sights.ruines, tourism.sights.archaeological_site,
        tourism.sights.lighthouse, tourism.sights.tower, adult.nightclub, adult.casino, beach,
        natural.forest, natural.water.hot_spring, natural.mountain, natural.sand.dune, national_park,
        pet.dog_park, commercial.outdoor_and_sport, commercial.outdoor_and_sport.water_sports,
        commercial.outdoor_and_sport.ski, commercial.outdoor_and_sport.diving, commercial.outdoor_and_sport.hunting,
        commercial.outdoor_and_sport.bicycle, commercial.outdoor_and_sport.fishing,
        commercial.outdoor_and_sport.golf, commercial.clothing.sport, commercial.marketplace,
        commercial.shopping_mall, commercial.department_store, commercial.clothing,
        commercial.clothing.accessories, commercial.gift_and_souvenir, commercial.bag, commercial.jewelry,
        
        Respond **only** with the exact category name from the above. Do not add any extra text. 
        Example output: `catering.restaurant`
        '''
    )

    system_prompt = """
        You are an assistant that extracts the closest matching category from the uploaded document.
        - The category **must** be listed in the document.
        - Do not infer or create new categories. Paste the exact category name from the document.
        - Respond with only the category name, exactly as it appears in the document.
    """

    response = generate(
        model='4o-mini',
        system=system_prompt,
        query=query,
        temperature=0.0,
        lastk=1,
        session_id="activity_agent",
    )
    
    # Extract the category from the LLM response.
    category = response.get('response', '').strip()
    print("Determined activity category:", category)
    return category

def agent_detect_intent(query):
    '''
    Uses LLM to detect intent.
    "1": message includes a request for suggestions
    "2": all other messages
    '''
    query = (f"""
                You are an intent detection assistant. Analyze the following message: {query}.
                Respond with a single number and just a single number. Respond with '1'
                if the user is asking for suggestions for an activity or is not sure 
                what to do as an activity. Otherwise, return '2'.
                Any vague idea of an activity (e.g., restaurant) counts as an activity and
                thus you can return '2'.
                If the user is stating an activity and not asking for a recommendation, return '2'.
            """)
    intent_response = generate(
        model='4o-mini',
        system=(
            "You are an intent detection assistant. "
            "Analyze the following user message and return a single number: "
            "return '1' if the user is asking for activity suggestions, and '2' otherwise."            
        ),
        query=query,
        temperature=0.0,
        lastk=1,
        session_id="intent_detector"
    )

    if isinstance(intent_response, dict):
        intent = intent_response.get('response', '').strip()
    else:
        intent = intent_response.strip()
    print(f"Detected intent: {intent}")
    return intent

@app.errorhandler(404)
def page_not_found(e):
    return "Not Found", 404

if __name__ == "__main__":
    app.run()