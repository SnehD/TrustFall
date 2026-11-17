"""Authorization policy evaluation - deliberately independent of signature verification."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    identity_verified: bool
    authorized: bool
    reason: str

    def to_dict(self):
        return {"identity_verified": self.identity_verified, "authorized": self.authorized, "reason": self.reason}


def evaluate_action(agent_id: str, action: str, scope: str, grants: dict, identity_verified: bool) -> PolicyDecision:
    """grants: {agent_id: [{"action": "config.write", "scopes": ["staging"]}, ...]}.
    Identity and authorization are separate outputs; authorized never depends on identity alone."""
    for g in grants.get(agent_id, []):
        if g["action"] == action and scope in g["scopes"]:
            return PolicyDecision(identity_verified, True, f"grant {action} on scope '{scope}' present")
    return PolicyDecision(identity_verified, False,
                          f"no grant for {action} on scope '{scope}' (identity verification is irrelevant to authorization)")
