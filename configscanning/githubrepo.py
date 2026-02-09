"""Tools for use with a specific GitHub repo"""

import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, urlparse

import pygit2
from filelock import FileLock
from github import Auth, Github, GithubIntegration
from github.Repository import Repository
from pygit2.enums import BranchType, ObjectType, ResetMode

logger = logging.getLogger(__name__)


# pygit2 uses the C wrapper and pylint falsely things many things are not defined because of this.
# pylint: disable=no-member
class GitHubRepo:
    """This represents a cloned repo"""

    location: Path
    parent_dir: Path | None
    repourl: str | None
    repourlobj: ParseResult
    gh_org: str
    gh_reponame: str
    branches_to_fetch: set[str]
    _github: Github | None
    _gh_repo: Repository | None

    # This is a gitpython Repo if a clone exists, otherwise None
    repo: pygit2.Repository | None

    def __init__(
        self,
        location: str | Path | None = None,
        parent_dir: str | Path | None = None,
        repourl: str | None = None,
        branches_to_fetch: set[str] | None = None,
    ) -> None:
        """
        This represents a repo to be cloned and kept up-to-date within the AIPIPE platform.

        Only GitHub repos are supported.

        The clone of the repo may exist or not.

        Args:
              location (str): File system location of clone, eg /repos/github.com/ORGNAME/REPONAME
                              May be None if repourl and parent_dir are specified
              parent_dir (str): File system location which will contain clones eg, /repos/
                                Usually /github.host.name/ORGNAME/REPONAME will be added.
                                May be None if location is specified.
              repourl (str): https URL for the repo - MUST be of form
                             https://github-host-name/orgname/reponame.git
              branches_to_fetch (set[str]): list of branch names to fetch - these MUST exist
        """
        if branches_to_fetch is None:
            branches_to_fetch = {"main"}

        self.repourl = repourl
        self.repourlobj = urlparse(repourl or "")
        self.branches_to_fetch = branches_to_fetch
        self.parent_dir = Path(parent_dir) if parent_dir is not None else None
        self._github = None
        self._gh_repo = None
        self._access_token = None

        path_parts = self.repourlobj.path[1:].split("/")
        self.gh_org = path_parts[0]
        self.gh_reponame = path_parts[1]
        self.gh_reponame = self.gh_reponame.removesuffix(".git")
        git_host = self.repourlobj.hostname or ""

        if location is None:
            assert parent_dir is not None
            self.location = Path() / parent_dir / git_host / self.gh_org / self.gh_reponame
        else:
            self.location = Path(location)

            if parent_dir is None:
                self.parent_dir = self.location.parent.parent.parent

        try:
            self.repo = pygit2.Repository(self.location, pygit2.GIT_REPOSITORY_OPEN_NO_SEARCH)
        except pygit2.GitError:  # pylint disable=no-member  (use of C wrapper breaks linting)
            self.repo = None

        assert self.parent_dir is not None
        self.lock = FileLock(
            self.parent_dir / ("_AIPIPE_LOCK_" + git_host + "-" + self.gh_org + "-" + self.gh_reponame),
        )

    @property
    def git_host(self) -> str:
        """Returns the hostname of the github server"""
        return self.repourlobj.hostname or ""

    def authenticate_to_github(self, app_id: int | str | None, app_private_key: str | None) -> Github:
        """
        Authenticate to GitHub as an app.

        None may be specified as the authentication data in when the repo involved is public.

        Args:
              app_id (str): AIPIPE GitHub App ID - provided when we register our app.
                            There is one per app registration (this is not app installation
                            specific).
              app_private_key (str): A private key generated for our app registration in the app
                                     management page github.com/organizations/org/settings/apps
        """
        if app_id is None:
            # This works only with public repos and limited methods.
            self._github = Github()
            self._access_token = None
        else:
            # First we must integrate as the app, which gives us limited access.
            auth = Auth.AppAuth(app_id, app_private_key)
            ghi = GithubIntegration(auth=auth)

            # We can use this to find the app installation (for the organization which owns the
            # repo), then get an authenticated client object from there.
            gh_installation = ghi.get_repo_installation(self.gh_org, self.gh_reponame)

            # Now we can get a full client object which can use the full API.
            self._github = gh_installation.get_github_for_installation()

            # We need this token for use with gitpython so that we can clone private repos.
            # Access the internal requester via name-mangled attribute.
            _requester_attr = "_Github__requester"
            self._access_token = getattr(self._github, _requester_attr).auth.token

        assert self._github is not None
        return self._github

    def get_github_repo(self) -> Repository:
        """Returns a github.Repository object representing the repo"""
        assert self._github is not None
        if self._gh_repo is None:
            self._gh_repo = self._github.get_repo(f"{self.gh_org}/{self.gh_reponame}")
        return self._gh_repo

    def _refspecs_to_pull(self) -> list[str]:
        """
        This returns a list of refspecs we should fetch from our remote, eg
          ["refs/heads/main:refs/remotes/origin/main"]
        """
        return [f"refs/heads/{branch}:refs/remotes/origin/{branch}" for branch in self.branches_to_fetch]

    def ref_positions(self) -> dict[str, Any]:
        """
        Returns a map from relevant branch/tag/... name to the commit it currently points to.
        Only returns results for branches in self.branches_to_fetch
        """
        assert self.repo is not None

        def data_for_branch(branch_name: str) -> dict[str, Any]:
            assert self.repo is not None
            commit_id = self.repo.branches[branch_name].target
            commit = self.repo.get(commit_id)
            assert isinstance(commit, pygit2.Commit)
            return {
                "hash": commit.id,
                "summary": commit.message.split("\n")[0],
                "commitDate": commit.commit_time,
            }

        return {
            self.repo.branches[branch_name].name: data_for_branch(branch_name)
            for branch_name in self.repo.branches.local
            if branch_name in self.branches_to_fetch
        }

    def update(self) -> None:
        """
        Updates our clone of the repo, creating it if necessary.

        This means that all branches in branches_to_fetch will have been fetched, but any
        other tags or branches may not have been.
        """
        logger.info(f"Updating repo {self.repourl} in {self.location}")

        # We must determine the branches to try to fetch because .fetch and .pull are not very
        # good at telling us when the branch doesn't exist in the remote.
        #
        # For that reason, we can't just use the list of branches we're given, we need to remove
        # any non-existent ones.
        gh_repo = self.get_github_repo()
        available_branches = set(map(lambda b: b.name, gh_repo.get_branches()))
        self.branches_to_fetch = self.branches_to_fetch & available_branches
        refspecs = self._refspecs_to_pull()

        with self.lock:
            logger.debug(f"Locked repo {self.repourl} in {self.location}")
            if self.repo is None:
                # No clone or clone is invalid at time of construction.
                # Check again now lock held.
                try:
                    self.repo = pygit2.Repository(self.location, pygit2.GIT_REPOSITORY_OPEN_NO_SEARCH)
                except pygit2.GitError:  # pylint disable=no-member
                    self.repo = None

            if self.repo is None:
                logger.info(f"Repo {self.repourl} does not exist in {self.location}; cloning")

                # Delete repo if it exists (in case of broken / partial clone)
                if self.location.exists():
                    shutil.rmtree(self.location)

                os.makedirs(self.location, exist_ok=True)

                self.repo = pygit2.init_repository(
                    path=self.location,
                    initial_head="main",
                )

                assert self.repourl is not None
                self.repo.remotes.create("origin", self.repourl, fetch=refspecs[0])

                for refspec in refspecs[1:]:
                    self.repo.remotes.add_fetch("origin", refspec)

                logger.debug(self.ref_positions())

            # Repo now exists.
            assert self.repo is not None
            #
            # First, fetch from remotes. ie, refs/remotes/origin/<branches> become up-to-date with
            # what's in GitHub
            logger.info(f"Fetching for repo {self.repourl} clone in {self.location}")

            transfer_progress = self.repo.remotes["origin"].fetch(
                callbacks=pygit2.RemoteCallbacks(credentials=pygit2.UserPass("none", self._access_token or ""))
            )

            logger.info(f"Fetched {transfer_progress}")

            # Now we can move our local branches to point to the tip of the remote branches.
            # We assume we can simply fast-forward here, which should be true.
            for branch in self.branches_to_fetch:
                logger.debug(f"Updating branch {branch}")
                remote_branch: pygit2.Branch = self.repo.lookup_branch(f"origin/{branch}", BranchType.REMOTE)
                logger.debug(f"Remote branch at {remote_branch.target}")

                if branch not in self.repo.branches.local:
                    # No local branch - create it
                    logger.info(f"Creating local branch {branch}")
                    remote_commit = self.repo.get(remote_branch.target)
                    assert isinstance(remote_commit, pygit2.Commit)
                    self.repo.branches.create(branch, remote_commit)
                else:
                    logger.info(f"Fast-forwarding local branch {branch}")
                    self.repo.checkout(f"refs/heads/{branch}")
                    local_branch: pygit2.Branch = self.repo.lookup_branch(branch)
                    local_branch.set_target(remote_branch.target)
                    self.repo.head.set_target(remote_branch.target)

            logger.debug(self.ref_positions())

    def has_ref(self, ref: str) -> bool:
        """Returns true if ref (eg, 'refs/tags/tagname') is known in the repo"""
        assert self.repo is not None
        return ref in self.repo.references

    def changed_files(
        self, since: str | None, until: str = "HEAD", only_matching: Callable[[str], bool] = lambda fname: True
    ) -> set[str]:
        """
        Return a set containing the paths (relative to repo root) of all files which:
          1) if 'since' is not None, have been changed between commit/ref 'since' and the current
             workdir commit, or, if 'since' is None, which exist at all in the current commit's
             tree;
          2) when passed to the function only_matching result in a True response.

          eg, changed_files(None, lambda f: f.endswith(".yaml")) will find all yaml files in the
              current branch, whereas changed_files("refs/tags/_SCANNED_main") will find
              all files changed between tag _SCANNED_main and the current work dir.
        """
        assert self.repo is not None
        if since is None:
            deltas = self.repo.revparse_single(until).peel(pygit2.Tree).diff_to_tree().deltas
        else:
            deltas = self.repo.diff(since, until).deltas

        return {delta.new_file.path for delta in deltas if only_matching(delta.new_file.path)}

    def checkout_and_reset(self, ref: str) -> None:
        """Set up the working directory with what is pointing to by 'ref', deleting any existing
        changes."""
        assert self.repo is not None
        self.repo.checkout(ref)
        self.repo.reset(self.repo.lookup_reference(ref).target, ResetMode.HARD)

    def delete_tag(self, name: str) -> None:
        """Delete the named tag, if it exists, otherwise do nothing"""
        assert self.repo is not None
        tagref = f"refs/tags/{name}"
        if tagref in self.repo.references:
            # Tag exists - delete it.
            self.repo.references[tagref].delete()

    def create_tag(self, name: str, message: str) -> None:
        """Create the tag specified pointing at the current HEAD. Deletes any old tag."""
        assert self.repo is not None
        self.delete_tag(name)
        self.repo.create_tag(
            name,
            self.repo.head.target,
            ObjectType.COMMIT,
            pygit2.Signature("Config Scanner", "configscanner@ai-pipeline.org"),
            message,
        )
