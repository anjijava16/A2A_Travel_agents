#!/usr/bin/env python3
"""
Cloud Map Deregistration Module
Deregisters agent container instance from AWS Cloud Map during graceful shutdown
"""

import json
import os
import sys

import boto3

from lib.logger import get_logger

# Configuration

logger = get_logger()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
INSTANCE_ID_FILE = "/tmp/cloudmap_instance_id.txt"


def deregister_instance():
    """Deregister this container instance from Cloud Map"""

    # Check if instance ID file exists
    if not os.path.exists(INSTANCE_ID_FILE):
        logger.info("No Cloud Map registration found. Nothing to deregister.")
        return True

    try:
        # Read instance registration info
        with open(INSTANCE_ID_FILE) as f:
            registration_info = json.load(f)

        instance_id = registration_info.get("instance_id")
        service_id = registration_info.get("service_id")

        if not instance_id or not service_id:
            logger.warning("Warning: Invalid registration info. Cannot deregister.")
            return False

        logger.info("Deregistering instance from Cloud Map:")
        logger.info(f"  Instance ID: {instance_id}")
        logger.info(f"  Service ID: {service_id}")

        # Create Cloud Map client
        servicediscovery = boto3.client("servicediscovery", region_name=AWS_REGION)

        # Deregister instance
        response = servicediscovery.deregister_instance(
            ServiceId=service_id, InstanceId=instance_id
        )

        operation_id = response.get("OperationId")
        logger.info(f"✓ Deregistration initiated (Operation ID: {operation_id})")

        # Remove instance ID file
        os.remove(INSTANCE_ID_FILE)
        logger.info(f"✓ Cleaned up {INSTANCE_ID_FILE}")

        return True

    except Exception as e:
        logger.error(f"Error deregistering from Cloud Map: {e}")
        return False


if __name__ == "__main__":
    success = deregister_instance()
    sys.exit(0 if success else 1)
