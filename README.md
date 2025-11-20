# 🌹 rosetrap: The Asynchronous Variable Data Hub

[![PyPI Version](https://img.shields.io/pypi/v/rosetrap.svg)](https://pypi.org/project/rosetrap/)
[![License](https://img.shields.io/github/license/tackyrose763/rosetrap.svg)](https://github.com/tackyrose763/rosetrap/blob/main/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**`rosetrap`** provides an efficient, non-polling mechanism for inter-process communication (IPC) and variable synchronization across Python scripts, leveraging **FastAPI** on the server and the **`requests`** library on the client.

It implements a robust, event-driven pattern that allows a consuming process to **block indefinitely without consuming CPU cycles** until a producing process updates the required variable.

-----

## ✨ Key Features

  * **Asynchronous Blocking:** Uses `asyncio.Event` on the FastAPI server to suspend client requests, eliminating busy-waiting and high CPU load typically associated with polling.
  * **Zero-Config IPC:** No need for complex message queues (Redis, Kafka); state is managed centrally by the lightweight `DATA_HUB`.
  * **Deadlock Prevention:** Robust client logic handles race conditions where data arrives between the initial status check and the blocking request.
  * **Simple API:** Client-side functions are reduced to two clear commands: `printToServer()` (Write) and `receiveFromServer()` (Read/Block).
  * **Independent Variables:** State management is fully independent for each variable name, allowing concurrent, synchronized access by multiple clients.

-----

## 🛠️ Installation & Setup

1.  **Install dependencies:**

    ```bash
    pip install fastapi requests pydantic uvicorn
    ```

2.  **Start the Server:** The `server_data_hub.py` script must be running first.

    ```bash
    python server_data_hub.py
    # Server runs on http://0.0.0.0:8000
    ```

-----

## 🚀 Usage Example: Concurrent Hand-off

This example demonstrates how **Client A** blocks waiting for **Client C**'s data, and then how **Client B** blocks waiting for **Client A**'s computed result, all without polling.

### 1\. The Server and Core Utilities

Ensure `server_data_hub.py` and `core_utils.py` are in your project directory.

### 2\. Client Scripts

Create these three files in the same directory:

#### `client_A.py` (Consumer of X, Producer of Y)

```python
import time
from core_utils import receiveFromServer, printToServer, set_client_id

set_client_id("CLIENT A")

# 1. Block until 'X_Data' is ready
print("CLIENT A: Waiting to receive X_Data...")
x_data = receiveFromServer("X_Data", timeout_seconds=60)

if x_data:
    print(f"CLIENT A: Successfully received X_Data: {x_data}")
    
    # 2. Compute a new value 'Y_Data'
    time.sleep(1) # Simulate computation time
    y_data = str(int(x_data) * 2)
    print(f"CLIENT A: Calculated Y_Data = X_Data * 2 = {y_data}")

    # 3. Send the new value 'Y_Data'
    print("CLIENT A: Sending Y_Data...")
    printToServer("Y_Data", y_data)
    print("CLIENT A: Finished sending Y_Data.")
else:
    print("CLIENT A: Failed to receive X_Data.")
```

#### `client_B.py` (Final Consumer of Y)

```python
from core_utils import receiveFromServer, set_client_id

set_client_id("CLIENT B")

# 1. Block until 'Y_Data' is ready
print("CLIENT B: Waiting to receive Y_Data...")
y_data = receiveFromServer("Y_Data", timeout_seconds=60)

if y_data:
    print(f"CLIENT B: Successfully received Y_Data: {y_data}")
    print("CLIENT B: Final result received. Execution complete.")
else:
    print("CLIENT B: Failed to receive Y_Data. Timeout or error occurred.")
```

#### `client_C.py` (Initial Producer of X)

```python
import time
from core_utils import printToServer, set_client_id

set_client_id("CLIENT C")

# 1. Compute the initial value
initial_value = 50
time.sleep(4) # Simulate initial computation delay

# 2. Send the value 'X_Data'
print(f"CLIENT C: Computation finished. Sending X_Data: {initial_value}")
printToServer("X_Data", initial_value)
print("CLIENT C: Finished sending X_Data.")
```

### 3\. Execution Sequence

The terminal output will clearly show the blocking and release mechanism.

1.  **Start Blocking Clients:**

    ```bash
    python client_A.py &
    python client_B.py &
    ```

    *Client A and B will print their "Waiting" messages and then immediately stop consuming CPU, as they are blocked on the server's `asyncio.Event.wait()`.*

2.  **Trigger the Chain:**

    ```bash
    python client_C.py
    ```

### Expected Flow:

1.  **Client C** sends "50" for `X_Data` after a 4-second delay.
2.  The **Server** sees the `X_Data` lookout is **True** (set by Client A) and signals the event.
3.  **Client A** unblocks, receives "50", computes the result (100), and sends "100" for `Y_Data`.
4.  The **Server** sees the `Y_Data` lookout is **True** (set by Client B) and signals the event.
5.  **Client B** unblocks, receives "100", and finishes.
