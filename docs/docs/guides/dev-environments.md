# Dev environments

A dev environment is a virtual machine pre-configured with hardware resources, source code, dependencies, and an
IDE.

Using `dstack`, you can define such a dev environment through a configuration file and provision it with a single
command.

## Configuration

To configure a dev environment, create its configuration file. It can be defined
in any folder but must be named with a suffix `.dstack.yml`.

Here's an example:

<div editor-title=".dstack.yml"> 

```yaml
type: dev-environment
ide: vscode
```

</div>

## Running a dev environment

To run a dev environment, use the `dstack run` command followed by the path to the directory you want to use as the
working directory during development.

<div class="termy">

```shell
$ dstack run . 

 RUN          CONFIGURATION   USER   PROJECT  INSTANCE  RESOURCES        SPOT
 fast-moth-1  app.dstack.yml  admin  local    -         5xCPUs, 15987MB  auto  
 
Provisioning and starting SSH tunnel...
---> 100%

To open in VS Code Desktop, use one of these links:
  vscode://vscode-remote/ssh-remote+fast-moth-1/workflow

To exit, press Ctrl+C.
```

</div>

The `dstack run` command provisions cloud resources, pre-installs the environment, code, and the IDE, and establishes an
SSH tunnel for secure access. 

To open the dev environment via a desktop IDE, click the URL in the output.

![](/assets/images/dstack-vscode-jupyter.png){ width=800 }

By default, VS Code comes with pre-installed Python and Jupyter extensions.

??? info "Using .gitignore"
    When running a dev environment, `dstack` uses the exact version of code that is present in the folder where you
    use the `dstack run` command.

    If your folder has large files or folders, this may affect the performance of the `dstack run` command. To avoid this,
    make sure to create a `.gitignore` file and include these large files or folders that you don't want to include when
    running dev environments or tasks.

!!! info "Default configuration"
    By default, the `dstack run` command looks for the default configuration file named `.dstack.yml` in the given working
    directory. If your configuration file is named differently, you can specify a path to it using the `-f` argument.

For more details on the `dstack run` command, refer to the [`dstack run` Reference](../../reference/cli/run.md).

## Environment

By default, a dev environment includes pre-installed CUDA driver, Python (matching your local version), 
and Conda (with Miniforge).

To modify the Python version or install additional packages beforehand, you can utilize other YAML properties 
like `python`, `init`, and `build`. 

### Pre-building the environment

In case you'd like to pre-build the environment rather than install packaged on every run,
you can use the `build` property. Here's an example:

<div editor-title="train.dstack.yml"> 

```yaml
type: task
build:
  - pip install -r requirements.txt
commands:
  - python train.py
```

</div>

To pre-build the environment you have two options:

1. Run the `dstack build` command:

    <div class="termy">
    
    ```shell
    $ dstack build . -f train.dstack.yml
    ```
    
    </div>
    
    Similar to the `dstack run` command, `dstack build` also provisions cloud resources and uses them to pre-build the
    environment. Consequently, when running the `dstack run` command again, it will reuse the pre-built image, leading
    to faster startup times, particularly for complex setups.

2. Use `--build` with `dstack run`

    <div class="termy">
    
    ```shell
    $ dstack run . -f train.dstack.yml --build
    ```
    
    </div>

    If there is no pre-built image, the `dstack run` command will build it and upload it to the storage. If the pre-built
    image is already available, the `dstack run` command will reuse it.

For more details on the syntax of `.dstack.yml`, refer to the [Reference](../../reference/dstack.yml).

## Profiles

If you [configured](../projects.md) a project that uses a cloud backend, you can define profiles that specify the
project and the cloud resources to be used.

To configure a profile, simply create the `profiles.yml` file in the `.dstack` folder within your project directory. 
Here's an example:

<div editor-title=".dstack/profiles.yml"> 

```yaml
profiles:
  - name: gpu-large
    project: gcp
    resources:
       memory: 48GB
       gpu:
         memory: 24GB
    default: true
```

</div>

By default, the `dstack run` command uses the default profile.

!!! info "Multiple profiles"
    You can define multiple profiles according to your needs and use any of them with the `dstack run` command by specifying
    the desired profile using the `--profile` argument.

For more details on the syntax of the `profiles.yml` file, refer to the [`profiles.yml` Reference](../../reference/profiles.yml.md).