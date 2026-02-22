# Copyright 2024 NickEngmann
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from unittest.mock import MagicMock

# Skip ament_pep257 tests if not available (e.g., in minimal test environments)
try:
    from ament_pep257.main import main
except ImportError:
    # If ament_pep257 is not available, skip the test
    import pytest
    pytest.skip("ament_pep257 not available", allow_module_level=True)
    sys.exit(0)

if __name__ == '__main__':
    sys.exit(main())