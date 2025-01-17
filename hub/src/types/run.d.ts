declare type TRunsRequestParams = {
    name: IProject['project_name'];
    repo_id?: string;
    run_name?: string;
    include_request_heads?: boolean;
};

declare type TDeleteRunsRequestParams = {
    name: IProject['project_name'];
    repo_id?: string;
    run_names: IRun['run_name'][];
};

declare type TStopRunsRequestParams = {
    name: IProject['project_name'];
    repo_id?: string;
    run_names: IRun['run_name'][];
    abort: boolean;
};


declare type TRunStatus =
    | 'pending'
    | 'submitted'
    | 'downloading'
    | 'running'
    | 'uploading'
    | 'stopping'
    | 'stopped'
    | 'aborting'
    | 'aborted'
    | 'failed'
    | 'done';

declare interface IRunJobHead {
    job_id: string,
    repo_ref: {
        repo_type: string,
        repo_id: string,
        repo_user_id: string
    },
    run_name: string,

    configuration_path: string,
    instance_type: string,
    workflow_name: null | string,
    provider_name: string,
    status: TRunStatus,
    error_code: null | string,
    container_exit_code: null,
    submitted_at: number,
    artifact_paths: null,
    tag_name: null | string,
    app_names: string[]
}

declare interface IRun {
    run_name: string,
    workflow_name: string | null,
    provider_name: string | null,
    repo_user_id: string,
    hub_user_name: string,
    artifact_heads: null | {
        job_id: string
        artifact_path: string
    }[],
    status: TRunStatus,
    submitted_at: number,
    tag_name: string | null,
    "app_heads": null |
    {
        job_id: string
        artifact_path: string
    }[],
    request_heads: string | null,
    job_heads: IRunJobHead[]
}
