#/usr/bin/bash

echo "Cleaning up old files..."

echo "Deleting package-lock.json"
rm package-lock.json

echo "Removing node modules..."
rm -rf node_modules

echo "Rebuilding packages"
npm install

npm run
