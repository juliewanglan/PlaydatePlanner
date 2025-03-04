import requests
from flask import Flask, request, jsonify
from llmproxy import generate, pdf_upload
import os
import uuid

app = Flask(__name__)
session_id = "3playdatePlanner-"

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

        #rocketchat_response = send_message_with_buttons(user, response_text)
    
    # feed response to location agent and activity agent
    # agents parse thru the info to get the zipcode and activity

    rocketchat_response = send_message_with_buttons(user, response_text)
    
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

    csgrad_handbook_pdf = pdf_upload(
        path = 'categories.pdf',
        session_id='activity_agent',
        strategy = 'smart')
    query = (
        f'''
        This is what the user wants in a plan: {message}.
        Based off this message and the uploaded document, respond with the closest activity.
        Or, match their descripton with the closest activity.
        Only respond with the category from the following mapping or a category in the document (and nothing else):
            "restaurant": "catering.restaurant",
            "cafe": "catering.cafe",
            "bar": "catering.pub",
            "fast food": "catering.fast_food",
            
            "park": "leisure.park",
            "picnic": "leisure.picnic",
            "museum": "entertainment.museum",
            "movie": "entertainment.cinema",
            "theater": "entertainment.culture",
            "club": "adult.nightclub",
            "concert": "entertainment.culture",
            "live music": "entertainment.culture",
            
            "shopping": "commercial.shopping_mall",
            "market": "commercial.marketplace",
            
            "sports": "commercial.outdoor_and_sport",
            "hobby": "commercial.hobby",
            "books": "commercial.books",
            "flowers": "commercial.florist",
            "toys and games": "commercial.toy_and_game",

            "thrift": "commercial.second_hand",
            "antiques": "commercial.antiques",
            "culture": "entertainment.culture",
            "arcade": "entertainment_arcade",
            
        Respond with only the category value, for example: catering.restaurant
        '''
    )
    response = generate(
        model='4o-mini',
        system="Extract the appropriate category based on the user's request. Respond only with the category.",
        query=query,
        temperature=0.0,
        lastk=1,
        session_id="activity_agent"
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