"""LMDB backend"""

from hat.event.server.backends.lmdb import common
from hat.event.server.backends.lmdb import backend


json_schema_id = 'hat://event/backends/lmdb.yaml#'
json_schema_repo = common.json_schema_repo
create = backend.create
