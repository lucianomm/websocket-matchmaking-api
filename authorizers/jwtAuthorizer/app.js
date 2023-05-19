const JwtRsaVerifier = require('aws-jwt-verify');

const verifier = JwtRsaVerifier.JwtRsaVerifier.create({
  issuer: process.env.ISSUER, // set this to the expected "iss" claim on your JWTs
  audience: process.env.AUDIENCE, // set this to the expected "aud" claim on your JWTs
  jwksUri: process.env.JWKS_URI, // set this to the JWKS uri from your OpenID configuration
});

exports.handler = async function(event, context, callback) {
  var token = event.authorizationToken;
  if(!token){
    token = event.headers.Authorization;
  }
  token = token.replace("Bearer ","");
  console.log(token);
  try {
    const payload = await verifier.verify(token);
    console.log("Token is valid. Payload:", payload);
    return generate_policy(payload.sub, 'Allow');
  } catch (e){
    console.log(e);
    console.log("Token not valid!");
    return generate_policy(null, 'Deny');
  }
}

const generate_policy = function(principal_id, effect){
  var auth_response = {'principalId': principal_id};
    if (effect){
      var policy_document = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': '*'
                }
            ]
        };
        auth_response['policyDocument'] = policy_document;
    }
    return auth_response
}