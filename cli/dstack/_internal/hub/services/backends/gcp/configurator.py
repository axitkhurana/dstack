import json
from typing import Dict, List, Optional, Tuple, Union

import google.auth
import google.auth.exceptions
import googleapiclient.discovery
import googleapiclient.errors
from google.cloud import compute_v1, storage
from google.oauth2 import service_account

from dstack._internal.backend.gcp import GCPBackend
from dstack._internal.backend.gcp import auth as gcp_auth
from dstack._internal.backend.gcp import utils as gcp_utils
from dstack._internal.backend.gcp.config import GCPConfig
from dstack._internal.hub.db.models import Project
from dstack._internal.hub.models import (
    GCPProjectConfig,
    GCPProjectConfigWithCreds,
    GCPProjectCreds,
    GCPProjectValues,
    GCPVPCSubnetProjectElement,
    GCPVPCSubnetProjectElementValue,
    ProjectElement,
    ProjectElementValue,
)
from dstack._internal.hub.services.backends.base import BackendConfigError, Configurator

DEFAULT_GEOGRAPHIC_AREA = "North America"

GCP_LOCATIONS = [
    {
        "name": "North America",
        "regions": [
            "northamerica-northeast1",
            "northamerica-northeast2",
            "us-central1",
            "us-east1",
            "us-east4",
            "us-east5",
            "us-south1",
            "us-west1",
            "us-west2",
            "us-west3",
            "us-west4",
        ],
        "default_region": "us-west1",
        "default_zone": "us-west1-b",
    },
    {
        "name": "South America",
        "regions": [
            "southamerica-east1",
            "southamerica-west1",
        ],
        "default_region": "southamerica-east1",
        "default_zone": "southamerica-east1-b",
    },
    {
        "name": "Europe",
        "regions": [
            "europe-central2",
            "europe-north1",
            "europe-southwest1",
            "europe-west1",
            "europe-west2",
            "europe-west3",
            "europe-west4",
            "europe-west6",
            "europe-west8",
            "europe-west9",
        ],
        "default_region": "europe-west4",
        "default_zone": "europe-west4-a",
    },
    {
        "name": "Asia",
        "regions": [
            "asia-east1",
            "asia-east2",
            "asia-northeast1",
            "asia-northeast2",
            "asia-northeast3",
            "asia-south1",
            "asia-south2",
            "asia-southeast1",
            "asia-southeast2",
        ],
        "default_region": "asia-southeast1",
        "default_zone": "asia-southeast1-b",
    },
    {
        "name": "Middle East",
        "regions": [
            "me-west1",
        ],
        "default_region": "me-west1",
        "default_zone": "me-west1-b",
    },
    {
        "name": "Australia",
        "regions": [
            "australia-southeast1",
            "australia-southeast2",
        ],
        "default_region": "australia-southeast1",
        "default_zone": "australia-southeast1-c",
    },
]


