ifndef MK_RELEASE_PY
MK_RELEASE_PY=1

include make/env.Makefile
include make/ci.py.Makefile

PYPI_NAME = $(shell $(READ_PYPROJECT_KEY) pypi.name)
PYPI_URL = $(shell $(READ_PYPROJECT_KEY) pypi.url)

# poetry expects the environment variables to match the name of
# the repository, so we have to create dynamic env vars
#
# Example, your repository is called `otc`, poetry expects:
# - PYPI_HTTP_BASIC_OTC_USERNAME
# - PYPI_HTTP_BASIC_OTC_PASSWORD
#

# Currently this normalisation only transforms to uppercase
# if you have a more complicated name, say with hyphens, etc.
# you'll need to change this
PYPI_NORMALISED_NAME = $(shell echo $(PYPI_NAME) | tr a-z A-Z)

POETRY_USERNAME_ENV = POETRY_HTTP_BASIC_${PYPI_NORMALISED_NAME}_USERNAME
POETRY_PASSWORD_ENV = POETRY_HTTP_BASIC_${PYPI_NORMALISED_NAME}_PASSWORD

build: clean  ## Build the python package
	poetry build

publish: export $(POETRY_USERNAME_ENV) = $(POETRY_USERNAME)
publish: export $(POETRY_PASSWORD_ENV) = $(POETRY_PASSWORD)
publish: build ## Publish the python package to the repository
	poetry config repositories.$(PYPI_NAME) $(PYPI_URL)
	poetry publish -r $(PYPI_NAME)

endif
