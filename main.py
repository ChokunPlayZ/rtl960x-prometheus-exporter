import os
from prometheus_client import start_http_server, Gauge, Info
import telnetlib
import time
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration from environment variables
def load_config():
    config = {}
    
    # Support multiple devices via comma-separated values or single device
    hostnames = os.getenv('HOSTNAME', '').split(',') if ',' in os.getenv('HOSTNAME', '') else [os.getenv('HOSTNAME')]
    ports = os.getenv('PORT', '23').split(',') if ',' in os.getenv('PORT', '23') else [os.getenv('PORT', '23')]
    users = os.getenv('USERNAME', '').split(',') if ',' in os.getenv('USERNAME', '') else [os.getenv('USERNAME')]
    passwords = os.getenv('PASSWORD', '').split(',') if ',' in os.getenv('PASSWORD', '') else [os.getenv('PASSWORD')]
    delay = os.getenv('DELAY', '10') 
    
    # Clean up any whitespace
    config['hostnames'] = [h.strip() for h in hostnames if h.strip()]
    config['ports'] = [int(p.strip()) for p in ports if p.strip()]
    config['users'] = [u.strip() for u in users if u.strip()]
    config['passwords'] = [p.strip() for p in passwords if p.strip()]
    config['webserver_port'] = int(os.getenv('WEBSERVER_PORT', '8114'))
    config['delay'] = int(delay)
    
    # Validation
    if not config['hostnames'] or not config['hostnames'][0]:
        raise ValueError("HOSTNAME environment variable is required")
    if not config['users'] or not config['users'][0]:
        raise ValueError("USERNAME environment variable is required")
    if not config['passwords'] or not config['passwords'][0]:
        raise ValueError("PASSWORD environment variable is required")
    
    # Ensure all lists have the same length by repeating single values
    max_len = len(config['hostnames'])
    if len(config['ports']) == 1:
        config['ports'] = config['ports'] * max_len
    if len(config['users']) == 1:
        config['users'] = config['users'] * max_len
    if len(config['passwords']) == 1:
        config['passwords'] = config['passwords'] * max_len
    
    if not (len(config['hostnames']) == len(config['ports']) == len(config['users']) == len(config['passwords'])):
        raise ValueError("Mismatch in number of hostnames, ports, users, and passwords")

    return config

# Load configuration
config = load_config()
logger.info(f"Loaded configuration for {len(config['hostnames'])} device(s)")

# Metric Definitions
temperature_gauge = Gauge('gpon_temperature_celsius', 'Temperature of the GPON device in Celsius', ['ip'])
voltage_gauge = Gauge('gpon_voltage_volts', 'Voltage of the GPON device in Volts', ['ip'])
tx_power_gauge = Gauge('gpon_tx_power_dbm', 'Tx Power of the GPON device in dBm', ['ip'])
rx_power_gauge = Gauge('gpon_rx_power_dbm', 'Rx Power of the GPON device in dBm', ['ip'])
bias_current_gauge = Gauge('gpon_bias_current_mA', 'Bias Current of the GPON device in mA', ['ip'])
onu_state_gauge = Gauge('gpon_onu_state', 'ONU State of the GPON device', ['ip'])

# ONU State and LOID Status Mappings
onu_state_mapping = {
    '01': 1,
    '02': 2,        
    '03': 3,
    '04': 4,
    'O5': 5,
    '06': 6,
    '07': 7,    
    # Add more mappings for other states as needed
}

loid_status_mapping = {
    'Initial Status': 0,
    'Loid Error': 1,
    # Add more mappings for other statuses as needed
}

