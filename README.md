# Python Service API

A Flask-based service that provides a search API endpoint integrating with Aryn's SDK for document search. The service handles search queries through either test mode or live API calls, storing results and messages in Supabase for session management.

## Overview

This service provides a `/api/search` endpoint that:

- Processes search queries against specified document sets
- Integrates with Aryn's SDK for document search
- Stores results in Supabase for session management
- Supports both test and live modes

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Unix/macOS
# or
.\venv\Scripts\activate  # On Windows
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:

```
TEST_MODE=true/false
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
ARYN_API_TOKEN=your_aryn_token
```

## Running the Service

Start the Flask server:

```bash
python app.py
```

The server will run on port 8080 by default.

## Testing

You can test the search endpoint locally with the following curl command:

```bash
curl -X POST "http://127.0.0.1:8080/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "docset_id": "aryn:ds-kfdt2c1d6blm1z1jh5mh0b4",
    "query": "What are the city'\''s upcoming infrastructure projects?",
    "session_id": 2
  }'
```

Notes:

- Ensure the Flask server is running on port 8080
- Update the `session_id` as needed for your test
- The endpoint returns a JSON response with the query result

## Development

To deactivate the virtual environment when done:

```bash
deactivate
```
