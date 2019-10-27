import logging
import pytest

from gssurgo.core.userprofile import UserProfile

@pytest.fixture
def victim():
    return UserProfile()

def test_get_test_data(victim):
    assert 'TestData' in victim.get_test_data()

if __name__ == '__main__':
    pytest.main([__file__])