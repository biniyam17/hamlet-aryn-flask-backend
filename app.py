from flask import Flask, request, jsonify
from aryn_sdk.client.client import Client, Query
from supabase import create_client, Client as SupabaseClient
import os
from datetime import datetime, UTC
from dotenv import load_dotenv
import glob

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

# Root endpoint for quick "is this alive?" checks
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "OK", 200


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

def upload_document_to_aryn(client: Client, file_path: str, docset_id: str) -> dict:
    """Helper function to upload a document to Aryn and return the async task info"""
    try:
        async_task = client.add_doc_async(file=file_path, docset_id=docset_id)
        print(f"[{datetime.now()}] Document upload initiated for {file_path}")
        return {
            "status": "success",
            "task_id": async_task.task_id,
            "file_path": file_path
        }
    except Exception as e:
        print(f"[{datetime.now()}] Error initiating document upload for {file_path}: {str(e)}")
        raise e

def upsert_city_to_supabase(supabase: SupabaseClient, city_name: str, docset_id: str) -> bool:
    """Helper function to create or update a city record in Supabase
    
    Args:
        supabase: Supabase client instance
        city_name: Name of the city (will be converted to lowercase)
        docset_id: The docset ID from Aryn
        
    Returns:
        bool: True if city was created/updated, False if it already existed
    """
    try:
        # Convert city name to lowercase
        city_name_lower = city_name.lower()
        
        # Check if city exists
        result = supabase.table("cities") \
            .select("id") \
            .eq("name", city_name_lower) \
            .execute()
            
        if result.data:
            print(f"[{datetime.now()}] City {city_name_lower} already exists in database")
            return False
            
        # Create new city record
        supabase.table("cities") \
            .insert({
                "name": city_name_lower,
                "docset_id": docset_id
            }) \
            .execute()
            
        print(f"[{datetime.now()}] Created new city record for {city_name_lower}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now()}] Error upserting city to Supabase: {str(e)}")
        raise e

@app.route('/api/upload', methods=['POST'])
def upload_document():
    print(f"\n[{datetime.now()}] Received document upload request")
    
    data = request.json
    if not data or 'file_path' not in data:
        return jsonify({
            "error": "No file_path provided"
        }), 400
        
    docset_id = data.get('docset_id')
    if not docset_id:
        return jsonify({
            "error": "No docset_id provided"
        }), 400
        
    file_path = data['file_path']
    print(f"[{datetime.now()}] Processing upload - Docset: {docset_id}, File: {file_path}")
    
    try:
        myClient = Client(aryn_api_key=API_TOKEN)
        result = upload_document_to_aryn(myClient, file_path, docset_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to initiate document upload: {str(e)}"
        }), 500

@app.route('/api/process-documents', methods=['POST'])
def process_documents():
    print(f"\n[{datetime.now()}] Starting batch document processing")
    import pdb; pdb.set_trace()  # Debugger will stop here
    
    try:
        myClient = Client(aryn_api_key=API_TOKEN)
        documents_path = "../documents/*.pdf"
        
        # Get all PDF files
        pdf_files = glob.glob(documents_path)
        if not pdf_files:
            return jsonify({
                "error": "No PDF files found in documents directory"
            }), 400
            
        print(f"[{datetime.now()}] Found {len(pdf_files)} PDF files")
        
        # Process each file
        for file_path in pdf_files:
            # Extract city name from filename (first word before underscore)
            city_name = os.path.basename(file_path).split('_')[0]
            docset_name = f"Hamlet - {city_name}"
            
            print(f"\n[{datetime.now()}] Processing {file_path}")
            print(f"[{datetime.now()}] Looking for docset: {docset_name}")
            
            # Check if docset exists
            existing_docsets = myClient.list_docsets(name_eq=docset_name).get_all()
            print(f"[{datetime.now()}] Found {len(existing_docsets)} existing docsets")
            
            if existing_docsets:
                docset = existing_docsets[0]
                docset_id = docset.docset_id
                print(f"[{datetime.now()}] Using existing docset with ID: {docset_id}")
            else:
                # Create new docset
                docset = myClient.create_docset(name=docset_name)
                docset_id = docset.value.docset_id  # Access the value property to get DocSetMetadata
                print(f"[{datetime.now()}] Created new docset: {docset_name} with ID: {docset_id}")
            
            # Always ensure city record exists in Supabase with current docset_id
            upsert_city_to_supabase(supabase, city_name, docset_id)
            
            # Check if docset already has documents
            docs = list(myClient.list_docs(docset_id=docset_id))
            print(f"[{datetime.now()}] Found {len(docs)} documents in docset {docset_id}")
            if len(docs) > 0:
                print(f"[{datetime.now()}] Skipping {file_path} - docset {docset_name} already has documents")
                continue
            
            # Upload document
            result = upload_document_to_aryn(myClient, file_path, docset_id)
            print(f"[{datetime.now()}] Uploaded {file_path} to docset {docset_name}")
            
        return jsonify({
            "status": "success",
            "message": "Document processing completed"
        })
        
    except Exception as e:
        print(f"[{datetime.now()}] Error processing documents: {str(e)}")
        return jsonify({
            "error": f"Failed to process documents: {str(e)}"
        }), 500

if __name__ == '__main__':
    # Start the Flask app on port 8080
    app.run(debug=True, host='0.0.0.0', port=8080)
