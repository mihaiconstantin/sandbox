"""Run the T1 contract scenarios against the shipped neutral fakes."""

# Imports.
import pytest

# Import the contract scenario sets.
from port_contract import BuilderContract, RuntimeContract

# Import the shipped fakes.
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.runtime import FakeRuntime


# Supply a fake builder configured by the contract's buildable fact.
class FakeBuilderContract(BuilderContract):
    # Supply a fresh fake builder.
    @pytest.fixture
    def builder(self, buildable: bool) -> FakeBuilder:
        # Return a builder matching the selected service shape.
        return FakeBuilder(buildable = buildable)


# Verify the buildable fake builder satisfies the Builder contract.
class TestFakeBuilderContract(FakeBuilderContract):
    pass


# Verify the image-only fake builder satisfies the same Builder contract.
class TestFakeImageOnlyBuilderContract(FakeBuilderContract):
    # Select an image-only service.
    @pytest.fixture
    def buildable(self) -> bool:
        # Report an image-only service.
        return False


# Verify the fake runtime satisfies the Runtime contract.
class TestFakeRuntimeContract(RuntimeContract):
    # Supply a fresh fake runtime.
    @pytest.fixture
    def runtime(self) -> FakeRuntime:
        # Return a default stateful runtime.
        return FakeRuntime()

    # Supply a second independent fake runtime.
    @pytest.fixture
    def other_runtime(self) -> FakeRuntime:
        # Return another default stateful runtime.
        return FakeRuntime()

    # Supply a runtime configured for one interactive shell status.
    @pytest.fixture
    def runtime_with_enter_status(self):
        # Return a factory that records the requested shell status.
        return lambda status: FakeRuntime(enter_status = status)
