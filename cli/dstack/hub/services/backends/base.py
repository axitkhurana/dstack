from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Union

from dstack.backend.base.config import BackendConfig
from dstack.hub.models import AnyProjectConfig, AnyProjectConfigWithCreds, Project, ProjectValues


class BackendConfigError(Exception):
    def __init__(self, message: str = "", code: str = "invalid_config", fields: List[str] = None):
        self.message = message
        self.code = code
        self.fields = fields if fields is not None else []


class Configurator(ABC):
    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def configure_project(self, config_data: Dict) -> ProjectValues:
        pass

    @abstractmethod
    def create_config_auth_data_from_project_config(
        self, project_config: AnyProjectConfigWithCreds
    ) -> Tuple[Dict, Dict]:
        pass

    @abstractmethod
    def get_project_config_from_project(
        self, project: Project, include_creds: bool
    ) -> Union[AnyProjectConfig, AnyProjectConfigWithCreds]:
        pass

    @abstractmethod
    def get_config_from_hub_config_data(
        self, project_name: str, config_data: Dict, auth_data: Dict
    ) -> BackendConfig:
        pass
