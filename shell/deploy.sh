#!/bin/bash

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use v20.11.0
export PATH="$PATH:$HOME/.yarn/bin"

# Step 1: Enable VirtualENV
echo "Enable VirtualENV"
source env/bin/activate
if [ $? -ne 0 ]; then
    echo "VirtualENV Enable failed. Exiting."
    exit 1
fi
echo "VirtualENV Enabled"

# Step 2: Run Git Pull Request
echo "Running Git Pull Request"
git stash
git pull
if [ $? -ne 0 ]; then
    echo "Run Git Pull Request failed. Exiting."
    exit 1
fi
echo "Run Git Pull Request Successfully"

# Step 3: Run requirements dev setup
echo "Setting up Requirements --DEV"
bench setup requirements --dev
if [ $? -ne 0 ]; then
    echo "Requirements --DEV Setup failed. Exiting."
    exit 1
fi
echo "Requirements --DEV Setup completed successfully."

# Step 4: Run requirements python setup
echo "Setting up Requirements --PYTHON"
bench setup requirements --python
if [ $? -ne 0 ]; then
    echo "Requirements --PYTHON Setup failed. Exiting."
    exit 1
fi
echo "Requirements --PYTHON Setup completed successfully."

# Step 5: Run requirements node setup
echo "Setting up Requirements --NODE"
bench setup requirements --node
if [ $? -ne 0 ]; then
    echo "Requirements --NODE Setup failed. Exiting."
    exit 1
fi
echo "Requirements --NODE Setup completed successfully."

# Step 8: Run Bench Build
echo "Running Bench Build"
bench build
if [ $? -ne 0 ]; then
    echo "Bench Build failed. Exiting."
    exit 1
fi
echo "Bench Build completed successfully."

# Step 9: Clear Cache
echo "Clearing Cache"
bench clear-cache
if [ $? -ne 0 ]; then
    echo "Clearing Cache failed. Exiting."
    exit 1
fi
echo "Cache cleared successfully."

# Step 10: Clear Website Cache
echo "Clearing Website Cache"
bench clear-website-cache
if [ $? -ne 0 ]; then
    echo "Clearing Website Cache failed. Exiting."
    exit 1
fi
echo "Website Cache cleared successfully."

# Step 11: Restart Bench
echo "Restarting Bench"
bench restart
if [ $? -ne 0 ]; then
    echo "Bench Restart failed. Exiting."
    exit 1
fi
echo "Bench restarted successfully."