class GCPConfigurator(Configurator):
    NAME = "gcp"

    def get_backend_class(self) -> type:
        return GCPBackend

    def configure_project(self, config_data: Dict) -> GCPProjectValues:
        project_values = GCPProjectValues()
        try:
            self.credentials, self.project_id = google.auth.default()
        except google.auth.exceptions.DefaultCredentialsError:
            project_values.default_credentials = False
        else:
            project_values.default_credentials = True

        credentials_data = config_data.get("credentials")
        if credentials_data is None:
            return project_values

        if credentials_data["type"] == "service_account":
            try:
                self._auth(credentials_data)
                storage_client = storage.Client(credentials=self.credentials)
                storage_client.list_buckets(max_results=1)
            except Exception:
                self._raise_invalid_credentials_error(fields=[["credentials", "data"]])
        elif not project_values.default_credentials:
            self._raise_invalid_credentials_error(fields=[["credentials"]])

        project_values.area = self._get_hub_geographic_area(config_data.get("area"))
        location = self._get_location(project_values.area.selected)
        project_values.region, regions = self._get_hub_region(
            location=location,
            default_region=config_data.get("region"),
        )
        project_values.zone = self._get_hub_zone(
            location=location,
            region=regions.get(project_values.region.selected),
            default_zone=config_data.get("zone"),
        )
        project_values.bucket_name = self._get_hub_buckets(
            region=project_values.region.selected,
            default_bucket=config_data.get("bucket_name"),
        )
        project_values.vpc_subnet = self._get_hub_vpc_subnet(
            region=project_values.region.selected,
            default_vpc=config_data.get("vpc"),
            default_subnet=config_data.get("subnet"),
        )
        return project_values

    def create_config_auth_data_from_project_config(
        self, project_config: GCPProjectConfigWithCreds
    ) -> Tuple[Dict, Dict]:
        config_data = GCPProjectConfig.parse_obj(project_config).dict()
        auth_data = project_config.credentials.__root__.dict()
        if project_config.credentials.__root__.type == "default":
            self._auth(auth_data)
            service_account_email = self._get_or_create_service_account(
                f"{project_config.bucket_name}-sa"
            )
            self._grant_roles_to_service_account(service_account_email)
            self._check_if_can_create_service_account_key(service_account_email)
            auth_data["service_account_email"] = service_account_email
        return config_data, auth_data

    def get_backend_config_from_hub_config_data(
        self, project_name: str, config_data: Dict, auth_data: Dict
    ) -> GCPConfig:
        self._auth(auth_data)
        data = {
            "backend": "gcp",
            "credentials": auth_data,
            "project": self.project_id,
            "region": config_data["region"],
            "zone": config_data["zone"],
            "bucket": config_data["bucket_name"],
            "vpc": config_data["vpc"],
            "subnet": config_data["subnet"],
        }
        return GCPConfig.deserialize(data)

    def get_project_config_from_project(
        self, project: Project, include_creds: bool
    ) -> Union[GCPProjectConfig, GCPProjectConfigWithCreds]:
        json_config = json.loads(project.config)
        area = json_config["area"]
        region = json_config["region"]
        zone = json_config["zone"]
        bucket_name = json_config["bucket_name"]
        vpc = json_config["vpc"]
        subnet = json_config["subnet"]
        if include_creds:
            json_auth = json.loads(project.auth)
            return GCPProjectConfigWithCreds(
                credentials=GCPProjectCreds.parse_obj(json_auth),
                area=area,
                region=region,
                zone=zone,
                bucket_name=bucket_name,
                vpc=vpc,
                subnet=subnet,
            )
        return GCPProjectConfig(
            area=area,
            region=region,
            zone=zone,
            bucket_name=bucket_name,
            vpc=vpc,
            subnet=subnet,
        )

    def _get_hub_geographic_area(self, default_area: Optional[str]) -> ProjectElement:
        area_names = sorted([l["name"] for l in GCP_LOCATIONS])
        if default_area is None:
            default_area = DEFAULT_GEOGRAPHIC_AREA
        if default_area not in area_names:
            raise BackendConfigError(f"Invalid GCP area {default_area}")
        element = ProjectElement(selected=default_area)
        for area_name in area_names:
            element.values.append(ProjectElementValue(value=area_name, label=area_name))
        return element

    def _get_hub_region(
        self, location: Dict, default_region: Optional[str]
    ) -> Tuple[ProjectElement, Dict]:
        regions_client = compute_v1.RegionsClient(credentials=self.credentials)
        regions = regions_client.list(project=self.project_id)
        region_names = sorted(
            [r.name for r in regions if r.name in location["regions"]],
            key=lambda name: (name != location["default_region"], name),
        )
        if default_region is None:
            default_region = region_names[0]
        if default_region not in region_names:
            raise BackendConfigError(
                f"Invalid GCP region {default_region} in area {location['name']}"
            )
        element = ProjectElement(selected=default_region)
        for region_name in region_names:
            element.values.append(ProjectElementValue(value=region_name, label=region_name))
        return element, {r.name: r for r in regions}

    def _get_location(self, area: str) -> Optional[Dict]:
        for location in GCP_LOCATIONS:
            if location["name"] == area:
                return location
        return None

    def _get_hub_zone(
        self, location: Dict, region: compute_v1.Region, default_zone: Optional[str]
    ) -> ProjectElement:
        zone_names = sorted(
            [gcp_utils.get_resource_name(z) for z in region.zones],
            key=lambda name: (name != location["default_zone"], name),
        )
        if default_zone is None:
            default_zone = zone_names[0]
        if default_zone not in zone_names:
            raise BackendConfigError(f"Invalid GCP zone {default_zone} in region {region.name}")
        element = ProjectElement(selected=default_zone)
        for zone_name in zone_names:
            element.values.append(ProjectElementValue(value=zone_name, label=zone_name))
        return element

    def _get_hub_buckets(
        self, region: str, default_bucket: Optional[str] = None
    ) -> ProjectElement:
        storage_client = storage.Client(credentials=self.credentials)
        buckets = storage_client.list_buckets()
        bucket_names = [bucket.name for bucket in buckets if bucket.location.lower() == region]
        if default_bucket is not None and default_bucket not in bucket_names:
            raise BackendConfigError(
                f"Invalid bucket {default_bucket} for region {region}",
                code="invalid_bucket",
                fields=[["bucket_name"]],
            )
        element = ProjectElement(selected=default_bucket)
        for bucket_name in bucket_names:
            element.values.append(ProjectElementValue(value=bucket_name, label=bucket_name))
        return element

    def _get_hub_vpc_subnet(
        self,
        region: str,
        default_vpc: Optional[str],
        default_subnet: Optional[str],
    ) -> GCPVPCSubnetProjectElement:
        if default_vpc is None:
            default_vpc = "default"
        if default_subnet is None:
            default_subnet = "default"
        no_preference_vpc_subnet = ("default", "default")
        networks_client = compute_v1.NetworksClient(credentials=self.credentials)
        networks = networks_client.list(project=self.project_id)
        vpc_subnet_list = []
        for network in networks:
            for subnet in network.subnetworks:
                subnet_region = gcp_utils.get_subnet_region(subnet)
                if subnet_region != region:
                    continue
                vpc_subnet_list.append((network.name, gcp_utils.get_subnet_name(subnet)))
        if (default_vpc, default_subnet) not in vpc_subnet_list:
            raise BackendConfigError(f"Invalid VPC subnet {default_vpc, default_subnet}")
        if (default_vpc, default_subnet) != no_preference_vpc_subnet:
            selected = f"{default_subnet} ({default_vpc})"
        else:
            selected = f"No preference (default)"
        vpc_subnet_list = sorted(vpc_subnet_list, key=lambda t: t != no_preference_vpc_subnet)
        element = GCPVPCSubnetProjectElement(selected=selected)
        for vpc, subnet in vpc_subnet_list:
            element.values.append(
                GCPVPCSubnetProjectElementValue(
                    vpc=vpc,
                    subnet=subnet,
                    label=f"{subnet} ({vpc})"
                    if (subnet, vpc) != no_preference_vpc_subnet
                    else f"No preference (default)",
                )
            )
        return element

    def _auth(self, credentials_data: Dict):
        if credentials_data["type"] == "service_account":
            service_account_info = json.loads(credentials_data["data"])
            self.credentials = service_account.Credentials.from_service_account_info(
                info=service_account_info
            )
            self.project_id = self.credentials.project_id
        else:
            self.credentials, self.project_id = google.auth.default()

    def _get_or_create_service_account(self, name: str) -> str:
        iam_service = googleapiclient.discovery.build("iam", "v1", credentials=self.credentials)
        try:
            service_account = (
                iam_service.projects()
                .serviceAccounts()
                .create(
                    name="projects/" + self.project_id,
                    body={
                        "accountId": name,
                        "serviceAccount": {
                            "displayName": name,
                        },
                    },
                )
                .execute()
            )
            return service_account["email"]
        except googleapiclient.errors.HttpError as e:
            if e.status_code == 409:
                return gcp_utils.get_service_account_email(self.project_id, name)
            elif e.status_code == 403:
                raise BackendConfigError(
                    "Not enough permissions. Default credentials must have Service Account Admin role.",
                    code="not_enough_permissions",
                )
            raise e

    def _grant_roles_to_service_account(self, service_account_email: str):
        service = googleapiclient.discovery.build(
            "cloudresourcemanager", "v1", credentials=self.credentials
        )
        try:
            policy = service.projects().getIamPolicy(resource=self.project_id).execute()
            self._add_roles_to_policy(
                policy=policy,
                service_account_email=service_account_email,
                roles=self._get_service_account_roles(),
            )
            service.projects().setIamPolicy(
                resource=self.project_id, body={"policy": policy}
            ).execute()
        except googleapiclient.errors.HttpError as e:
            if e.status_code == 403:
                raise BackendConfigError(
                    "Not enough permissions. Default credentials must have Security Admin role.",
                    code="not_enough_permissions",
                )
            raise e

    def _get_service_account_roles(self) -> List[str]:
        return [
            "roles/compute.admin",
            "roles/logging.admin",
            "roles/secretmanager.admin",
            "roles/storage.admin",
            "roles/iam.serviceAccountUser",
        ]

    def _add_roles_to_policy(self, policy: Dict, service_account_email: str, roles: List[str]):
        member = f"serviceAccount:{service_account_email}"
        for role in roles:
            policy["bindings"].append({"role": role, "members": [member]})

    def _check_if_can_create_service_account_key(self, service_account_email: str):
        try:
            gcp_auth.create_service_account_key(
                iam_service=googleapiclient.discovery.build(
                    "iam", "v1", credentials=self.credentials
                ),
                project_id=self.project_id,
                service_account_email=service_account_email,
            )
        except gcp_auth.NotEnoughPermissionError:
            raise BackendConfigError(
                "Not enough permissions. Default credentials must have Service Account Key Admin role.",
                code="not_enough_permissions",
            )

    def _raise_invalid_credentials_error(self, fields: Optional[List[List[str]]] = None):
        raise BackendConfigError(
            "Invalid credentials",
            code="invalid_credentials",
            fields=fields,
        )
