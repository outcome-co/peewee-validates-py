ifndef MK_ENV
MK_ENV=1

include make/env.*.Makefile

# Determine whether we're in a CI environment such as Github Actions
# Github Actions defines a GITHUB_ACTIONS=true variable
#
# Generic tools can set CI=true 
ifneq "$(or $(GITHUB_ACTIONS), $(CI), $(PRE_COMMIT))" ""
$(info Running in CI mode)
INSIDE_CI=1
else
NOT_INSIDE_CI=1
endif

# VARIABLES

# We unfortunately have to wrap some of these in ifndef otherwise they replace the values of
# external environment variables, so for example if you run
#
# DB_SERVER=postgres make test
#
# Without the ifndef, DB_SERVER will not be equal to 'postgres', but will be equal to whatever is read from the TOML

# Are we in a git repo?
IN_GIT = $(shell ((test -d .git && echo "1") || echo "0") 2> /dev/null)

ifeq ($(IN_GIT),1)
GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD)
GIT_BRANCH_NORMAL = $(shell echo $(GIT_BRANCH) | tr '/' '-')

# The master branch can be called HEAD when checked out in a detached state
ifeq ($(GIT_BRANCH),master)
IN_GIT_MAIN=1
else ifeq ($(GIT_BRANCH),HEAD)
IN_GIT_MAIN=1
else
IN_GIT_MAIN=0
endif

else
IN_GIT_MAIN=0
endif

COMMIT_SHA1 = $(shell git rev-parse --short=8 HEAD)
PLATFORM = $(shell echo $$(uname -s) | tr '[:upper:]' '[:lower:]')

empty :=
space := $(empty) $(empty)

endif
