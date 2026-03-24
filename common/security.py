import hashlib
import ipaddress
import socket
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


TLS_DIR_NAME = "tls"
CERT_FILE_NAME = "server.crt"
KEY_FILE_NAME = "server.key"


def _build_san_entries():
    entries = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname())]
    try:
        entries.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
        entries.append(x509.IPAddress(ipaddress.ip_address("::1")))
    except ValueError:
        pass
    return entries


def ensure_server_certificate(data_dir):
    tls_dir = Path(data_dir) / TLS_DIR_NAME
    tls_dir.mkdir(parents=True, exist_ok=True)
    cert_path = tls_dir / CERT_FILE_NAME
    key_path = tls_dir / KEY_FILE_NAME
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TCPTransGUI"),
            x509.NameAttribute(NameOID.COMMON_NAME,
                               "TCPTransGUI Secure Server"),
        ]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(_build_san_entries()), critical=False)
        .sign(private_key, hashes.SHA256())
    )

    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def create_server_ssl_context(data_dir):
    cert_path, key_path = ensure_server_certificate(data_dir)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


def create_client_ssl_context():
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def certificate_fingerprint_from_der(cert_bytes):
    digest = hashlib.sha256(cert_bytes).hexdigest().upper()
    return ":".join(digest[index:index + 2] for index in range(0, len(digest), 2))


def peer_certificate_fingerprint(sock):
    cert_bytes = sock.getpeercert(binary_form=True)
    if not cert_bytes:
        raise RuntimeError("TLS certificate is missing.")
    return certificate_fingerprint_from_der(cert_bytes)
