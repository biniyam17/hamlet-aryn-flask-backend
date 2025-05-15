from flask import Flask, request, jsonify
from aryn_sdk.client.client import Client, Query
from supabase import create_client, Client as SupabaseClient
import os
from datetime import datetime, UTC
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load configuration from environment variables
TEST_MODE = os.environ["TEST_MODE"].lower() == "true"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
API_TOKEN = os.environ["ARYN_API_TOKEN"]

print("in test mode? ", TEST_MODE)

# Initialize Supabase client
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

# Dummy result for testing mode
class DummyQueryResult:
    def __init__(self):
        self.query_id = '45imecgk35du9dnrf4wkqfp'
        self.result = (
            "Anaheim has an ambitious lineup of infrastructure projects planned for the coming years. "
            "The city is focusing on enhancing public safety, improving livability, and investing in infrastructure and amenities. "
            "Key projects include the Anaheim Canyon Metrolink Station improvements, which aim to boost efficiency and reliability for commuters, "
            "and the OC River Walk initiative, which will revitalize a 2-mile corridor along the Santa Ana River. "
            "Additionally, the city is working on the Electric System Underground program to improve reliability and aesthetics by moving power lines underground.\n\n"
            "Anaheim is also committed to sustainable solutions, with projects like the installation of groundwater treatment systems and investments in renewable energy sources. "
            "The city is enhancing recreational spaces, such as the Brookhurst Splash Pad and the Haskett Makerspace/Media Lab, to foster community engagement and skill development.\n\n"
            "Moreover, Anaheim is addressing housing insecurity with projects like Finamore Place Affordable Housing and the Center of Hope initiative, which integrates wrap-around services for the unhoused population. "
            "The city is also focused on revitalizing its corridors, with efforts like the Rebuild Beach Initiative to improve safety and reduce crime along Beach Boulevard.\n\n"
            "Overall, Anaheim's infrastructure projects are designed to create a more connected, sustainable, and vibrant community for residents and visitors alike."
        )

# Helper function to find and update a service response and return its ID
def insert_service_response(supabase, session_id, query_text, result, query_id, created_at):
    # First find the pending record for this session
    find_result = supabase.table("service_responses") \
        .select("id, metadata") \
        .eq("session_id", session_id) \
        .eq("status", "pending") \
        .execute()
    
    if not find_result.data:
        return None
        
    record_id = find_result.data[0]["id"]
    existing_metadata = find_result.data[0].get("metadata", {})
    
    # Update the existing record
    update_data = {
        "content": result,
        "status": "success",
        "metadata": {**existing_metadata, "query_id": query_id}
    }
    
    supabase.table("service_responses") \
        .update(update_data) \
        .eq("id", record_id) \
        .execute()
        
    return record_id

# Helper function to insert a service message
def insert_service_message(supabase, session_id, result, created_at, service_response_id):
    message = {
        "session_id": session_id,
        "content": result,
        "message_type": "service",
        "created_at": created_at,
        "service_response_id": service_response_id,
    }
    supabase.table("messages").insert(message).execute()

# Main route to handle search requests
@app.route('/api/search', methods=['POST'])
def search():
    print(f"\n[{datetime.now()}] Received search request")
    data = request.json
    docset_id = data['docset_id']
    query_text = data['query']
    session_id = data["session_id"]
    
    print(f"[{datetime.now()}] Processing request - Docset: {docset_id}, Session: {session_id}")
    print(f"[{datetime.now()}] Query: {query_text}")

    # Use dummy result in test mode, otherwise call the live API
    if TEST_MODE:
        print(f"[{datetime.now()}] Running in TEST MODE - using dummy result")
        query_result = DummyQueryResult()
    else:
        print(f"[{datetime.now()}] Running in LIVE MODE - calling Aryn API")
        myClient = Client(aryn_api_key=API_TOKEN)
        query_obj = Query(
            docset_id=docset_id,
            query=query_text,
            summarize_result=False,
            plan=None,
            stream=False
        )
        result_obj = myClient.query(query=query_obj)
        if query_obj.stream:
            print(f"[{datetime.now()}] Streaming mode detected")
            for e in result_obj:
                print(f"[{datetime.now()}] Stream event: {e.event_type}")
                print(e.event_type, e.data)
            query_result = None
        else:
            try:
                val = next(result_obj)
            except StopIteration as e:
                response = e.value
                query_result = response.value
                print(f"[{datetime.now()}] Received query result: {query_result}")
                print(f"[{datetime.now()}] Received query result with ID: {query_result.query_id}")
                print(f"[{datetime.now()}] Query result content: {query_result.result}")

    # Persist the service response and message to Supabase
    created_at = datetime.now(UTC).isoformat()
    print(f"[{datetime.now()}] Persisting to Supabase")
    service_response_id = insert_service_response(
        supabase, session_id, query_text, query_result.result if query_result else "", 
        query_result.query_id if query_result else None, created_at
    )
    
    if service_response_id:
        print(f"[{datetime.now()}] Created service response ID: {service_response_id}")
        insert_service_message(
            supabase, session_id, query_result.result if query_result else "", 
            created_at, service_response_id
        )
        print(f"[{datetime.now()}] Created service message")
    else:
        print(f"[{datetime.now()}] ERROR: No pending service response found")
        return jsonify({
            "error": "No pending service response found for this session"
        }), 400

    print(f"[{datetime.now()}] Request completed successfully\n")
    return jsonify({
        "query_id": query_result.query_id,
        "result": query_result.result,
    })

if __name__ == '__main__':
    # Start the Flask app on port 8080
    app.run(debug=True, host='0.0.0.0', port=8080)
