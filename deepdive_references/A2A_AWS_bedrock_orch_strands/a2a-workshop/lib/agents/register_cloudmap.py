#!/usr/bin/env python3
"""
Cloud Map Registration Module
Registers agent container instance with AWS Cloud Map for service discovery
"""

from datetime import UTC, datetime
import json
import os
import socket
import sys

import boto3

from lib.logger import get_logger

# Configuration from environment variables

logger = get_logger()

NAMESPACE_ID = os.getenv("CLOUDMAP_NAMESPACE_ID")
SERVICE_NAME = os.getenv("CLOUDMAP_SERVICE_NAME")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8000"))
AGENT_URL = os.getenv("AGENT_URL")  # ALB URL
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# File to store instance ID for cleanup
INSTANCE_ID_FILE = "/tmp/cloudmap_instance_id.txt"


def get_container_ip():
    """Get the container's IP address"""
    try:
        # Get hostname
        hostname = socket.gethostname()
        # Resolve to IP
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except Exception as e:
        logger.warning(f"Warning: Could not determine container IP: {e}")
        return "127.0.0.1"


def get_service_id(servicediscovery, namespace_id, service_name):
    """Look up Service ID from service name"""
    try:
        response = servicediscovery.list_services(
            Filters=[
                {"Name": "NAMESPACE_ID", "Values": [namespace_id], "Condition": "EQ"}
            ]
        )

        for service in response.get("Services", []):
            if service["Name"] == service_name:
                return service["Id"]

        logger.error(
            f"Error: Service '{service_name}' not found in namespace {namespace_id}"
        )
        return None
    except Exception as e:
        logger.error(f"Error looking up service ID: {e}")
        return None


def register_instance():
    """Register this container instance with Cloud Map"""

    if not NAMESPACE_ID or not SERVICE_NAME:
        logger.error(
            "Error: CLOUDMAP_NAMESPACE_ID and CLOUDMAP_SERVICE_NAME must be set"
        )
        sys.exit(1)

    # Get container IP
    container_ip = get_container_ip()

    # Generate unique instance ID (use container hostname)
    instance_id = socket.gethostname()

    logger.info("Registering instance with Cloud Map:")
    logger.info(f"  Instance ID: {instance_id}")
    logger.info(f"  Namespace ID: {NAMESPACE_ID}")
    logger.info(f"  Service Name: {SERVICE_NAME}")
    logger.info(f"  IP Address: {container_ip}")
    logger.info(f"  Port: {AGENT_PORT}")
    if AGENT_URL:
        logger.info(f"  Agent URL (ALB): {AGENT_URL}")

    try:
        # Create Cloud Map client
        servicediscovery = boto3.client("servicediscovery", region_name=AWS_REGION)

        # Look up service ID from service name
        service_id = get_service_id(servicediscovery, NAMESPACE_ID, SERVICE_NAME)
        if not service_id:
            logger.error("Error: Could not find service ID")
            return False

        logger.info(f"  Service ID: {service_id}")

        # Prepare instance attributes
        attributes = {
            "AWS_INSTANCE_IPV4": container_ip,
            "AWS_INSTANCE_PORT": str(AGENT_PORT),
        }

        # Add ALB URL if available
        if AGENT_URL:
            attributes["AGENT_URL"] = AGENT_URL

        # Register instance
        response = servicediscovery.register_instance(
            ServiceId=service_id, InstanceId=instance_id, Attributes=attributes
        )

        operation_id = response.get("OperationId")
        logger.info(f"✓ Registration initiated (Operation ID: {operation_id})")

        # Save instance ID for cleanup
        with open(INSTANCE_ID_FILE, "w") as f:
            json.dump(
                {
                    "instance_id": instance_id,
                    "service_id": SERVICE_NAME,
                    "namespace_id": NAMESPACE_ID,
                    "registered_at": datetime.now(UTC).isoformat(),
                    "operation_id": operation_id,
                },
                f,
            )

        logger.info(f"✓ Instance ID saved to {INSTANCE_ID_FILE}")
        return True

    except Exception as e:
        logger.error(f"Error registering with Cloud Map: {e}")
        logger.warning(
            "Note: Agent will continue running, but won't be discoverable via Cloud Map"
        )
        return False


if __name__ == "__main__":
    success = register_instance()
    sys.exit(0 if success else 1)
