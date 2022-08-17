## Context

### Why

We need replication of parameters and secrets to our failover regions for disaster recovery purposes.

### How - Event Based

This service watches CloudTrail logs for parameter and secret creation events and will attempt to replicate these
items in real time.

### How - Daily Schedule

Once per day, the script will attempt to sync all parameters & set replication on all secrets. This is a
safety net in case of failure during processing of an individual event.

### What - Secrets Manager

We enable the automatic replication feature AWS provides. This will replicate the secret to the target region, including
all metadata and access policies, etc. It does add steps to the secret deletion process, as the replica must first be
promoted (and/or deleted) before the source secret can be removed. AWS requires a minimum of 7 days to remove a secret. 

### What - SSM Parameter Store

There is no managed replication option for Parameter Store. We perform replication by creating a copy with identical
properties and by appending `ReplicationStatus: monitored-by-parameter-store-replication-lambda` to the existing item's
tags. If an item is removed from the source region, we'll also delete the replicated version.  

## Development & Deployment

See serverless.yml for the lambda infrastructure configuration and [Serverless Framework Documentation](https://www.serverless.com/framework/docs).

The control loop can be found in `handler.py->handle()`. 

### Requirement: SNS Topic

For this stack to notify the team of replication errors, an SNS topic must be created and this lambda must have
permission to Publish to the topic. The recommended pattern here is to create a topic in the management account
(or another workload account which won't be deleted) and to grant Publish to any principal in the Organization. 

### Installing Serverless

`npm i -g serverless` will get you started. 

### AWS Credentials

Serverless works with AWS environment variables and/or `~/.aws/credentials`. 
For SSO use-cases, we can lean on tools like `yawsso` to generate environment variables and credentials profiles.


### Local Development

Modify handler.py and other files as necessary. To run a test, use the following:

`sls invoke local --function handle --path payloads/sync-*.json` (replace * with your desired name). 

This will invoke the lambda in your local environment, feeding it variables from serverless.yml, etc. 

### Deployment

`sls deploy` will package and deploy the current code to AWS, creating resources as needed through CloudFormation.

### Remote Operation

`sls invoke --function handle --path payloads/sync-*.json` will trigger an invocation of the lambda in AWS, providing
the `event` parameter using the chosen .json file. 

### Teardown

`sls remove` will destroy the cloudformation stack and the deployment bucket. If this project is no longer useful,
we should also find and consider removal of the independently-created SNS topic. 