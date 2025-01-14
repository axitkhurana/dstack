import json
from typing import Dict, List, Optional, Tuple, Union

import botocore.exceptions
from boto3.session import Session

from dstack._internal.backend.aws import AwsBackend
from dstack._internal.backend.aws.config import AWSConfig
from dstack._internal.backend.base.config import BackendConfig
from dstack._internal.hub.db.models import Project
from dstack._internal.hub.models import (
    AWSBucketProjectElement,
    AWSBucketProjectElementValue,
    AWSProjectConfig,
    AWSProjectConfigWithCreds,
    AWSProjectCreds,
    AWSProjectValues,
    ProjectElement,
    ProjectElementValue,
)
from dstack._internal.hub.services.backends.base import BackendConfigError, Configurator

regions = [
    ("US East, N. Virginia", "us-east-1"),
    ("US East, Ohio", "us-east-2"),
    ("US West, N. California", "us-west-1"),
    ("US West, Oregon", "us-west-2"),
    ("Asia Pacific, Singapore", "ap-southeast-1"),
    ("Canada, Central", "ca-central-1"),
    ("Europe, Frankfurt", "eu-central-1"),
    ("Europe, Ireland", "eu-west-1"),
    ("Europe, London", "eu-west-2"),
    ("Europe, Paris", "eu-west-3"),
    ("Europe, Stockholm", "eu-north-1"),
]


class AWSConfigurator(Configurator):
    NAME = "aws"

    def get_backend_class(self) -> type:
        return AwsBackend

    def configure_project(self, config_data: Dict) -> AWSProjectValues:
        config = AWSConfig.deserialize(config_data)

        if config.region_name is not None and config.region_name not in {r[1] for r in regions}:
            raise BackendConfigError(f"Invalid AWS region {config.region_name}")

        project_values = AWSProjectValues()
        session = Session()
        if session.region_name is None:
            session = Session(region_name=config.region_name)

        project_values.default_credentials = self._valid_credentials(session=session)

        credentials_data = config_data.get("credentials")
        if credentials_data is None:
            return project_values

        if credentials_data["type"] == "access_key":
            session = Session(
                region_name=config.region_name,
                aws_access_key_id=credentials_data["access_key"],
                aws_secret_access_key=credentials_data["secret_key"],
            )
            if not self._valid_credentials(session=session):
                self._raise_invalid_credentials_error(
                    fields=[["credentials", "access_key"], ["credentials", "secret_key"]]
                )
        elif not project_values.default_credentials:
            self._raise_invalid_credentials_error(fields=[["credentials"]])

        # TODO validate config values
        project_values.region_name = self._get_hub_regions(default_region=session.region_name)
        project_values.s3_bucket_name = self._get_hub_buckets(
            session=session, region=config.region_name, default_bucket=config.bucket_name
        )
        project_values.ec2_subnet_id = self._get_hub_subnet(
            session=session, default_subnet=config.subnet_id
        )
        return project_values

    def create_config_auth_data_from_project_config(
        self, project_config: AWSProjectConfigWithCreds
    ) -> Tuple[Dict, Dict]:
        project_config.s3_bucket_name = project_config.s3_bucket_name.replace("s3://", "")
        config = AWSProjectConfig.parse_obj(project_config).dict()
        auth = project_config.credentials.__root__.dict()
        return config, auth

    def get_backend_config_from_hub_config_data(
        self, project_name: str, config_data: Dict, auth_data: Dict
    ) -> BackendConfig:
        return AWSConfig.deserialize(config_data, auth_data)

    def get_project_config_from_project(
        self, project: Project, include_creds: bool
    ) -> Union[AWSProjectConfig, AWSProjectConfigWithCreds]:
        json_config = json.loads(project.config)
        region_name = json_config["region_name"]
        s3_bucket_name = json_config["s3_bucket_name"]
        ec2_subnet_id = json_config["ec2_subnet_id"]
        if include_creds:
            json_auth = json.loads(project.auth)
            return AWSProjectConfigWithCreds(
                region_name=region_name,
                region_name_title=region_name,
                s3_bucket_name=s3_bucket_name,
                ec2_subnet_id=ec2_subnet_id,
                credentials=AWSProjectCreds.parse_obj(json_auth),
            )
        return AWSProjectConfig(
            region_name=region_name,
            region_name_title=region_name,
            s3_bucket_name=s3_bucket_name,
            ec2_subnet_id=ec2_subnet_id,
        )

    def _valid_credentials(self, session: Session) -> bool:
        sts = session.client("sts")
        try:
            sts.get_caller_identity()
        except botocore.exceptions.ClientError:
            return False
        return True

    def _raise_invalid_credentials_error(self, fields: Optional[List[List[str]]] = None):
        raise BackendConfigError(
            "Invalid credentials",
            code="invalid_credentials",
            fields=fields,
        )

    def _get_hub_regions(self, default_region: Optional[str]) -> ProjectElement:
        element = ProjectElement(selected=default_region)
        for r in regions:
            element.values.append(ProjectElementValue(value=r[1], label=r[0]))
        return element

    def _get_hub_buckets(
        self, session: Session, region: str, default_bucket: Optional[str]
    ) -> AWSBucketProjectElement:
        if default_bucket is not None:
            self._validate_hub_bucket(session=session, region=region, bucket_name=default_bucket)
        element = AWSBucketProjectElement(selected=default_bucket)
        s3_client = session.client("s3")
        response = s3_client.list_buckets()
        for bucket in response["Buckets"]:
            element.values.append(
                AWSBucketProjectElementValue(
                    name=bucket["Name"],
                    created=bucket["CreationDate"].strftime("%d.%m.%Y %H:%M:%S"),
                    region=region,
                )
            )
        return element

    def _validate_hub_bucket(self, session: Session, region: str, bucket_name: str):
        s3_client = session.client("s3")
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            bucket_region = response["ResponseMetadata"]["HTTPHeaders"]["x-amz-bucket-region"]
            if bucket_region.lower() != region:
                raise BackendConfigError(
                    "The bucket belongs to another AWS region",
                    code="invalid_bucket",
                    fields=[["s3_bucket_name"]],
                )
        except botocore.exceptions.ClientError as e:
            if (
                hasattr(e, "response")
                and e.response.get("Error")
                and e.response["Error"].get("Code") in ["404", "403"]
            ):
                raise BackendConfigError(
                    f"The bucket {bucket_name} does not exist",
                    code="invalid_bucket",
                    fields=[["s3_bucket_name"]],
                )
            raise e

    def _get_hub_subnet(self, session: Session, default_subnet: Optional[str]) -> ProjectElement:
        element = ProjectElement(selected=default_subnet)
        _ec2 = session.client("ec2")
        response = _ec2.describe_subnets()
        for subnet in response["Subnets"]:
            element.values.append(
                ProjectElementValue(
                    value=subnet["SubnetId"],
                    label=subnet["SubnetId"],
                )
            )
        return element
