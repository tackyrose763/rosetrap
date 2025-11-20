import requests
import logging
import sys
from typing import Any, Optional

# --- LOGGING SETUP ---
LOG_FILENAME = "LOG_CORE_UTILS.txt"
logger = logging.getLogger("core_utils")
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILENAME, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s | UTIL | %(levelname)s | %(message)s'))
    logger.addHandler(file_handler)

SERVER_URL = "http://127.0.0.1:8000"
CLIENT_ID = "Unknown"

def set_client_id(client_name):
    global CLIENT_ID
    sys.stdout.write(f"\n--- Setting Client ID to {client_name} ---\n")
    CLIENT_ID = client_name

def api_call(method, endpoint, json_data=None, request_timeout=5):
    url = f"{SERVER_URL}/{endpoint}"
    logger.info(f"CALL START ({CLIENT_ID}) -> {method} {url}. Payload: {json_data}. Timeout: {request_timeout}s")
    
    try:
        response = requests.request(method, url, json=json_data, timeout=request_timeout)
        if response.status_code == 200:
            try:
                response_json = response.json()
                logger.info(f"CALL END ({CLIENT_ID}) -> Status: 200. Response JSON: {response_json}")
                return response_json
            except requests.exceptions.JSONDecodeError:
                logger.error(f"CALL ERROR ({CLIENT_ID}): Failed to decode JSON. Status: {response.status_code}. Response text: {response.text}")
                return None
        else:
            logger.error(f"CALL ERROR ({CLIENT_ID}): API call failed. Status: {response.status_code}. Response text: {response.text}")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"CALL ERROR ({CLIENT_ID}): Request timed out after {request_timeout} seconds to {url}.")
        return None
    except Exception as e:
        logger.exception(f"CALL ERROR ({CLIENT_ID}): An unexpected error occurred.")
        return None

# --- PUBLIC COMMUNICATION FUNCTIONS (OLD IMPLEMENTATION - NOW GENERALIZED) ---

def request_data_status(var_name: str, timeout_seconds: int = 5):
    msg = f"STATUS CHECK FOR {var_name}" 
    return api_call("POST", "request_data", {"variable_name": var_name, "message": msg}, request_timeout=timeout_seconds)

def start_blocking_wait(var_name: str, timeout_seconds: int):
    msg = f"INITIATING BLOCKING WAIT FOR {var_name}"
    return api_call("POST", "set_lookout", {"variable_name": var_name, "message": msg}, request_timeout=timeout_seconds)

def acknowledge_data(var_name: str, timeout_seconds: int = 5):
    msg = f"ACKNOWLEDGE {var_name} RECEIVED"
    return api_call("POST", "acknowledge", {"variable_name": var_name, "message": msg}, request_timeout=timeout_seconds)

def update_variable_x(var_name: str, new_value: str, timeout_seconds: int = 5):
    return api_call("POST", "update_variable", {"variable_name": var_name, "new_value": new_value}, request_timeout=timeout_seconds)


# --- NEW, SIMPLIFIED API FOR CODING ---

def printToServer(var_name: str, var_value: Any, timeout_seconds: int = 5):
    return update_variable_x(var_name, str(var_value), timeout_seconds)


def receiveFromServer(var_name: str, timeout_seconds: int = 30) -> Optional[str]:
    # Step 1: Check if data is already there (request_data_status)
    initial_response = request_data_status(var_name, timeout_seconds=5)
    
    if not initial_response:
        logger.error(f"receiveFromServer failed at initial status check for '{var_name}'.")
        return None

    status = initial_response.get('status')
    
    if status == "READY":
        # Data found immediately
        value = initial_response.get('value')
        logger.info(f"receiveFromServer: Data for '{var_name}' already present: '{value}'")
        return value
    
    if status != "PENDING":
        logger.error(f"receiveFromServer failed: Unexpected initial status: {status}")
        return None
    
    # Status is PENDING.
    # Step 2: Initiate blocking wait
    logger.info(f"receiveFromServer: Data for '{var_name}' not found. Initiating blocking wait (Timeout: {timeout_seconds}s).")
    
    wait_response = start_blocking_wait(var_name, timeout_seconds=timeout_seconds)
    
    if not wait_response:
        logger.error(f"receiveFromServer failed: Blocking wait for '{var_name}' timed out or failed.")
        return None

    # Step 3: Woke up, check status and extract value
    final_status = wait_response.get('status')
    value = wait_response.get('value')
    
    if final_status in ["READY", "RECEIVED"] and value is not None:
        # READY: Deadlock prevention hit (data arrived between steps 1 & 2)
        # RECEIVED: Data arrived while blocked (standard case)
        logger.info(f"receiveFromServer: Data for '{var_name}' received (Status: {final_status}): '{value}'")

        # Step 4: Send acknowledgement
        acknowledge_data(var_name)
        return value
        
    logger.error(f"receiveFromServer failed: Final server status was '{final_status}'. No valid value received.")
    acknowledge_data(var_name)
    return None