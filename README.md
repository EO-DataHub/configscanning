# EODHP config-scanner

This is the EODHP config scanner. It scans git repositories for changes and can be imported if additional
functionality is required if changes are found.

This component has the following responsibilities:
* To synchronize git repositories into a persistent volume in the platform.
* To scan these repositories for configuration files which the platform must process, and which define the Models,
  Workflows and Applications which must be deployed.
* To process this configuration and create/manage Model, Workflow and Application kubernetes CRs.


# Setup

You will need Python 3.13 and [uv](https://docs.astral.sh/uv/).

```commandline
make setup
```

This will install dependencies via `uv sync` and set up `pre-commit` hooks.

It's safe and fast to run `make setup` repeatedly as it will only update things if
they have changed.

To modify dependencies, edit `pyproject.toml` and run `uv sync`.


# Formatting and linting

The project uses [Ruff](https://docs.astral.sh/ruff/) for formatting and linting, and
[Pyright](https://github.com/microsoft/pyright) for type checking.

```commandline
make format   # Auto-fix lint issues and format code
make check    # Run all checks (ruff, pyright, validate-pyproject)
```


# Testing

```commandline
make testonce  # Run tests once
make test      # Run tests continuously (watch mode)
```

Beware that some tests are marked `integrationtest` and will talk to GitHub and check out repos in a temporary directory.


# Building for deployment

You will need to be logged into ECR (see 'Configure AWS ECR' in argocd-deployment/README.md).

Then build, tag and push the image:
* `git tag <version>` (if version is not 'latest')
* `make dockerbuild dockerpush VERSION=<version>` (default version is 'latest')


# Configuration

The following environment variables are used:
- `AWS_ACCESS_KEY` - key for AWS access (optional)
- `AWS_SECRET_ACCESS_KEY` - secret access key for AWS (optional)
- `KUBERNETES_SERVICE_HOST` - service host address for kubernetes (optional)
- `GITHUB_APP_ID` - ID of GitHub app (optional, reads in from file instead if not provided)
- `GITHUB_APP_PRIVATE_KEY` - private key for GitHub app (optional, reads in from file instead if not provided)


## Development

- Code is in `configscanning`.
- Formatting and linting: [Ruff](https://docs.astral.sh/ruff/).
- Type checking: [Pyright](https://github.com/microsoft/pyright).
- Pre-commit checks are installed with `make setup`.

Useful Makefile targets:

- `make setup`: Set up or update the dev environment.
- `make test`: Run tests continuously (watch mode).
- `make testonce`: Run tests once.
- `make check`: Run all checks (ruff, pyright, validate-pyproject).
- `make format`: Auto-fix lint issues and format code.
- `make dockerbuild`: Build a Docker image.
- `make dockerpush`: Push a Docker image.


# License

This project is licensed under the Telespazio UK Ltd Apache 2.0 Licence. See [LICENSE](LICENSE.txt) for details.
