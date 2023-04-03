declare type TProjectBackendType = 'aws' | 'gcp' | 'azure';

declare type TProjectBackend = { type: TProjectBackendType } & TProjectBackendAWSWithTitles  & TProjectBackendGCP
declare interface IProject {
    project_name: string,
    backend: TProjectBackend,
    members: IProjectMember[]
}

declare type TAwsBucket = {
    name: string;
    created?: string;
    region?: string;
}

declare interface IProjectAwsBackendValues {
        region_name: {
            selected?: string,
            values: { value: string, label: string}[]
        },
        s3_bucket_name: {
            selected?: string,
            values: TAwsBucket[]
        },
        ec2_subnet_id: {
            selected?: string | null,
            values: { value: string, label: string}[]
        },
}

declare interface IProjectGCPBackendValues {
    area: {
        selected?: string,
        values: { value: string, label: string}[]
    },
    bucket_name: null | {
        selected?: string,
        values: { value: string, label: string}[]
    },
    region: null | {
        selected?: string,
        values: { value: string, label: string}[]
    },
    vpc_subnet: null | {
        selected?: string,
        values: { value: string, label: string}[]
    },
    zone: null | {
        selected?: string,
        values: { value: string, label: string}[]
    },
}

declare type IProjectBackendValues = { type: TProjectBackendType } & IProjectAwsBackendValues & IProjectGCPBackendValues

declare interface TProjectBackendAWS {
    access_key: string,
    secret_key: string,
    region_name: string,
    s3_bucket_name: string,
    ec2_subnet_id: string | null,
}

declare interface TProjectBackendGCP {
    credentials: string,
    area: string,
    region: string,
    zone: string,
    bucket_name: string,
    vpc_subnet: string,
}

declare interface TProjectBackendAWSWithTitles extends TProjectBackendAWS {
    region_name_title: string,
}

declare interface IProjectMember {
    user_name: string,
    project_role: TProjectRole,
}

declare type TProjectRole = 'read' | 'run' | 'admin'
