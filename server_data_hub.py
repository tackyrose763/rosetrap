from fastapi import FastAPI
from asyncio import Event
import uvicorn
from pydantic import BaseModel 
import logging
from typing import Dict, Any

# --- LOGGING SETUP ---
LOG_FILENAME = "LOG_SERVER.txt"
log_formatter = logging.Formatter('%(asctime)s | SERVER | %(levelname)s | %(message)s')
file_handler = logging.FileHandler(LOG_FILENAME, mode='w')
file_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers = [file_handler, logging.StreamHandler()]
logger.info("SERVER INIT: Logging started. Resetting handlers for fresh run.")

# --- FASTAPI & STATE ---\
app = FastAPI()

# Generalized Request Models - now include the variable name
class MessageRequest(BaseModel):
    variable_name: str
    message: str 

class UpdateRequest(BaseModel):
    variable_name: str
    new_value: str

# Centralized data store and event manager
# Key: variable_name (str)
# Value: { 'value': Any, 'lookout': bool, 'event': Event, 'response_message': str }
DATA_HUB: Dict[str, Dict[str, Any]] = {}

def get_variable_state(var_name: str):
    """Initializes a variable's state if it doesn't exist and returns it."""
    if var_name not in DATA_HUB:
        DATA_HUB[var_name] = {
            'value': None,
            'lookout': False,
            'event': Event(),
            'response_message': ""
        }
        logger.info(f"LOGIC: Initialized state for variable '{var_name}'.")
    return DATA_HUB[var_name]

# -------------------------------------------------------------------
# STAGE 1: Initial Request and Decision (/request_data)
# -------------------------------------------------------------------

@app.post("/request_data")
async def request_data(request: MessageRequest):
    var_name = request.variable_name
    state = get_variable_state(var_name)
    logger.info(f"FUNC: Entered /request_data for '{var_name}'.")
    
    if state['value'] is not None:
        logger.info(f"LOGIC: Value for '{var_name}' is available. Returning immediately.")
        # Machine-friendly reply: Status READY with the value
        return {"status": "READY", "value": state['value']}
    else:
        logger.info(f"LOGIC: Value for '{var_name}' is None. Asking client to set lookout.")
        # Machine-friendly reply: Status PENDING
        return {"status": "PENDING"}

# -------------------------------------------------------------------
# STAGE 2: Lookout and Acknowledge
# -------------------------------------------------------------------

@app.post("/set_lookout")
async def set_lookout(request: MessageRequest):
    var_name = request.variable_name
    state = get_variable_state(var_name)
    logger.info(f"FUNC: Entered /set_lookout for '{var_name}'.")

    # Deadlock Prevention Check: Has the data arrived between /request_data and /set_lookout?
    if state['value'] is not None:
        logger.info(f"LOGIC: '{var_name}' already found while setting lookout. No block needed.")
        # Machine-friendly reply: Status READY, value is present
        return {"status": "READY", "value": state['value']}
        
    state['lookout'] = True
    state['event'].clear() # Ensure the event is clear before waiting
    logger.info(f"LOGIC: Lookout set to {state['lookout']} for '{var_name}'. Blocking client.")
    
    try:
        await state['event'].wait()
        
        # When awakened: return the stored value directly
        logger.info(f"LOGIC: Woke up for '{var_name}'. Returning value: '{state['value']}'")
        # Machine-friendly reply: Status RECEIVED, value is present
        return {"status": "RECEIVED", "value": state['value']}
    except Exception as e:
        logger.error(f"ERROR: Exception during blocking wait for '{var_name}': {e}")
        return {"status": "ERROR", "message": f"Blocking wait failed for {var_name}"}

@app.post("/acknowledge")
async def acknowledge(request: MessageRequest):
    var_name = request.variable_name
    state = get_variable_state(var_name)
    logger.info(f"FUNC: Entered /acknowledge for '{var_name}'.")

    state['lookout'] = False
    state['event'].clear()
    state['response_message'] = ""
    logger.info(f"LOGIC: Client acknowledged '{var_name}'. Lookout set to {state['lookout']}. Event cleared.")
    return {"status": "OK"}

# -------------------------------------------------------------------
# STAGE 3: Data Update (/update_variable)
# -------------------------------------------------------------------

@app.post("/update_variable")
def update_variable(request: UpdateRequest):
    var_name = request.variable_name
    new_value = request.new_value
    state = get_variable_state(var_name)
    logger.info(f"FUNC: Entered /update_variable for '{var_name}'.")
    
    # 1. Update the value
    state['value'] = new_value
    logger.info(f"LOGIC: Value for '{var_name}' updated to '{new_value}'.")
    
    # 2. Check for waiting clients
    if state['lookout']:
        logger.info(f"LOGIC: LOOKOUT ON for '{var_name}'. Signalling client.")
        state['event'].set()
        logger.info(f"LOGIC: Signaled waiting client for '{var_name}' to wake up.")
        return {"status": "OK", "message": f"Update complete. Client waiting for {var_name} notified."}
    else:
        logger.info(f"LOGIC: No client was waiting for '{var_name}'.")
        return {"status": "OK", "message": "Update complete. No client was waiting."}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")