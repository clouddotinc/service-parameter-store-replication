from dataclasses import dataclass


@dataclass
class Secret:
    """Ensure a clean struct from differing methods."""
    ID: str
    ARN: str
    Name: str
    Description: str
    PrimaryRegion: str
    ReplicationStatus: list

    def has_replication(self, target_region):
        return len(self.ReplicationStatus) > 0 and target_region in [region['Region'] for region in self.ReplicationStatus]
