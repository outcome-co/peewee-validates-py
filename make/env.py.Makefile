ifndef MK_ENV_PY
MK_ENV_PY=1

READ_PYPROJECT_KEY=docker run --rm -v $$(pwd):/work/ outcomeco/action-read-toml:latest --path /work/pyproject.toml --key

endif
