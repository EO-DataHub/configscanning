# EODHP config-scanner

This is the EODHP config scanner. It scans git repositories for changes and can be imported if additional 
functionality is required if changes are found. 

This component has the following responsibilities:
* To synchronize git repositories into a persistent volume in the platform.
* To scan these repositories for configuration files which the platform must process, and which define the Models,
  Workflows and Applications which must be deployed.
* To process this configuration and create/manage Model, Workflow and Application kubernetes CRs.


# Setup

You will need Python 3.11. On Debian you may need:
* `apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys F23C5A6CF475977595C89F51BA6932366A755776`
* `sudo add-apt-repository -y 'deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu focal main'` (or `jammy` in place of 
  `focal` for later Debian)
* `sudo apt update`
* `sudo apt install python3.11 python3.11-venv`

and on Ubuntu you may need
* `sudo add-apt-repository -y 'ppa:deadsnakes/ppa'`
* `sudo apt update`
* `sudo apt install python3.11 python3.11-venv`

then:

* `virtualenv venv -p python3.11`
* `. venv/bin/activate`
* `rehash`
* `python -m ensurepip -U`
* `pip3 install -r requirements.txt -r requirements-dev.txt`

To modify the requirements edit `pyproject.toml` and run first `pip-compile`, then 
`pip-compile --extra dev -o requirements-dev.txt`. The second should only be necessary if you modify the dev 
dependencies.


## Installing via makefile

```commandline
make setup
```

This will create a virtual environment called `venv`, build `requirements.txt` and
`requirements-dev.txt` from `pyproject.toml` if they're out of date, install the Python
and Node dependencies and install `pre-commit`.

It's safe and fast to run `make setup` repeatedly as it will only update these things if
they have changed.

After `make setup` you can run `pre-commit` to run pre-commit checks on staged changes and
`pre-commit run --all-files` to run them on all files. This replicates the linter checks that
run from GitHub actions.


# Formatting and linting

The project is formatted with black, run `black --line-length 100 .` to reformat or use an editor integration.
A GitHub workflow will reformat what you commit.

The project is also linted with ruff, run `ruff .` or use an editor integration. The GitHub workflow will also
run this.


# Testing

Run `pytest` to test. Beware that this will talk to GitHub and check out some repos in a temporary directory, so running
this with `--looponfail` may be undesirable (unless you exclude tests marked `integrationtest`).

To test the Docker build, use `make testdocker`.


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

- Code is in `planet-harvester`.
- Formatting: [Black](https://black.readthedocs.io/), [Ruff](https://docs.astral.sh/ruff/), [isort](https://pycqa.github.io/isort/).
- Linting: [Pylint](https://pylint.pycqa.org/).
- Pre-commit checks are installed with `make setup`.

Useful Makefile targets:

- `make setup`: Set up or update the dev environment.
- `make test`: Run tests continuously.
- `make testonce`: Run tests once.
- `make lint`: Run all linters and formatters.
- `make requirements`: Update requirements files from `pyproject.toml`.
- `make requirements-update`: Update to the latest allowed versions.
- `make dockerbuild`: Build a Docker image.
- `make dockerpush`: Push a Docker image.


# License

This project is licensed under the Telespazio UK Ltd Apache 2.0 Licence. See [LICENSE](LICENSE.txt) for details.
