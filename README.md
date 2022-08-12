<!--
title: 'Parameter Store Replication'
description: 'This stack will deploy a lambda & cloudtrail listener to watch for updated SSM Parameters and replicate to the target region.'
layout: Doc
framework: v3
platform: AWS
language: python
priority: 2
authorLink: 'https://github.com/serverless'
authorName: 'Serverless, inc.'
authorAvatar: 'https://avatars1.githubusercontent.com/u/13742415?s=200&v=4'
-->

# Context

We want to enable Secret & Parameter replication to a secondary region for DR purposes.
Secrets Manager supports cross-region replication including metadata, so we just need to enable it on all secrets. 
Parameter Store doesn't support replication, so we need to manually sync secrets to the failover region. 

This stack will create two jobs:

- A daily cron which triggers a full sync of parameters (including removing deleted params) and enables replication on all Secrets.
- A Cloudwatch Event listener which watches for parameter updates and replicates those to the failover region. 

## Usage

See [Serverless Framework](https://serverless.com) for additional details & documentation.

Configuration of the infrastructure is stored in serverless.yml.
Function code is stored in *.py files, with the function root in `handler.py`.

### Deployment

In order to deploy the example, you need to run the following command:

```
sls deploy
```

After running deploy, you should see output similar to:

```bash
Deploying aws-python-project to stage dev (us-east-1)

✔ Service deployed to stack aws-python-project-dev (112s)

functions:
  hello: aws-python-project-dev-hello (1.5 kB)
```

### Invocation

After successful deployment, you can invoke the deployed function by using the following command:

```bash
serverless invoke --function replicate
```

Which should result in response similar to the following:

```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Operation completed without error.\", \"input\": {}}"
}
```

### Local development

You can invoke your function locally by using the following command:

```bash
serverless invoke local --function replicate
```

Which should result in response similar to the following:

```
{
    "statusCode": 200,
    "body": "{\"message\": \"Operation completed without error.\", \"input\": {}}"
}
```

### Bundling dependencies

In case you would like to include third-party dependencies, you will need to use a plugin
called `serverless-python-requirements`. You can set it up by running the following command:

```bash
serverless plugin install -n serverless-python-requirements
```

Running the above will automatically add `serverless-python-requirements` to `plugins` section in your `serverless.yml`
file and add it as a `devDependency` to `package.json` file. The `package.json` file will be automatically created if it
doesn't exist beforehand. Now you will be able to add your dependencies to `requirements.txt` file (`Pipfile`
and `pyproject.toml` is also supported but requires additional configuration) and they will be automatically injected to
Lambda package during build process. For more details about the plugin's configuration, please refer
to [official documentation](https://github.com/UnitedIncome/serverless-python-requirements).
