from typing import List

from pydantic import BaseModel

from dstack._internal.core.instance import InstanceType
from dstack._internal.core.job import Job


class JobPlan(BaseModel):
    job: Job
    instance_type: InstanceType


class RunPlan(BaseModel):
    project: str
    hub_user_name: str
    job_plans: List[JobPlan]
