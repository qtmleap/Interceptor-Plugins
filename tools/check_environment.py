#!/usr/bin/env python3
"""Read existing deployment protections before a job can reference its environment."""
from repository_config import ToolError, check_repository, parse_args, run_main
from setup import ENVIRONMENT, GitHub, environment_state


def require_environment(api, repository):
    repository = check_repository(repository)
    if environment_state(api, 'repos/' + repository) is None:
        raise ToolError('github-pages environment is missing; restore its master-only policy before publishing')


def main(argv):
    args = parse_args(argv, ('--repository',))
    require_environment(GitHub(), args['--repository'])
    print(f'{ENVIRONMENT}: existing master-only deployment policy verified')


if __name__ == '__main__':
    run_main(main)
