# Prometheus Exporter for Realtek RTL960x

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://python.org)
[![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=Prometheus&logoColor=white)](https://prometheus.io/)

A Prometheus metrics collector for Realtek RTL960x based xPON ONU devices that runs in Docker.

## Features

- 🔌 Collects metrics from GPON Sticks via SSH
- 🏗️ Supports multiple sticks
- 🐳 Runs in Docker container
- 🏥 Health checks included

## Installation

### Prerequisites

- Docker and Docker Compose
- Access to GPON Stick device(s) via SSH

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ChokunPlayZ/rtl960x-prometheus-exporter.git
   cd rtl960x-prometheus-exporter
   ```

2. **Copy the environment template:**
   ```bash
   cp env.example .env
   ```

3. **Edit `.env` with your device details:**
   ```bash
   # Single device (SSH)
   HOSTNAME=192.168.4.1
   PORT=22
   USER=admin
   PASSWORD=admin
   WEBSERVER_PORT=8114
   ```

4. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

5. **Access metrics:** http://localhost:8114/metrics

## Configuration

### Environment Variables

- `HOSTNAME`: Device hostname/IP (required)
- `PORT`: SSH port (default: 22)
- `USER`: SSH username (required)
- `PASSWORD`: SSH password (required)
- `WEBSERVER_PORT`: Prometheus metrics port (default: 8114)

### Multiple Devices

For multiple devices, use comma-separated values:

```bash
HOSTNAME=192.168.1.1,192.168.2.1,192.168.3.1
PORT=22,22,22
USER=admin,admin,admin
PASSWORD=admin,admin,admin
```

Or use single values that will be applied to all devices:

```bash
HOSTNAME=192.168.1.1,192.168.2.1,192.168.3.1
PORT=22
USER=admin
PASSWORD=admin
```

## Metrics Collected

- `gpon_temperature_celsius`: Device temperature
- `gpon_voltage_volts`: Device voltage
- `gpon_tx_power_dbm`: Transmit power
- `gpon_rx_power_dbm`: Receive power
- `gpon_bias_current_mA`: Bias current
- `gpon_onu_state`: ONU state
- `gpon_onu_id`: ONU ID
- `gpon_loid_status`: LOID status

All metrics include an `ip` label with the device hostname/IP.

## Commands

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down

# Rebuild after changes
docker-compose up --build -d

# Check health
docker-compose ps
```

## Troubleshooting

- Verify connectivity to GPON Stick(s) via SSH
- Ensure SSH credentials are correct
- Check firewall settings for both SSH (port 22) and metrics ports
- Test connection manually with legacy algorithms: `ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oCiphers=+3des-cbc -oHostKeyAlgorithms=+ssh-rsa admin@<hostname>`
- Use the included `test.py` script to debug connections

## Testing Connection

You can test the SSH connection manually:

```bash
# Test connection with legacy algorithms
ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oCiphers=+3des-cbc -oHostKeyAlgorithms=+ssh-rsa admin@192.168.4.1

# Or use the included test script
python test.py
```

## Contribution

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a new branch: `git checkout -b feature/YourFeature`
3. Make your changes
4. Commit your changes: `git commit -m 'Add new feature'`
5. Push to the branch: `git push origin feature/YourFeature`
6. Create a pull request

Please ensure your code follows the existing style and includes appropriate tests.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for GPON device monitoring
- Uses Prometheus for metrics collection
- Docker containerized for easy deployment

## Support

If you encounter any issues or have questions:

1. Check the [Issues](../../issues) page
2. Review the troubleshooting section above
3. Create a new issue with detailed information

## Changelog

### v1.0.0
- Initial release
- Docker containerization
- Multi-device support
- Prometheus metrics export
