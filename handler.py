import json
import boto3
import os
from dataclasses import dataclass

ssm_source = boto3.client('ssm', region_name=os.getenv('source_region'))
ssm_target = boto3.client('ssm', region_name=os.getenv('target_region'))


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

def replicate(event):
    if "detail" in event and "name" in event['detail']:
        parameter_name = event['detail']['name']

        if parameter_name == "all":
            sync_all_parameters()

        elif "operation" in event['detail']:
            operation = event['detail']['operation']

            try:
                if operation in ["update", "create"]:
                    parameter = get_parameter(parameter_name)
                    update_parameter(parameter)
                elif operation in ["delete"]:
                    delete_parameter(parameter_name)
            except BaseException as ex:
                notify_exception(ex)

    body = {
        "message": "Operation completed without error."
    }
    return {"statusCode": 200, "body": json.dumps(body)}


def notify_exception(ex):
    foo = "bar"  # TODO stub this out with SNS notification. DR Team?


def get_parameter(parameter_name):
    request = ssm_source.get_parameter(Name=parameter_name, WithDecryption=True)
    return Parameter(**request['Parameter'])


def delete_parameter(parameter_name):
    ssm_target.delete_parameter(Name=parameter_name, WithDecryption=True)


def update_parameter(parameter: Parameter):
    ssm_target.put_parameter(parameter.__dict__)


def sync_all_parameters():
    # This will most definitely not delete things from either account. There are reasons, namely that I don't
    # want someone to stand up resources in another region and then wonder why they keep disappearing. Individual
    # item deletes *should* be handled by the delete action above, as we see those in logs. This is all best-effort.

    # For future me, consider deleting params that are missing from source if they are tagged as replicated.

    paginator = ssm_source.get_paginator('describe_parameters')
    page_iterator = paginator.paginate().build_full_result()

    for page in page_iterator['Parameters']:
        # page gets us everything except the parameter's current value.

        try:
            parameter = get_parameter(page['Name'])

            param = Parameter(**{
                "Value": parameter.Value,
                "Name": page['Parameter']['Name'],
                "Description": page['Parameter']['Description'],
                "Type": page['Parameter']['Type'],
                "Overwrite": True,
                "AllowedPattern": page['Parameter']['AllowedPattern'],
                "Tags": [
                    {
                        'Key': 'Environment',
                        'Value': 'disaster-recovery'
                    },
                    {
                        'Key': 'Source',
                        'Value': 'parameter-store-replication-lambda'
                    }
                ],
                "Tier": page['Parameter']['Tier'],
                "Policies": page['Parameter']['Policies'],
                "DataType": page['Parameter']['DataType']
            })

            update_parameter(param)
        except BaseException as ex:
            notify_exception(ex)


