import requests
from flask import Flask, request, jsonify
from llmproxy import generate
import os
import uuid

app = Flask(__name__)

# Rocket.Chat API endpoint
ROCKETCHAT_URL = "https://chat.genaiconnect.net/api/v1/chat.postMessage"  # Keep the same URL

# Headers with authentication tokens stored securely in environment variables
HEADERS = {
    "Content-Type": "application/json",
    "X-Auth-Token": os.environ.get("RC_token"),  #Replace with your bot token for local testing or keep it and store secrets in Koyeb
    "X-User-Id": os.environ.get("RC_userId") #Replace with your bot user id for local testing or keep it and store secrets in Koyeb
}

def activity_extraction_agent(message):
    '''Extract the type of activity from the user query'''
    query = (
        '''
        Extract any information on the type of activity the user wants from the prompt.
        T
        '''
    )

def send_message_with_buttons(username, text):
    """Send a message with Yes/No buttons for plan confirmation."""
    payload = {
        "channel": f"@{username}",
        "text": text,
        "attachments": [
            {
                "text": "Do you want to finalize this plan?",
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

    response = requests.post(ROCKETCHAT_URL, json=payload, headers=HEADERS)
    return response.json()

@app.route('/', methods=['POST'])
def hello_world():
   return jsonify({"text":'Hello from Koyeb - you reached the main page!'})

@app.route('/query', methods=['POST'])
def main():
    data = request.get_json() 

    # Extract relevant information
    user = data.get("user_name", "Unknown")
    message = data.get("text", "")
    sess_id = "PLAYDATE PLANNER"

    print(data)

    # Ignore bot messages
    if data.get("bot") or not message:
        return jsonify({"status": "ignored"})

    print(f"Message from {user} : {message}")

    query = (
        f"You are PlaydatePlanner, a friendly assistant that helps users plan hangouts with their friends. "
        f"Your goal is to collect all the necessary information to create a complete hangout plan. "
        f"Specifically, you need the following details:\n"
        f"1. The location (city and state).\n"
        f"2. The time or time period for the hangout.\n"
        f"3. The type of activity they want to do.\n\n"
        f"User input is provided between triple asterisks: ***{message}***.\n\n"
        f"Examine the input carefully. If any of the details are missing, ask the user a follow-up question to obtain that specific missing information. "
        f"Ask one question at a time and in a friendly manner. "
        f"Once all the required details are provided, generate a complete hangout plan including a suggested date, time, activity, and location."
    )
    system = (
        "Answer as a friendly helper called PlaydatePlanner. "
        "If the user's input is missing any required detail (location, time, or activity), ask a clarifying question to get that missing information. "
        "Only generate a complete plan once you have all the necessary details."
    )

    # Generate a response using LLMProxy
    response = generate(
        model='4o-mini',
        system=system,
        query= query,
        temperature=0.0,
        lastk=50,
        session_id=sess_id
    )

    response_text = response['response']

    # feed response to location agent and activity agent
    # agents parse thru the info to get the zipcode and activi

    # rocketchat_response = send_message_with_buttons(user, response_text)
    
    # Send response back
    print(response_text)

    return jsonify({"text": response_text})
    
def agent_location(query, sess_id):
    system = """
    Goal is to return the zipcode of the given location.
    """

    response = generate(model = '4o-mini',
        system = system,
        query = query,
        temperature=0.3,
        lastk=10,
        session_id=sess_id,
    )

    try:
        print(response['response'])
        return response['response']
    except Exception as e:
        print(f"Error occured with parsing output: {response}")
        raise e
    return 


@app.route('/interaction', methods=['POST'])
def handle_interaction():
    """Handle Rocket.Chat button clicks from users."""
    data = request.get_json()
    user = data.get("user_name", "Unknown")
    message_text = data.get("text", "")

    print(f"Interaction received from {user}: {message_text}")

    if "!confirm" in message_text:
        parts = message_text.split()
        if len(parts) >= 3:
            target_user = parts[1]
            decision = parts[2]

            update_text = f"🎉 {user} has finalized the plan! ✅" if decision == "yes" else f"❌ {user} has rejected the plan."

            # Send confirmation message
            send_message_with_buttons(target_user, update_text)

    return jsonify({"status": "success"})
    
@app.errorhandler(404)
def page_not_found(e):
    return "Not Found", 404

if __name__ == "__main__":
    app.run()