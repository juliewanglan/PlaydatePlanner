import requests
from flask import Flask, request, jsonify, session
from flask_session import Session
from llmproxy import generate, pdf_upload
import os
import uuid

app = Flask(__name__)
session_id = "3playdatePlanner-"

# Rocket.Chat API endpoint
API_BASE_URL = "https://chat.genaiconnect.net/api/v1"
ROCKETCHAT_URL = "https://chat.genaiconnect.net/api/v1/chat.postMessage"  # Keep the same URL

# Headers with authentication tokens stored securely in environment variables
HEADERS = {
    "Content-Type": "application/json",
    "X-Auth-Token": os.environ.get("RC_token"),  #Replace with your bot token for local testing or keep it and store secrets in Koyeb
    "X-User-Id": os.environ.get("RC_userId") #Replace with your bot user id for local testing or keep it and store secrets in Koyeb
}


def send_message_with_buttons(username, text):
    """Send a message with Yes/No buttons for plan confirmation."""
    payload = {
        "channel": f"@{username}",
        "text": text,
        "attachments": [
            {
                "text": "Would you like to send these options to a friend?",
                "actions": [
                    {
                        "type": "button",
                        "text": "✅ Yes",
                        "msg": f"!confirm {username} yes",
                        "msg_in_chat_window": True
                    },
                    {
                        "type": "button",
                        "text": "❌ No",
                        "msg": f"!confirm {username} no",
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

def send_plan_to_friend(friend_username, plan_text):
    """
    Send the plan message to the friend.
    """
    payload = {
        "channel": f"@{friend_username}",
        "text": plan_text
    }
    try:
        response = requests.post(f"{ROCKETCHAT_URL}", json=payload, headers=HEADERS)
        response.raise_for_status()
        print(f"Plan sent successfully to {friend_username}.")
        return response.json()
    except Exception as e:
        print(f"Error sending plan to {friend_username}: {e}")
        return {"error": str(e)}


@app.route('/', methods=['POST'])
def hello_world():
   return jsonify({"text":'Hello from Koyeb - you reached the main page!'})

@app.route('/query', methods=['POST'])
def main():
    data = request.get_json() 

    # Extract relevant information
    user = data.get("user_name", "Unknown")
    message = data.get("text", "")
    sess_id = session_id + user

    print(data)

    # Ignore bot messages
    if data.get("bot") or not message:
        return jsonify({"status": "ignored"})

    print(f"Message from {user} : {message}")

    if len(message.split()) == 1:
        if is_valid_username(message):
            plan_text = "HIHI MESSAGE!!"  # Replace with your actual plan message
            send_plan_to_friend(message, plan_text)
            return jsonify({"status": "plan_sent", "friend_username": message})
        else:
            # Optionally, you might want to send an error back to the user.
            error_payload = {
                "channel": f"@{user}",
                "text": f"'{message}' is not a valid username. Please try again."
            }
            requests.post(f"{ROCKETCHAT_URL}/chat.postMessage", json=error_payload, headers=HEADERS)
            return jsonify({"status": "invalid_username"})


    # Check if the message is a confirmation response
    if message.startswith("!confirm"):
        parts = message.split()
        if len(parts) >= 3:
            confirmed_user = parts[1]
            confirmation = parts[2]

            if confirmation == "yes":
                # Ask for the friend's username
                ask_for_friend_username(confirmed_user)
                return jsonify({"status": "asked_for_friend_username"})
            elif confirmation == "no":
                return jsonify({"status": "confirmation_denied"})
        return jsonify({"status": "invalid_confirmation"})

    query = (
        "You are PlaydatePlanner, a friendly assistant helping users plan a hangout. "
        "Your goal is to gather three key details: location, time, and activity. "
        "Only ask about missing details—do not ask again if the user has already provided something. "
        "Once all details are collected, respond with exactly: 'All necessary details completed:' followed by a summary. "

        f"This is the user's next message: {message}"
    )
    system = (
        "You are PlaydatePlanner, a helpful and friendly assistant. 🎉 "
        "This is an ongoing conversation—do NOT restart it. "
        "Always remember what has already been discussed. "
        "Ask clarifying questions only if required details (location, time, or activity) are missing. "
        "If everything is provided, summarize the plan starting with: 'All necessary details completed:'. "
        "Do NOT repeat questions unnecessarily."
    )

    # Generate a response using LLMProxy
    response = generate(
        model='4o-mini',
        system=system,
        query= query,
        temperature=0.0,
        lastk=10,
        session_id=sess_id
    )

    response_text = response['response']

    print(sess_id)

    if "All necessary details completed" in response_text:
        print("ALL NECESSARY DETAILS")
        try: 
            activity = agent_activity(response_text)
            location = agent_location(response_text)

            params = {
                "category": activity,
                "bias": location,
                "limit":10,
                "apiKey":os.environ.get("geoapifyApiKey")
            }

            url = f"https://api.geoapify.com/v2/places?categories={params['category']}&filter=circle:{params['bias']},1000&limit=10&apiKey={params['apiKey']}"
            api_result = requests.get(url)
            print(url)
            if api_result.status_code == 200:
                data_api = api_result.json()
                print("Geoapify API response:", data_api)
            else:
                print("Error calling Geoapify API")

            response = generate(model = '4o-mini',
                system = 'Give human readable text',
                query = f"Format the results of this api call nicely: {api_result.json()}",
                temperature=0.3,
                lastk=0,
                session_id="generic"

            )
            response_text = response['response']
            print('LIST OF PLACES GENERATED')
            print(response_text)
        except Exception as e:
            # Log the error and update response_text with a generic error message
            print(f"An error occurred: {e}")
            response_text = "An error occurred while processing your request. Please try again later."

        rocketchat_response = send_message_with_buttons(user, response_text)
    
    # feed response to location agent and activity agent
    # agents parse thru the info to get the zipcode and activity

    # rocketchat_response = send_message_with_buttons(user, response_text)
    
    # Send response back
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
        The category **must** be explicitly listed in the document. 
        Respond **only** with the exact category name from the document. Do not add any extra text. 
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
        rag_usage=True,
        rag_threshold='0.90',
        rag_k=3
    )
    
    # Extract the category from the LLM response.
    category = response.get('response', '').strip()
    print("Determined activity category:", category)
    return category

    
@app.errorhandler(404)
def page_not_found(e):
    return "Not Found", 404

if __name__ == "__main__":
    app.run()