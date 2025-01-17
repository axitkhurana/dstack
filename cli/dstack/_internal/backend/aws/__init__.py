from datetime import datetime
from typing import Generator, List, Optional

import boto3
from botocore.client import BaseClient

from dstack._internal.backend.aws import logs
from dstack._internal.backend.aws.compute import AWSCompute
from dstack._internal.backend.aws.config import AWSConfig
from dstack._internal.backend.aws.secrets import AWSSecretsManager
from dstack._internal.backend.aws.storage import AWSStorage
from dstack._internal.backend.base import Backend
from dstack._internal.backend.base import artifacts as base_artifacts
from dstack._internal.backend.base import cache as base_cache
from dstack._internal.backend.base import jobs as base_jobs
from dstack._internal.backend.base import repos as base_repos
from dstack._internal.backend.base import runs as base_runs
from dstack._internal.backend.base import secrets as base_secrets
from dstack._internal.backend.base import tags as base_tags
from dstack._internal.core.artifact import Artifact
from dstack._internal.core.instance import InstanceType
from dstack._internal.core.job import Job, JobHead, JobStatus
from dstack._internal.core.log_event import LogEvent
from dstack._internal.core.repo import RemoteRepoCredentials, RepoHead, RepoSpec
from dstack._internal.core.repo.base import Repo
from dstack._internal.core.run import RunHead
from dstack._internal.core.secret import Secret
from dstack._internal.core.tag import TagHead
from dstack._internal.utils.common import PathLike


