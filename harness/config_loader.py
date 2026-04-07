"""Load and validate the master config.yaml."""

from pathlib import Path
from dataclasses import dataclass

import yaml


@dataclass
class LocalModel:
    id: str
    name: str
    params: str
    active_params: str
    size_gb: float
    num_ctx: int
    notes: str = ""


@dataclass
class FrontierModel:
    id: str
    name: str
    input_price_per_mtok: float
    output_price_per_mtok: float


@dataclass
class TestParams:
    runs_per_test: int
    temperature_code: float
    temperature_writing: float
    mdap_k: int
    mdap_k_sensitivity: int


@dataclass
class LocalCost:
    power_watts: float
    electricity_per_kwh_gbp: float
    hardware_cost_gbp: float
    amortisation_years: float
    gbp_to_usd: float = 1.28

    @property
    def cost_per_hour_gbp(self) -> float:
        electricity = (self.power_watts / 1000) * self.electricity_per_kwh_gbp
        amortisation = self.hardware_cost_gbp / (self.amortisation_years * 365 * 24)
        return electricity + amortisation

    @property
    def cost_per_hour_usd(self) -> float:
        return self.cost_per_hour_gbp * self.gbp_to_usd

    @property
    def cost_per_second_usd(self) -> float:
        return self.cost_per_hour_usd / 3600


@dataclass
class Config:
    ollama_base_url: str
    ollama_default_temperature: float
    ollama_default_num_ctx: int
    local_models: list[LocalModel]
    frontier_models: list[FrontierModel]
    test_params: TestParams
    local_cost: LocalCost
    llm_judge_model: str
    embedding_model: str
    categories: list[str]
    tiers: list[str]

    def get_local_model(self, model_id: str) -> LocalModel:
        for m in self.local_models:
            if m.id == model_id:
                return m
        raise ValueError(f"Unknown local model: {model_id}")

    def get_frontier_model(self, model_id: str) -> FrontierModel:
        for m in self.frontier_models:
            if m.id == model_id:
                return m
        raise ValueError(f"Unknown frontier model: {model_id}")


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        path = Path(__file__).parent.parent / "config.yaml"
    path = Path(path)

    with open(path) as f:
        raw = yaml.safe_load(f)

    local_models = [LocalModel(**m) for m in raw["models"]["local"]]
    frontier_models = [FrontierModel(**m) for m in raw["models"]["frontier"]]
    test_params = TestParams(**raw["test_params"])
    local_cost = LocalCost(**raw["local_cost"])

    return Config(
        ollama_base_url=raw["ollama"]["base_url"],
        ollama_default_temperature=raw["ollama"]["default_params"]["temperature"],
        ollama_default_num_ctx=raw["ollama"]["default_params"]["num_ctx"],
        local_models=local_models,
        frontier_models=frontier_models,
        test_params=test_params,
        local_cost=local_cost,
        llm_judge_model=raw["evaluation"]["llm_judge_model"],
        embedding_model=raw["evaluation"]["embedding_model"],
        categories=raw["categories"],
        tiers=raw["tiers"],
    )
