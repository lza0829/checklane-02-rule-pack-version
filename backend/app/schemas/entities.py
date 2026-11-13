from pydantic import BaseModel


class InspectRequest(BaseModel):
    dataset_id: int
    rule_pack_id: int


class RuleEnablePatch(BaseModel):
    enabled: bool


class RulePackCreate(BaseModel):
    dataset_id: int
    note: str | None = None
