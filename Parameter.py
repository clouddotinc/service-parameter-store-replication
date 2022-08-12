from dataclasses import dataclass


@dataclass
class Parameter:
    REPLICATED_TAG_VALUE = "parameter-store-replication-lambda"

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
        return self.REPLICATED_TAG_VALUE in [tag['Value'] for tag in self.Tags]

    def add_replication_tags(self):
        if not self.has_replication_tags():
            self.Tags = self.Tags + [
                {
                    'Key': 'Source',
                    'Value': self.REPLICATED_TAG_VALUE
                },
                {
                    'Key': 'Environment',
                    'Value': 'disaster-recovery'
                }
            ]
