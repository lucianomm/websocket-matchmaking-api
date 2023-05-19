# websocket-matchmaking-api
This repository showcases the architecture of a game matchmaking system, utilizing Amazon API Gateway, AWS Lambda, and WebSockets for real-time communication. It serves as a reference for creating an efficient, serverless matchmaking system

## Disclaimer
Ideally this solution should be separated into two parts, the API logic, and the ECS infrastructure. 
I've kept a single repository in order to have all the information bundled together.
I strongly suggest you separate the two.

# Deploying:
This is the infrastructure as code (IaC) for a matchmaking API written with AWS Serverless Application Model (SAM).
All the resources are described in the api.yaml, userApi.yaml and matchmakingApi.yaml stacks.
Every Lambda function has their own folder with respective code

## Building solution:

Some files need to be shared with a group of functions, those files are specified in the buid.ps1 file
npm packages are also built using the same script

**Run**:

`.\build.sh`

## Uploading/Updating infra:

Configure samconfig.toml with the correct parameter overrides
install aws cli
install sam cli

**First Run**:
Create the repository on aws
Replace the repository name you chose in the parameter `CodeCommitRepositoryName` and `CodeCommitBranchName` on `server-pipeline.yaml`
create the pipeline for infrastructure deployment of the ECS task in each region, the regions can be configured as comma separeted values in the parameter 'DeployRegions'
`sam deploy -t .\server-pipeline.yaml --config-file .\server-pipeline-config.toml --guided`

log into aws and clone the created repository, add the folder ServerImage and the file ecs-cluster.yaml and push the changes. 
The pipeline should take care of publishing the image and creating the tasks definitions for ECS.


`sam deploy -t .\api.yaml --config-file .\samconfig.toml --guided`

**Consecutive Runs**:

`sam deploy -t .\api.yaml --config-file .\samconfig.toml`

**Update Server Image**:

push changes to repository

# User Flow:
The complete matchmaking flow is described in the chart below:
![Alt text](./matchmaking_flow.png?raw=true "Title")

## Enter queue
For users to connect to the queue, they should first connect to the websocket, that can be managed using wscat in linux:
`wscat -c 'wss://matchmaking.dev.playwof.com' -H Authorization:'Bearer <token>'`

If you don't want to use token based authentication, remove it from the project, but be mindfull of adapting that flow and passing at least the user_id in the header for database management. It is not recommended though, as it will give users agency towards what data will be changed when matches are taking place. Use it at your own peril!

After connecting, users should join the matchmaking queue with the following message:
`{"action":"joinQueue","region":"<ecs-enabled-region>"}`

## Match Players

Once connected, there is an action to pair matching players:
`{"action":"tryCreateMatch"}`

This action is an example for the API to try to pair players, your logic can vary, calling the function periodically or whenever there is change in the queue. Note that in this solution, the function has a concurrency limit of 1, so that when matches are being paired, the API waits for the process to end, that is important to guarantee the correct flow, so that players are not paired in multiple matches because of concurrency issues.

If a match is found, the server will alert all users who have been paired with the message:
`MATCH FOUND` 

## Match Found

When a match is found, the server will boot in a container in ecs (**Initialization**), once it is booted, the server will alert the API which will alert the users:
`server created with ip:<ip>`

The users can then connect to that IP and disconnect from the websocket. When a message 'HOME' or 'AWAY' is typed on the server, it will resolve a win for the team typed. To know which player is in which team, type STATUS

When solved, the results should be updated in the table according to the math in glicko_team.py file.