class AwsBackend(Backend):
    NAME = "aws"
    backend_config: AWSConfig
    _storage: AWSStorage
    _compute: AWSCompute
    _secrets_manager: AWSSecretsManager

    def __init__(
        self,
        backend_config: AWSConfig,
    ):
        super().__init__(backend_config=backend_config)
        if self.backend_config.credentials is not None:
            self._session = boto3.session.Session(
                region_name=self.backend_config.region_name,
                aws_access_key_id=self.backend_config.credentials.get("access_key"),
                aws_secret_access_key=self.backend_config.credentials.get("secret_key"),
            )
        else:
            self._session = boto3.session.Session(region_name=self.backend_config.region_name)
        self._storage = AWSStorage(
            s3_client=self._s3_client(), bucket_name=self.backend_config.bucket_name
        )
        self._compute = AWSCompute(
            ec2_client=self._ec2_client(),
            iam_client=self._iam_client(),
            bucket_name=self.backend_config.bucket_name,
            region_name=self.backend_config.region_name,
            subnet_id=self.backend_config.subnet_id,
        )
        self._secrets_manager = AWSSecretsManager(
            secretsmanager_client=self._secretsmanager_client(),
            iam_client=self._iam_client(),
            sts_client=self._sts_client(),
            bucket_name=self.backend_config.bucket_name,
        )

    @classmethod
    def load(cls) -> Optional["AwsBackend"]:
        config = AWSConfig.load()
        if config is None:
            return None
        return cls(
            backend_config=config,
        )

    def _s3_client(self) -> BaseClient:
        return self._get_client("s3")

    def _ec2_client(self) -> BaseClient:
        return self._get_client("ec2")

    def _iam_client(self) -> BaseClient:
        return self._get_client("iam")

    def _logs_client(self) -> BaseClient:
        return self._get_client("logs")

    def _secretsmanager_client(self) -> BaseClient:
        return self._get_client("secretsmanager")

    def _sts_client(self) -> BaseClient:
        return self._get_client("sts")

    def _get_client(self, client_name: str) -> BaseClient:
        return self._session.client(client_name)

    def predict_instance_type(self, job: Job) -> Optional[InstanceType]:
        return base_jobs.predict_job_instance(self._compute, job)

    def create_run(self, repo_id: str) -> str:
        logs.create_log_groups_if_not_exist(
            self._logs_client(), self.backend_config.bucket_name, repo_id
        )
        return base_runs.create_run(self._storage)

    def create_job(self, job: Job):
        base_jobs.create_job(self._storage, job)

    def get_job(self, repo_id: str, job_id: str) -> Optional[Job]:
        return base_jobs.get_job(self._storage, repo_id, job_id)

    def list_jobs(self, repo_id: str, run_name: str) -> List[Job]:
        return base_jobs.list_jobs(self._storage, repo_id, run_name)

    def run_job(self, job: Job, failed_to_start_job_new_status: JobStatus):
        base_jobs.run_job(self._storage, self._compute, job, failed_to_start_job_new_status)

    def stop_job(self, repo_id: str, abort: bool, job_id: str):
        base_jobs.stop_job(self._storage, self._compute, repo_id, job_id, abort)

    def list_job_heads(self, repo_id: str, run_name: Optional[str] = None) -> List[JobHead]:
        return base_jobs.list_job_heads(self._storage, repo_id, run_name)

    def delete_job_head(self, repo_id: str, job_id: str):
        base_jobs.delete_job_head(self._storage, repo_id, job_id)

    def list_run_heads(
        self,
        repo_id: str,
        run_name: Optional[str] = None,
        include_request_heads: bool = True,
        interrupted_job_new_status: JobStatus = JobStatus.FAILED,
    ) -> List[RunHead]:
        job_heads = self.list_job_heads(repo_id=repo_id, run_name=run_name)
        return base_runs.get_run_heads(
            self._storage,
            self._compute,
            job_heads,
            include_request_heads,
            interrupted_job_new_status,
        )

    def poll_logs(
        self,
        repo_id: str,
        run_name: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        descending: bool = False,
        diagnose: bool = False,
    ) -> Generator[LogEvent, None, None]:
        return logs.poll_logs(
            self._storage,
            self._logs_client(),
            self.backend_config.bucket_name,
            repo_id,
            run_name,
            start_time,
            end_time,
            descending,
            diagnose,
        )

    def list_run_artifact_files(
        self, repo_id: str, run_name: str, prefix: str, recursive: bool = False
    ) -> List[Artifact]:
        return base_artifacts.list_run_artifact_files(
            self._storage, repo_id, run_name, prefix, recursive
        )

    def download_run_artifact_files(
        self,
        repo_id: str,
        run_name: str,
        output_dir: Optional[PathLike],
        files_path: Optional[PathLike] = None,
    ):
        artifacts = self.list_run_artifact_files(
            repo_id, run_name=run_name, prefix="", recursive=True
        )
        base_artifacts.download_run_artifact_files(
            storage=self._storage,
            repo_id=repo_id,
            artifacts=artifacts,
            output_dir=output_dir,
            files_path=files_path,
        )

    def upload_job_artifact_files(
        self,
        repo_id: str,
        job_id: str,
        artifact_name: str,
        artifact_path: PathLike,
        local_path: PathLike,
    ):
        base_artifacts.upload_job_artifact_files(
            storage=self._storage,
            repo_id=repo_id,
            job_id=job_id,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
            local_path=local_path,
        )

    def list_tag_heads(self, repo_id: str) -> List[TagHead]:
        return base_tags.list_tag_heads(self._storage, repo_id)

    def get_tag_head(self, repo_id: str, tag_name: str) -> Optional[TagHead]:
        return base_tags.get_tag_head(self._storage, repo_id, tag_name)

    def add_tag_from_run(
        self, repo_id: str, tag_name: str, run_name: str, run_jobs: Optional[List[Job]]
    ):
        base_tags.create_tag_from_run(
            self._storage,
            repo_id,
            tag_name,
            run_name,
            run_jobs,
        )

    def add_tag_from_local_dirs(
        self,
        repo: Repo,
        hub_user_name: str,
        tag_name: str,
        local_dirs: List[str],
        artifact_paths: List[str],
    ):
        base_tags.create_tag_from_local_dirs(
            storage=self._storage,
            repo=repo,
            hub_user_name=hub_user_name,
            tag_name=tag_name,
            local_dirs=local_dirs,
            artifact_paths=artifact_paths,
        )

    def delete_tag_head(self, repo_id: str, tag_head: TagHead):
        base_tags.delete_tag(self._storage, repo_id, tag_head)

    def list_repo_heads(self) -> List[RepoHead]:
        return base_repos.list_repo_heads(self._storage)

    def update_repo_last_run_at(self, repo_spec: RepoSpec, last_run_at: int):
        base_repos.update_repo_last_run_at(
            self._storage,
            repo_spec,
            last_run_at,
        )

    def get_repo_credentials(self, repo_id: str) -> Optional[RemoteRepoCredentials]:
        return base_repos.get_repo_credentials(self._secrets_manager, repo_id)

    def save_repo_credentials(self, repo_id: str, repo_credentials: RemoteRepoCredentials):
        base_repos.save_repo_credentials(self._secrets_manager, repo_id, repo_credentials)

    def delete_repo(self, repo_id: str):
        base_repos.delete_repo(self._storage, repo_id)

    def list_secret_names(self, repo_id: str) -> List[str]:
        return base_secrets.list_secret_names(self._storage, repo_id)

    def get_secret(self, repo_id: str, secret_name: str) -> Optional[Secret]:
        return base_secrets.get_secret(self._secrets_manager, repo_id, repo_id)

    def add_secret(self, repo_id: str, secret: Secret):
        base_secrets.add_secret(self._storage, self._secrets_manager, repo_id, secret)

    def update_secret(self, repo_id: str, secret: Secret):
        base_secrets.update_secret(self._storage, self._secrets_manager, repo_id, secret)

    def delete_secret(self, repo_id: str, secret_name: str):
        base_secrets.delete_secret(self._storage, self._secrets_manager, repo_id, repo_id)

    def get_signed_download_url(self, object_key: str) -> str:
        return self._storage.get_signed_download_url(object_key)

    def get_signed_upload_url(self, object_key: str) -> str:
        return self._storage.get_signed_upload_url(object_key)

    def delete_workflow_cache(self, repo_id: str, hub_user_name: str, workflow_name: str):
        base_cache.delete_workflow_cache(self._storage, repo_id, hub_user_name, workflow_name)
