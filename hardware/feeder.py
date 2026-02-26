# Used to send HTTP requests to the ESP32 device
import requests        
import logging      
from config import ESP32_IP   


def trigger_feeder():
    """
    Sends an HTTP request to the ESP32 to trigger the feeder (open the box).
    This function is called when a new possum visit is detected.
    """
    try:
        # Send GET request to the ESP32 '/open' endpoint with a 3-second timeout
        response = requests.get(f"http://{ESP32_IP}/open", timeout=3)

        # Log successful trigger with response text returned by ESP32 

        if response.text == "BOX_OPENED":
            logging.info("Feeder confirmed: BOX_OPENED")
        else:
            logging.warning(f"Unexpected feeder response: {response.text}")

    except Exception as e:
        # Log error if the request fails 
        logging.error(f"Feeder trigger failed: {e}")
