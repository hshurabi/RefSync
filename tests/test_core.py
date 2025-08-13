import os
from refsync.core import process_folder

def test_import():
    assert callable(process_folder)
