#!/bin/bash

# Script to manually install mkcert CA certificate
echo "Installing mkcert CA certificate..."

CA_ROOT=$(mkcert -CAROOT)
CA_CERT="$CA_ROOT/rootCA.pem"

if [ ! -f "$CA_CERT" ]; then
    echo "Error: CA certificate not found at $CA_CERT"
    exit 1
fi

echo "CA certificate found at: $CA_CERT"
echo ""
echo "To install the CA certificate manually, run:"
echo "sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain \"$CA_CERT\""
echo ""
echo "Or you can double-click the certificate file to install it through Keychain Access:"
echo "open \"$CA_CERT\""

# Try to open the certificate for manual installation
open "$CA_CERT"