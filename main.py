import os
from prometheus_client import start_http_server, Gauge, Info
import paramiko
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
    ports = os.getenv('PORT', '22').split(',') if ',' in os.getenv('PORT', '22') else [os.getenv('PORT', '22')]
    users = os.getenv('USER', '').split(',') if ',' in os.getenv('USER', '') else [os.getenv('USER')]
    passwords = os.getenv('PASSWORD', '').split(',') if ',' in os.getenv('PASSWORD', '') else [os.getenv('PASSWORD')]
    
    # Clean up any whitespace
    config['hostnames'] = [h.strip() for h in hostnames if h.strip()]
    config['ports'] = [int(p.strip()) for p in ports if p.strip()]
    config['users'] = [u.strip() for u in users if u.strip()]
    config['passwords'] = [p.strip() for p in passwords if p.strip()]
    config['webserver_port'] = int(os.getenv('WEBSERVER_PORT', '8114'))
    
    # Validation
    if not config['hostnames'] or not config['hostnames'][0]:
        raise ValueError("HOSTNAME environment variable is required")
    if not config['users'] or not config['users'][0]:
        raise ValueError("USER environment variable is required")
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
logger.info(f"Configuration loaded: {config}")
logger.info(f"Loaded configuration for {len(config['hostnames'])} device(s)")

# Metric Definitions
temperature_gauge = Gauge('gpon_temperature_celsius', 'Temperature of the GPON device in Celsius', ['ip'])
voltage_gauge = Gauge('gpon_voltage_volts', 'Voltage of the GPON device in Volts', ['ip'])
tx_power_gauge = Gauge('gpon_tx_power_dbm', 'Tx Power of the GPON device in dBm', ['ip'])
rx_power_gauge = Gauge('gpon_rx_power_dbm', 'Rx Power of the GPON device in dBm', ['ip'])
bias_current_gauge = Gauge('gpon_bias_current_mA', 'Bias Current of the GPON device in mA', ['ip'])
onu_state_gauge = Gauge('gpon_onu_state', 'ONU State of the GPON device', ['ip'])
onu_id_gauge = Gauge('gpon_onu_id', 'ONU ID of the GPON device', ['ip'])
loid_status_gauge = Gauge('gpon_loid_status', 'LOID Status of the GPON device', ['ip'])

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

## SSH client
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def fetch_and_update_metrics_via_ssh(hostname, port, username, password):
    try:
        logger.info(f"Connecting to {hostname}:{port}")
        
        # Create SSH client using the transport
        client.connect(
            hostname,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            disabled_algorithms={
                # remove lines if not strictly needed
                # 'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512'],
                'kex': [],
                'keys': [],
                'ciphers': [],
                'macs': []
            }
        )

        commands = {
            'diag pon get transceiver bias-current': bias_current_gauge,
            'diag pon get transceiver rx-power': rx_power_gauge,
            'diag pon get transceiver temperature': temperature_gauge,
            'diag pon get transceiver tx-power': tx_power_gauge,
            'diag pon get transceiver voltage': voltage_gauge,
            'diag gpon get onu-state': onu_state_gauge,
            'omcicli get onuid': onu_id_gauge,
            'omcicli get state': loid_status_gauge,
        }

        for command, gauge in commands.items():
            try:
                stdin, stdout, stderr = client.exec_command(command, timeout=10)
                result = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                
                stdin.close()
                stdout.close()
                stderr.close()
                
                if error:
                    logger.warning(f"Command '{command}' on {hostname} produced error: {error}")

                if command in ['diag pon get transceiver rx-power', 'diag pon get transceiver tx-power']:
                    value = re.search(r'(-?\d+\.\d+)', result)
                    if value:
                        gauge.labels(ip=hostname).set(float(value.group(0)))
                        logger.debug(f"{command} on {hostname}: {value.group(0)}")
                elif command.startswith('diag gpon get onu-state'):
                    state_code = re.search(r'ONU state: (.*)', result)
                    if state_code:
                        gauge.labels(ip=hostname).set(onu_state_mapping.get(state_code.group(1), 0))
                        logger.debug(f"{command} on {hostname}: {state_code.group(1)}")
                elif command.startswith('omcicli get state'):
                    status_code = re.search(r'LOID Status: (.*)', result)
                    if status_code:
                        gauge.labels(ip=hostname).set(loid_status_mapping.get(status_code.group(1), 0))
                        logger.debug(f"{command} on {hostname}: {status_code.group(1)}")
                else:
                    value = re.search(r'(\d+\.\d+)', result)
                    if value:
                        gauge.labels(ip=hostname).set(float(value.group(0)))
                        logger.debug(f"{command} on {hostname}: {value.group(0)}")

            except Exception as e:
                logger.error(f"Error executing command '{command}' on {hostname}: {e}")

        client.close()
        logger.info(f"Successfully updated metrics for {hostname}")
    except Exception as e:
        logger.error(f"Failed to connect to {hostname}:{port} - {e}")
        # Set all metrics to -1 to indicate connection failure
        for gauge in [temperature_gauge, voltage_gauge, tx_power_gauge, rx_power_gauge, 
                     bias_current_gauge, onu_state_gauge, onu_id_gauge, loid_status_gauge]:
            gauge.labels(ip=hostname).set(-1)

def main():
    logger.info(f"Starting GPON Metrics Collector on port {config['webserver_port']}")
    start_http_server(config['webserver_port'])
    logger.info(f"Prometheus metrics server started on port {config['webserver_port']}")
    
    while True:
        try:
            for i in range(len(config['hostnames'])):
                fetch_and_update_metrics_via_ssh(
                    config['hostnames'][i], 
                    config['ports'][i], 
                    config['users'][i], 
                    config['passwords'][i]
                )
            logger.info("Completed metrics collection cycle, sleeping for 300 seconds")
            time.sleep(300)  # Fetch every 5 minutes
        except KeyboardInterrupt:
            logger.info("Received shutdown signal, exiting...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main()