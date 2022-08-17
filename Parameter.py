from dataclasses import dataclass
from datetime import datetime


@dataclass
class Parameter:
    REPLICATED_TAG_VALUE = "monitored-by-parameter-store-replication-lambda"

    """Ensure a clean struct from differing methods."""
    Name: str
    Type: str
    Version: int
    LastModifiedDate: datetime
    ARN: str
    DataType: str
    LastModifiedUser: str
    Description: str
    Tier: str
    Policies: str
    Tags: list = None
    Value: str = ""
    AllowedPattern: str = ""
    Overwrite = True

    def has_replication_tags(self):
        if self.Tags is None:
            self.Tags = []

        return self.REPLICATED_TAG_VALUE in [tag['Value'] for tag in self.Tags]

    def add_replication_tags(self):
        if not self.has_replication_tags():
            self.Tags = self.Tags + [
                {
                    'Key': 'ReplicationStatus',
                    'Value': self.REPLICATED_TAG_VALUE
                },
                {
                    'Key': 'Environment',
                    'Value': 'disaster-recovery'
                }
            ]
