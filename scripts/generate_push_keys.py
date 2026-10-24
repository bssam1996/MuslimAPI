"""Generate VAPID keys once. Keep the private PEM outside source control."""
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

private = ec.generate_private_key(ec.SECP256R1())
target = Path('secrets/vapid.pem')
target.parent.mkdir(parents=True, exist_ok=True)
with target.open('xb') as output:
    output.write(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
target.chmod(0o600)
public = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
public_value = base64.urlsafe_b64encode(public).decode().rstrip('=')
private_value = base64.urlsafe_b64encode(private.private_numbers().private_value.to_bytes(32, 'big')).decode().rstrip('=')
env_target = Path('secrets/vapid.env')
with env_target.open('x', encoding='utf-8') as output:
    output.write(f'VAPID_PUBLIC_KEY={public_value}\nVAPID_PRIVATE_KEY={private_value}\n')
env_target.chmod(0o600)
print('VAPID_PUBLIC_KEY=' + public_value)
print('Private key and deployment variables saved in secrets/. Keep them private and back them up; existing subscribers require these same keys.')
