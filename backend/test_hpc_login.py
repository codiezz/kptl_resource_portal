import paramiko
import logging

# Enable Paramiko debug logs
logging.basicConfig(level=logging.DEBUG)

HOST = "192.168.1.152"
PORT = 22
USERNAME = "test"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(
        hostname=HOST,
        port=PORT,
        username=USERNAME,
        password=None,
        allow_agent=False,
        look_for_keys=False,
        timeout=10
    )

    print("CONNECTED!")

except Exception as e:
    print("ERROR:")
    print(type(e).__name__)
    print(e)
