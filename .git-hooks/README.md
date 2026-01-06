# Git hooks

Git hooks are a set of scripts that are executed at specific points in the Git workflow. They can be used to enforce coding standards, automate testing, and perform other tasks automatically. Git hooks can be configured to run on the local machine or on a remote server.

## Available Hooks

- `pre-commit`: Runs before a commit is made.
- `post-commit`: Runs after a commit is made.
- `pre-push`: Runs before a push is made to a remote repository.
- `post-merge`: Runs after a merge is completed.

## Configuration

To setup git hooks run:

> git config core.hooksPath .git-hooks || echo 'Not in a git repo'
