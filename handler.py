import json
import boto3
import os
from Parameter import Parameter
from Secret import Secret

sns_topic = os.getenv('SNS_TOPIC')
sns_region = os.getenv('SNS_REGION')

source_region = os.getenv('SOURCE_REGION')
target_region = os.getenv('TARGET_REGION')
account_id = os.getenv('ACCOUNT_ID')

ssm_source_client = boto3.client('ssm', region_name=source_region)
ssm_target_client = boto3.client('ssm', region_name=target_region)

secrets_client = boto3.client('secretsmanager', region_name=source_region)


def notify_exception(ex, context=""):
    message = {
        "subject": "parameter-store-replication-lambda failure detected",
        "account_id": account_id,
        "context": context,
        "error_detail": ex,
    }

    sns = boto3.client('sns', TopicArn=sns_topic, region_name=sns_region)
    print(json.dumps(message))


# delete is a write operation, so we hard-code **ssm_target_client** and avoid modification of source.
def delete_parameter(parameter_name):
    print(f"delete_parameter({parameter_name}) was called.")
    try:
        foo = 1  # TODO uncomment when ready.
        # ssm_target_client.delete_parameter(Name=parameter_name, WithDecryption=True)
    except BaseException as ex:
        notify_exception(ex, f"Failure during delete_parameter({parameter_name}).")


# update is a write operation, so we hard-code **ssm_target_client** and avoid modification of source.
def update_parameter(parameter: Parameter):
    print(f"update_parameter({parameter.Name}) was called.")
    try:
        foo = 2  # TODO uncomment when ready.
        # ssm_target_client.put_parameter(parameter.__dict__)
    except BaseException as ex:
        notify_exception(ex, f"Failure during update_parameter({parameter.Name}).")


def get_parameter(parameter_name):
    try:
        request = ssm_source_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return Parameter(**request['Parameter'])
    except BaseException as ex:
        notify_exception(ex, f"Failure during get_parameter({parameter_name}")


def get_paginated_parameters(ssm_client):
    try:
        paginator = ssm_client.get_paginator('describe_parameters')
        page_iterator = paginator.paginate().build_full_result()
        return page_iterator
    except BaseException as ex:
        notify_exception(ex, f"Failure during describe_parameters() for region: {ssm_client.meta.region_name}")

        # This is only reached if sync_all_parameters() is invoked and will break that workflow completely,
        # so we need to force an exit.
        exit(1)


def get_all_parameters(ssm_client):
    parameters = []

    for page in get_paginated_parameters(ssm_client)['Parameters']:
        try:
            parameter = get_parameter(page['Parameter']['Name'])
            loaded = page.update(parameter)
            parameters.append(Parameter(**loaded))

        except BaseException as ex:
            parameter_name = "Missing Name"
            if "Parameter" in page and "Name" in page['Parameter']:
                parameter_name = page['Parameter']['Name']
            notify_exception(ex, f"Failure during get_all_parameters() call for param: {parameter_name}")

    return parameters


def get_paginated_secrets():
    try:
        paginator = secrets_client.get_paginator('list_secrets')
        page_iterator = paginator.paginate().build_full_result()
        return page_iterator
    except BaseException as ex:
        notify_exception(ex, f"Failure during list_secrets() for region: {secrets_client.meta.region_name}")

        # This is only reached if sync_all_parameters() is invoked and will break that workflow completely,
        # so we need to force an exit.
        exit(1)


def get_all_secret_ids():
    return [secret['Id'] for secret in get_paginated_secrets()['Secrets']]


def replicate_all_secrets():
    secret_ids = get_all_secret_ids()
    for secret_id in secret_ids:
        secret = secrets_client.describe_secret(SecretId=secret_id)
        secret = Secret(**secret)
        if not secret.has_replication(target_region=target_region):
            foo = 3
            # TODO uncomment when ready to test replication.
            # replicate_secret(secret_id)


def replicate_secret(secret_id):
    try:
        secrets_client.replicate_secret_to_regions(
            SecretId=secret_id,
            AddReplicaRegions=[
                {
                    'Region': target_region
                },
            ],
            ForceOverwriteReplicaSecret=True
        )
    except BaseException as ex:
        notify_exception(ex, f"Failure when enabling secret replication: ID {secret_id} to Region {target_region}")


def sync_all_parameters():
    source_names = []

    for param in get_all_parameters(ssm_source_client):
        source_names.append(param.Name)
        param.add_replication_tags()
        update_parameter(param)

    for param in get_all_parameters(ssm_target_client):
        if param.Name not in source_names and param.has_replication_tags():
            delete_parameter(param.Name)


def validate_configuration(event):
    if source_region == target_region:
        raise ValueError("Source and Target regions cannot be the same.")

    if "detail" not in event:
        raise ValueError("Invalidly formed event. Missing 'detail' key.")

    if "name" not in event['detail']:
        raise ValueError("Invalidly formed event. Missing 'name' in detail object.")


def get_event_detail(event):
    validate_configuration(event)

    name = event['detail']['name']
    operation = ""
    if "operation" in event['detail']:
        operation = event['detail']['operation']

    return name, operation


def handle(event):
    name, operation = get_event_detail(event)

    if name == "all":
        sync_all_parameters()
        replicate_all_secrets()

    elif operation in ["update", "create"]:
        parameter = get_parameter(name)
        update_parameter(parameter)

    elif operation == "delete":
        delete_parameter(name)

    body = {
        "message": "Operation completed without error."
    }
    return {"statusCode": 200, "body": json.dumps(body)}
