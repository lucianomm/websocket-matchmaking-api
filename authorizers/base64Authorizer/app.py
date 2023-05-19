import base64
import os

def lambda_handler(event, context):
    method_arn = event["methodArn"]
    encoded_auth = event["authorizationToken"]
    encoded_auth = encoded_auth.replace("Basic ","")

    (request_client_id, request_client_secret) = base64.b64decode(encoded_auth).decode('utf-8').split(":")

    if request_client_id != os.environ["CLIENT_ID"] or request_client_secret != os.environ["CLIENT_SECRET"]:
        return generate_policy(None, "Deny")

    if request_client_id == os.environ["CLIENT_ID"] and request_client_secret == os.environ["CLIENT_SECRET"]:
        return generate_policy(os.environ["CLIENT_ID"], "Allow")

    return


def generate_policy(principal_id, effect):
    auth_response = {'principalId': principal_id}
    if effect:
        policy_document = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': "*"
                }
            ]
        };
        auth_response['policyDocument'] = policy_document;
    return auth_response