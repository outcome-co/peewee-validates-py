"""Invoke tasks."""

from invoke import Collection
from outcome.devkit.invoke import tasks

namespace: Collection = tasks.namespace
