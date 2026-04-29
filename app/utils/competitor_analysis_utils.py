import enum


class SourceType(str, enum.Enum):
    excel = 'excel'
    onec = '1c'
    api = 'api'


class ImportStatus(str, enum.Enum):
    uploaded = 'uploaded'
    processing = 'processing'
    done = 'done'
    error = 'error'
