import json
import boto3
import os
from Parameter import Parameter

sns_topic_arn = os.getenv('SNS_TOPIC')
sns_region = os.getenv('SNS_REGION')

source_region = os.getenv('SOURCE_REGION')
target_region = os.getenv('TARGET_REGION')
account_id = os.getenv('ACCOUNT_ID')

ssm_source_client = boto3.client('ssm', region_name=source_region)
ssm_target_client = boto3.client('ssm', region_name=target_region)

secrets_client = boto3.client('secretsmanager', region_name=source_region)


def notify_exception(ex, context=""):
    subject = "parameter-store-replication-lambda failure detected"
    message = {
        "account_id": account_id,
        "context": context,
        "error_detail": ex.__str__(),
    }

    sns = boto3.client('sns', region_name=sns_region)
    sns.publish(
        TargetArn=sns_topic_arn,
        Message=json.dumps(message),
        Subject=subject,
    )


# delete is a write operation, so we hard-code **ssm_target_client** and avoid modification of source.
def delete_parameter(parameter_name):
    try:
        ssm_target_client.get_parameter(Name=parameter_name, WithDecryption=True)
        ssm_target_client.delete_parameter(Name=parameter_name)
    except ssm_target_client.exceptions.ParameterNotFound:
        pass
    except BaseException as ex:
        notify_exception(ex, f"Failure during delete_parameter({parameter_name}).")


# update is a write operation, so we hard-code **ssm_target_client** and avoid modification of source.
def update_parameter(parameter: Parameter):
    try:

        parameter.add_replication_tags()

        update = {
            "Name": parameter.Name,
            "Description": parameter.Description,
            "Value": parameter.Value,
            "Type": parameter.Type,
            "AllowedPattern": parameter.AllowedPattern,
            "Tier": parameter.Tier,
            "DataType": parameter.DataType,
            "Overwrite": True
        }

        if parameter.Tier.lower() != "standard":
            update.Policies = json.dumps(parameter.Policies)
        ssm_target_client.put_parameter(**update)
        ssm_target_client.add_tags_to_resource(ResourceType='Parameter', ResourceId=parameter.Name, Tags=parameter.Tags)

    except BaseException as ex:
        notify_exception(ex, f"Failure during update_parameter({parameter.Name}).")


def get_parameter_tags(parameter_name):
    tags = ssm_source_client.list_tags_for_resource(ResourceType='Parameter', ResourceId=parameter_name)
    return tags['TagList']


def get_parameter(parameter_name):
    try:
        get = ssm_source_client.get_parameter(Name=parameter_name, WithDecryption=True)
        base = get['Parameter']
        describe = ssm_source_client.describe_parameters(ParameterFilters=[{
            'Key': 'Name',
            'Option': 'Equals',
            'Values': [parameter_name]
        }])

        param = describe['Parameters'][0]
        param['Tags'] = get_parameter_tags(parameter_name)
        base.update(describe['Parameters'][0])

        return Parameter(**base)

    except BaseException as ex:
        notify_exception(ex, f"Failure during get_parameter({parameter_name}).")


def get_paginated_parameters(ssm_client):
    try:
        paginator = ssm_client.get_paginator('describe_parameters')
        page_iterator = paginator.paginate().build_full_result()
        return page_iterator
    except BaseException as ex:
        notify_exception(ex, f"Failure during describe_parameters() for region: {ssm_client.meta.region_name}")
        raise


def get_all_parameters(ssm_client):
    parameters = []
    for page in get_paginated_parameters(ssm_client)['Parameters']:
        try:
            get_param = get_parameter(page['Name'])
            parameters.append(get_param)
        except BaseException as ex:
            parameter_name = "Missing Name"
            if "Name" in page:
                parameter_name = page['Name']
            notify_exception(ex, f"Failure during get_all_parameters() call for param: {parameter_name}")

    return parameters


def get_paginated_secrets():
    try:
        paginator = secrets_client.get_paginator('list_secrets')
        page_iterator = paginator.paginate()
        return page_iterator
    except BaseException as ex:
        notify_exception(ex, f"Failure during list_secrets() for region: {secrets_client.meta.region_name}")
        raise


def get_all_secrets():
    secrets = []
    for secret in get_paginated_secrets():
        secrets += secret['SecretList']

    return secrets


def get_all_secret_arns():
    return [secret for secret in get_all_secrets()]


def replicate_all_secrets():
    secrets_list = get_all_secret_arns()
    for secret_list in secrets_list:
        secret = secrets_client.describe_secret(SecretId=secret_list['ARN'])
        if "ReplicationStatus" not in secret:
            replicate_secret(secret_list['ARN'])


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


def handle(event, context):
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
