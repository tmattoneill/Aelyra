#/usr/bin/bash

echo "Cleaning up old files..."
rm package-lock.json
rm -rf node_modules

echo "Rebuilding packages"
npm install

npm run
