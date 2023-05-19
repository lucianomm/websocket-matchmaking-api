#!/bin/bash

# -------- COPY REPO FILES --------
echo -e "\n-------- COPY REPO FILES --------\n"

function Copy-RepoFile {
    sourceFile=$1
    destinationRoot=$2
    recursive=$3

    if [ $recursive = true ]; then
        echo "Copying $sourceFile to all subfolders in $destinationRoot"
        for folder in $(find $destinationRoot -mindepth 1 -type d); do
            destination="$folder/$(basename $sourceFile)"
            cp $sourceFile $destination -f
        done
    else
        echo "Copying $sourceFile to $destinationRoot"
        destination="$destinationRoot/$(basename $sourceFile)"
        cp $sourceFile $destination -f
    fi
}

#Copy matchmakingTableRepository from matchmakingApi folder to all WEBSOCKET folders
sourceFile="matchmakingApi/matchmakingTableRepository.py"
destinationRoot="matchmakingApi/WEBSOCKET"
Copy-RepoFile $sourceFile $destinationRoot true

#Copy matchmakingTableRepository from matchmakingApi folder to all HTTP folders
sourceFile="matchmakingApi/matchmakingTableRepository.py"
destinationRoot="matchmakingApi/HTTP"
Copy-RepoFile $sourceFile $destinationRoot true

#Copy glicko_team.py from matchmakingApi folder to all WEBSOCKET folders
sourceFile="matchmakingApi/glicko_team.py"
destinationRoot="matchmakingApi/WEBSOCKET"
Copy-RepoFile $sourceFile $destinationRoot true

#Copy glicko_team.py from matchmakingApi folder to all HTTP folders
sourceFile="matchmakingApi/glicko_team.py"
destinationRoot="matchmakingApi/HTTP"
Copy-RepoFile $sourceFile $destinationRoot true

# -------- UPDATE NPM PACKAGES --------
echo -e "\n-------- UPDATE NPM PACKAGES --------\n"
# Update npm packages
IFS=$'\n'
folders=$(find "$PWD" -not -path '*/node_modules/*' -type f -name 'package.json' -exec dirname {} +)
for folder in $folders; do
    echo "Updating packages in $folder..."
    cd "$folder"
    npm update
    cd -
done