def fetch_and_update_metrics(hostname, port, username, password):
    try:
        logger.debug(f"Connecting to {hostname}:{port}")
        
        tn = telnetlib.Telnet(hostname, port, timeout=10)

        # Wait for login prompt
        response = tn.read_until(b"login: ", timeout=10)
        print(f"Login prompt: {response.decode('ascii', errors='ignore')}")
        
        # Send username
        tn.write(username.encode('ascii') + b"\n")
        
        # Wait for password prompt
        response = tn.read_until(b"Password: ", timeout=10)
        print(f"Password prompt: {response.decode('ascii', errors='ignore')}")
        
        # Send password
        tn.write(password.encode('ascii') + b"\n")
        
        # Wait for shell prompt
        response = tn.read_until(b"# ", timeout=10)
        print(f"Shell prompt: {response.decode('ascii', errors='ignore')}")

        commands = {
            'diag pon get transceiver bias-current': bias_current_gauge,
            'diag pon get transceiver rx-power': rx_power_gauge,
            'diag pon get transceiver temperature': temperature_gauge,
            'diag pon get transceiver tx-power': tx_power_gauge,
            'diag pon get transceiver voltage': voltage_gauge,
            'diag gpon get onu-state': onu_state_gauge
        }

        for command, gauge in commands.items():
            try:
                # Send command with proper byte encoding
                tn.write(f"{command}\n".encode('ascii'))
                response = tn.read_until(b"# ", timeout=10)
                result = response.decode('ascii', errors='ignore')
                logger.debug(f"Command response for '{command}': {result}")
                
                # Check for error indicators in the response
                error_indicators = ['error', 'invalid', 'failed', 'not found', 'permission denied']
                if any(indicator in result.lower() for indicator in error_indicators):
                    logger.warning(f"Command '{command}' on {hostname} produced error response: {result.strip()}")
                    gauge.labels(ip=hostname).set(-1)  # Set error value
                    continue

                # Parse the response based on command type
                value_set = False
                
                if command in ['diag pon get transceiver rx-power', 'diag pon get transceiver tx-power']:
                    value_match = re.search(r'(-?\d+\.\d+)', result)
                    if value_match:
                        try:
                            value = float(value_match.group(0))
                            gauge.labels(ip=hostname).set(value)
                            logger.debug(f"{command} on {hostname}: {value}")
                            value_set = True
                        except ValueError as ve:
                            logger.error(f"Failed to convert value '{value_match.group(0)}' to float for command '{command}' on {hostname}: {ve}")
                            
                elif command.startswith('diag gpon get onu-state'):
                    state_match = re.search(r'ONU state: .*\(([^)]+)\)', result)
                    if state_match:
                        state_code = state_match.group(1).strip()
                        numeric_value = onu_state_mapping.get(state_code, 0)
                        gauge.labels(ip=hostname).set(numeric_value)
                        logger.debug(f"{command} on {hostname}: {state_code} -> {numeric_value}")
                        value_set = True
                    else:
                        logger.warning(f"Could not parse ONU state from response: {result.strip()}")
                        
                else:
                    # For other numeric commands (temperature, voltage, bias-current, onu-id)
                    value_match = re.search(r'(\d+\.?\d*)', result)
                    if value_match:
                        try:
                            value = float(value_match.group(0))
                            gauge.labels(ip=hostname).set(value)
                            logger.debug(f"{command} on {hostname}: {value}")
                            value_set = True
                        except ValueError as ve:
                            logger.error(f"Failed to convert value '{value_match.group(0)}' to float for command '{command}' on {hostname}: {ve}")
                
                # If no value was successfully parsed and set, log a warning and set error value
                if not value_set:
                    logger.warning(f"No valid value found in response for command '{command}' on {hostname}. Response: {result.strip()}")
                    gauge.labels(ip=hostname).set(-1)

            except Exception as e:
                logger.error(f"Error executing command '{command}' on {hostname}: {e}")
                # Set error value for this specific metric
                try:
                    gauge.labels(ip=hostname).set(-1)
                except Exception as gauge_error:
                    logger.error(f"Failed to set error value for gauge on {hostname}: {gauge_error}")        # Exit gracefully
        try:
            tn.write(b"exit\n")
            tn.close()
        except Exception as close_error:
            logger.warning(f"Error while closing telnet connection to {hostname}: {close_error}")
        
        logger.debug(f"Successfully updated metrics for {hostname}")
    except Exception as e:
        logger.error(f"Failed to connect to {hostname}:{port} - {e}")
        # Set all metrics to -1 to indicate connection failure
        try:
            for gauge in [temperature_gauge, voltage_gauge, tx_power_gauge, rx_power_gauge, 
                         bias_current_gauge, onu_state_gauge]:
                gauge.labels(ip=hostname).set(-1)
        except Exception as gauge_error:
            logger.error(f"Failed to set error values for gauges on {hostname}: {gauge_error}")
        
        # Ensure telnet connection is closed even on error
        try:
            if 'tn' in locals():
                tn.close()
        except Exception:
            pass  # Ignore errors when closing after a failure

def main():
    logger.info(f"Starting GPON Metrics Collector on port {config['webserver_port']}")
    start_http_server(config['webserver_port'])
    logger.info(f"Prometheus metrics server started on port {config['webserver_port']}")
    
    while True:
        try:
            for i in range(len(config['hostnames'])):
                fetch_and_update_metrics(
                    config['hostnames'][i], 
                    config['ports'][i], 
                    config['users'][i], 
                    config['passwords'][i]
                )
            logger.debug(f"Completed metrics collection cycle, sleeping for {config['delay']} seconds")
            time.sleep(config['delay'])  # Fetch every x minutes
        except KeyboardInterrupt:
            logger.info("Received shutdown signal, exiting...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(config['delay'])  # Wait a minute before retrying

if __name__ == "__main__":
    main()