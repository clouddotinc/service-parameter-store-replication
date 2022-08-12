import json
import boto3
import os
from dataclasses import dataclass

ssm_source = boto3.client('ssm', region_name=os.getenv('source_region'))
ssm_target = boto3.client('ssm', region_name=os.getenv('target_region'))
replicated_tag_value = "parameter-store-replication-lambda"


def validate_configuration(event):
    if os.getenv('SOURCE_REGION') == os.getenv('TARGET_REGION'):
        raise ValueError("Source and Target regions cannot be the same.")

    if "detail" not in event:
        raise ValueError("Invalidly formed event. Missing 'detail' key.")

    if "name" not in event['detail']:
        raise ValueError("Invalidly formed event. Missing 'name' in detail object.")


@dataclass
class Parameter:
    """Ensure a clean struct from differing methods."""
    Name: str
    DataType: str
    Description: str
    Type: str
    Overwrite: bool
    AllowedPattern: str
    Tags: list
    Tier: str
    Policies: list
    Value: str = ""

    def has_replication_tags(self):
        for tag in self.Tags:
            if "Value" in tag and tag['Value'] == replicated_tag_value:
                return True
        return False

    def add_replication_tags(self):
        if not self.has_replication_tags():
            self.Tags = self.Tags + [
                {
                    'Key': 'Source',
                    'Value': replicated_tag_value
                },
                {
                    'Key': 'Environment',
                    'Value': 'disaster-recovery'
                }
            ]


# delete is a write operation, so we hard-code ssm_target as the client to avoid modification of source.
def delete_parameter(parameter_name):
    print(f"delete_parameter({parameter_name}) was called.")
    try:
        foo = 1
        # ssm_target.delete_parameter(Name=parameter_name, WithDecryption=True)
    except BaseException as ex:
        notify_exception(ex, f"Failure during delete_parameter({parameter_name}).")


# update is a write operation, so we hard-code ssm_target as the client to avoid modification of source.
def update_parameter(parameter: Parameter):
    print(f"update_parameter({parameter.Name}) was called.")
    try:
        foo = 2
        # ssm_target.put_parameter(parameter.__dict__)
    except BaseException as ex:
        notify_exception(ex, f"Failure during update_parameter({parameter.Name}).")


def notify_exception(ex, context=""):
    message = {
        "subject": "SSM Parameter Replication Failed!",
        "context": context,
        "error": ex,

    }
    sns = boto3.client('sns')  # TODO create a topic in mgmt account and grant access to all our accounts.

    print(message)
    exit(1)


def get_parameter(parameter_name):
    try:
        request = ssm_source.get_parameter(Name=parameter_name, WithDecryption=True)
        return Parameter(**request['Parameter'])
    except BaseException as ex:
        notify_exception(ex, f"Failure during get_parameter({parameter_name}")


def get_all_parameters(ssm_client):
    parameters = []
    paginator = ssm_client.get_paginator('describe_parameters')
    page_iterator = paginator.paginate().build_full_result()
    for page in page_iterator['Parameters']:
        try:
            parameter = get_parameter(page['Parameter']['Name'])

            param = Parameter(**{
                "Value": parameter.Value,
                "Name": page['Parameter']['Name'],
                "Description": page['Parameter']['Description'],
                "Type": page['Parameter']['Type'],
                "Overwrite": True,
                "AllowedPattern": page['Parameter']['AllowedPattern'],
                "Tags": page['Parameter']['Tags'],
                "Tier": page['Parameter']['Tier'],
                "Policies": page['Parameter']['Policies'],
                "DataType": page['Parameter']['DataType']
            })
            parameters.append(param)
        except BaseException as ex:
            parameter_name = "Missing Name"
            if "Parameter" in page and "Name" in page['Parameter']:
                parameter_name = page['Parameter']['Name']

            notify_exception(ex, f"Failure during get_all_parameters() call for param: {parameter_name}")

    return parameters


def sync_all_parameters():
    source_parameters = get_all_parameters(ssm_source)
    target_parameters = get_all_parameters(ssm_target)

    source_names = []
    for param in source_parameters:
        source_names.append(param.Name)

        param.add_replication_tags()
        update_parameter(param)

    for param in target_parameters:
        if param.Name not in source_names and param.has_replication_tags():
            delete_parameter(param.Name)

def handle(event):
    validate_configuration(event)

    parameter_name = event['detail']['name']

    if parameter_name == "all":
        sync_all_parameters()

    elif "operation" in event['detail']:
        operation = event['detail']['operation']
        if operation in ["update", "create"]:
            parameter = get_parameter(parameter_name)
            update_parameter(parameter)
        elif operation in ["delete"]:
            delete_parameter(parameter_name)

    body = {
        "message": "Operation completed without error."
    }
    return {"statusCode": 200, "body": json.dumps(body)}
