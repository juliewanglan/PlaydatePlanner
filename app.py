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
    sess_id = "PLAYDATE PLANNER-testing"

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
        f"2. The times or time periods for the hangout.\n"
        f"3. The type of activity they want to do.\n\n"
        f"User input is provided between triple asterisks: ***{message}***.\n\n"
        f"Examine the input carefully. If any of the details are missing, ask the user a follow-up question to obtain that specific missing information. "
        f"Ask one question at a time and in a friendly manner. "
        f"Once you have all the necessary details, output the phrase 'All necessary details completed:' "
        "followed by a summary of all the details "
    )
    system = (
        "Answer as a friendly helper called PlaydatePlanner. "
        "If the user's input is missing any required detail (location, time, or activity), ask a clarifying question to get that missing information. "
        "Once you have all the necessary details, generate a summary which starts with "
        "the phrase 'All necessary details completed:"
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

    if "All necessary details completed" in response_text:
        print("ALL NECESSARY DETAILS")
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
            print("Error calling Geoapify API:", data_api.text)

        response = generate(model = '4o-mini',
            system = 'Give human readable text',
            query = f"Format the results of this api call nicely: {api_result.json()}",
            temperature=0.3,
            lastk=10,
            session_id='playdateplanner-json',
        )
        response_text = response['response']

        #rocketchat_response = send_message_with_buttons(user, response_text)
    
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
        lastk=10,
        session_id='playDatePlanner_agent_location',
    )

    try:
        print(response['response'])
        return response['response']
    except Exception as e:
        print(f"Error occured with parsing output: {response}")
        raise e
    return 

def agent_activity(message):
    print('IN ACTIVITY AGENT')
    query = (
        f'''
        This is what the user wants in a plan: {message}.
        Based off this message, respond with the closest activity.
        Only respond with the category from the following mapping (and nothing else):
            "restaurant": "catering.restaurant",
            "dining": "catering.restaurant",
            "food": "catering.restaurant",
            "pakistani": "catering.restaurant",
            "italian": "catering.restaurant",
            "chinese": "catering.restaurant",
            "mexican": "catering.restaurant",
            "japanese": "catering.restaurant",
            "american": "catering.restaurant",
            "burger": "catering.restaurant",
            "cafe": "catering.cafe",
            "coffee": "catering.cafe",
            "bar": "catering.pub",
            "pub": "catering.pub",
            "fast food": "catering.fast_food",
            
            "park": "leisure.park",
            "picnic": "leisure.picnic",
            "museum": "entertainment.museum",
            "cinema": "entertainment.cinema",
            "movie": "entertainment.cinema",
            "theatre": "entertainment.culture",
            "theater": "entertainment.culture",
            "nightclub": "adult.nightclub",
            "club": "adult.nightclub",
            "concert": "entertainment.culture",
            "live music": "entertainment.culture",
            
            "shopping": "commercial.shopping_mall",
            "mall": "commercial.shopping_mall",
            "market": "commercial.marketplace",
            
            "hiking": "leisure.hiking",
            "gym": "sport.fitness",
            "fitness": "sport.fitness",
            "spa": "leisure.spa"
            
        Respond with only the category value, for example: catering.restaurant
        '''
    )
    response = generate(
        model='4o-mini',
        system="Extract the appropriate category based on the user's request. Respond only with the category.",
        query=query,
        temperature=0.0,
        lastk=10,
        session_id="AGENT-ACTIVITY"
    )
    
    # Extract the category from the LLM response.
    category = response.get('response', '').strip()
    print("Determined activity category:", category)
    return category

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